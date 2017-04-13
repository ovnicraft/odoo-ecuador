# -*- coding: utf-8 -*-
# © 2016 Cristian Salamea <cristian.salamea@ayni.com.ec>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from datetime import timedelta
from odoo import api, fields, models, _
from odoo.tools import float_compare, float_is_zero


def seconds(td):
    assert isinstance(td, timedelta)
    return (td.microseconds + (td.seconds + td.days * 24 * 3600) * 10**6) / 10.**6  # noqa


class HrSalaryRule(models.Model):
    _inherit = 'hr.salary.rule'

    def get_account(self, contract, side):
        # Try simple
        if side == 'debit' and self.account_debit:
            return self.account_debit
        elif side == 'credit' and self.account_credit:
            return self.account_credit
        # Goes dynamic
        config = self.account_ids.filtered(lambda l: l.department_id.id == contract.department_id.id)  # noqa
        if side == 'debit':
            return config.account_debit_id.id
        else:
            return config.account_credit_id.id


class HrPayslip(models.Model):

    _inherit = 'hr.payslip'

    @api.model
    def get_worked_day_lines(self, contract_ids, date_from, date_to):
        """
        @param contract_ids: list of contract id
        @return: returns a list of dict containing the input
        that should be applied for the given contract
        between date_from and date_to
        """

        def was_on_leave_interval(employee_id, date_from, date_to):
            date_from = fields.Datetime.to_string(date_from)
            date_to = fields.Datetime.to_string(date_to)
            return self.env['hr.holidays'].search([
                ('state', '=', 'validate'),
                ('employee_id', '=', employee_id),
                ('type', '=', 'remove'),
                ('date_from', '<=', date_from),
                ('date_to', '>=', date_to)
            ], limit=1)

        res = []
        # fill only if the contract as a working schedule linked
        uom_day = self.env.ref('product.product_uom_day', raise_if_not_found=False)  # noqa
        for contract in self.env['hr.contract'].browse(contract_ids).filtered(lambda contract: contract.working_hours):  # noqa
            uom_hour = contract.employee_id.resource_id.calendar_id.uom_id or self.env.ref('product.product_uom_hour', raise_if_not_found=False)  # noqa
            interval_data = []
            holidays = self.env['hr.holidays']
            attendances = {
                'name': _("Normal Working Days paid at 100%"),
                'sequence': 1,
                'code': 'WORK100',
                'number_of_days': 0.0,
                'number_of_hours': 0.0,
                'contract_id': contract.id,
            }
            leaves = {}
            day_from = fields.Datetime.from_string(date_from)
            day_to = fields.Datetime.from_string(date_to)
            nb_of_days = (day_to - day_from).days + 1

            # Gather all intervals and holidays
            for day in range(0, nb_of_days):
                working_intervals_on_day = contract.working_hours.get_working_intervals_of_day(start_dt=day_from + timedelta(days=day))  # noqa
                for interval in working_intervals_on_day:
                    interval_data.append((interval, was_on_leave_interval(contract.employee_id.id, interval[0], interval[1])))  # noqa

            # Extract information from previous data.
            # A working interval is considered:
            # - as a leave if a hr.holiday completely covers the period
            # - as a working period instead
            # lunch time
            lunch = timedelta(hours=contract.working_hours.lunch_max)
            for interval, holiday in interval_data:
                holidays |= holiday
                hours = (interval[1] - interval[0] - lunch).total_seconds() / 3600.0  # noqa
                if holiday:
                    # if he was on leave, fill the leaves dict
                    if holiday.holiday_status_id.name in leaves:
                        leaves[holiday.holiday_status_id.name]['number_of_hours'] += hours  # noqa
                    else:
                        leaves[holiday.holiday_status_id.name] = {
                            'name': holiday.holiday_status_id.name,
                            'sequence': 5,
                            'code': holiday.holiday_status_id.name,
                            'number_of_days': 0.0,
                            'number_of_hours': hours,
                            'contract_id': contract.id,
                        }
                else:
                    # add the input vals to tmp (increment if existing)
                    attendances['number_of_hours'] += hours

            # Clean-up the results
            leaves = [value for key, value in leaves.items()]
            for data in [attendances] + leaves:
                data['number_of_days'] = uom_hour._compute_quantity(
                    data['number_of_hours'], uom_day) \
                    if uom_day and uom_hour\
                    else data['number_of_hours'] / 8.0
                res.append(data)
        return res

    @api.multi
    def compute_workdays(self):
        """
        Metodo que calcula los dias/horas trabajadas del mes
        para el empleado.
        Esto aplica con los codigos:
        WORK100: jornada laboral
        WORK125: horas extras al 25%
        WORK150: horas extras al 50%
        WORK200: horas extras al 100%
        """
        for obj in self:
            df, dt = obj.date_from, obj.date_to
            self.total = df - dt

    @api.multi
    def compute_sheet(self):
        self.compute_workdays()
        return super(HrPayslip, self).compute_sheet()

    @api.multi
    def action_payslip_done(self):
        precision = self.env['decimal.precision'].precision_get('Payroll')

        for slip in self:
            line_ids = []
            debit_sum = 0.0
            credit_sum = 0.0
            date = slip.date or slip.date_to

            name = _('Payslip of %s') % (slip.employee_id.name)
            move_dict = {
                'narration': name,
                'ref': slip.number,
                'journal_id': slip.journal_id.id,
                'date': date,
            }
            for line in slip.details_by_salary_rule_category:
                amount = slip.credit_note and -line.total or line.total
                if float_is_zero(amount, precision_digits=precision):
                    continue
                # redeficion para elegir la cuenta
                debit_account_id = line.salary_rule_id.get_account(slip.contract_id, 'debit')  # noqa
                credit_account_id = line.salary_rule_id.get_account(slip.contract_id, 'credit')  # noqa

                if debit_account_id:
                    debit_line = (0, 0, {
                        'name': line.name,
                        'partner_id': line._get_partner_id(credit_account=False),  # noqa
                        'account_id': debit_account_id,
                        'journal_id': slip.journal_id.id,
                        'date': date,
                        'debit': amount > 0.0 and amount or 0.0,
                        'credit': amount < 0.0 and -amount or 0.0,
                        'analytic_account_id': line.salary_rule_id.analytic_account_id.id,  # noqa
                        'tax_line_id': line.salary_rule_id.account_tax_id.id,
                    })
                    line_ids.append(debit_line)
                    debit_sum += debit_line[2]['debit'] - debit_line[2]['credit']  # noqa

                if credit_account_id:
                    credit_line = (0, 0, {
                        'name': line.name,
                        'partner_id': line._get_partner_id(credit_account=True),  # noqa
                        'account_id': credit_account_id,
                        'journal_id': slip.journal_id.id,
                        'date': date,
                        'debit': amount < 0.0 and -amount or 0.0,
                        'credit': amount > 0.0 and amount or 0.0,
                        'analytic_account_id': line.salary_rule_id.analytic_account_id.id,  # noqa
                        'tax_line_id': line.salary_rule_id.account_tax_id.id,
                    })
                    line_ids.append(credit_line)
                    credit_sum += credit_line[2]['credit'] - credit_line[2]['debit']  # noqa

            if float_compare(credit_sum, debit_sum, precision_digits=precision) == -1:  # noqa
                acc_id = slip.journal_id.default_credit_account_id.id
                if not acc_id:
                    raise UserError(_('The Expense Journal "%s" has not properly configured the Credit Account!') % (slip.journal_id.name))  # noqa
                adjust_credit = (0, 0, {
                    'name': _('Adjustment Entry'),
                    'partner_id': False,
                    'account_id': acc_id,
                    'journal_id': slip.journal_id.id,
                    'date': date,
                    'debit': 0.0,
                    'credit': debit_sum - credit_sum,
                })
                line_ids.append(adjust_credit)

            elif float_compare(debit_sum, credit_sum, precision_digits=precision) == -1:  # noqa
                acc_id = slip.journal_id.default_debit_account_id.id
                if not acc_id:
                    raise UserError(_('The Expense Journal "%s" has not properly configured the Debit Account!') % (slip.journal_id.name))  # noqa
                adjust_debit = (0, 0, {
                    'name': _('Adjustment Entry'),
                    'partner_id': False,
                    'account_id': acc_id,
                    'journal_id': slip.journal_id.id,
                    'date': date,
                    'debit': credit_sum - debit_sum,
                    'credit': 0.0,
                })
                line_ids.append(adjust_debit)
            move_dict['line_ids'] = line_ids
            move = self.env['account.move'].create(move_dict)
            slip.write({'move_id': move.id, 'date': date})
            move.post()
        return super(HrPayslip, self).action_payslip_done()


class HrContract(models.Model):
    _inherit = 'hr.contract'

    pay_decimo3 = fields.Boolean('Acumula Décimo Tercero')
    pay_decimo4 = fields.Boolean('Acumula Décimo Cuarto')
    pay_fondo_reserva = fields.Boolean('Acumula Fondo de Reserva')
    pay_asume_iess = fields.Boolean('Asume IESS Empresa')


class ResourceCalendar(models.Model):
    _inherit = 'resource.calendar'

    @api.multi
    def get_working_hours_of_date(self, start_dt=None, end_dt=None,
                                  leaves=None, compute_leaves=False,
                                  resource_id=None,
                                  default_interval=None):
        """ Get the working hours of the day based on calendar. This method uses
        get_working_intervals_of_day to have the work intervals of the day. It
        then calculates the number of hours contained in those intervals. """
        obj = self
        lunch_time = timedelta(hours=obj.lunch_max)
        res = timedelta()
        intervals = self.get_working_intervals_of_day(
            start_dt, end_dt, leaves,
            compute_leaves, resource_id,
            default_interval)
        for interval in intervals:
            res += interval[1] - interval[0] - lunch_time
        return seconds(res) / 3600.0


class HrPayrollAccount(models.Model):
    _name = 'hr.rule.account'

    rule_id = fields.Many2one(
        'hr.payroll.rule',
        'Regla'
    )
    account_debit_id = fields.Many2one(
        'account.account',
        'Cuenta Debito',
        required=True
    )
    account_credit_id = fields.Many2one(
        'account.account',
        'Cuenta Credito',
        required=True
    )
    department_id = fields.Many2one(
        'hr.department',
        'Departamento',
        required=True
    )


class HrPayrollRule(models.Model):

    _inherit = 'hr.salary.rule'

    account_ids = fields.One2many(
        'hr.rule.account',
        'rule_id',
        'Cuentas'
    )
