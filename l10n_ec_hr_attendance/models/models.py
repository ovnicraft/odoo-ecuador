# -*- coding: utf-8 -*-
# © 2015 Michael Cristian Salamea <cristian.salamea@ayni.com.ec>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import sqlite3
from datetime import timedelta

from odoo import api, fields, models


class HrAttendance(models.Model):
    _inherit = 'hr.attendance'

    no_valid = fields.Boolean('Inconsistente')


class ResourceCalendar(models.Model):
    _inherit = 'resource.calendar'

    lunch_from = fields.Float('Salida Almuerzo')
    lunch_to = fields.Float('Entrada Almuerzo')
    lunch_max = fields.Float('Límite para Almuerzo (h)')
    tolerance_in = fields.Integer('Tolerancia en ingreso (min)', default=5)
    tolerance_out = fields.Integer('Tolerancia en salida (min)', default=15)
    exception_ids = fields.One2many(
        'hr.calendar.exception',
        'calendar_id',
        string='Excepciones'
    )


class HrCalendarException(models.Model):
    _name = 'hr.calendar.exception'
    _order = 'date ASC'

    name = fields.Char('Motivo', size=64, required=True)
    date = fields.Date('Fecha que aplica', required=True)
    hour_from = fields.Float('Trabajar desde')
    hour_to = fields.Float('Trabajar hasta')
    state = fields.Selection(
        [
            ('draft', 'Borrador'),
            ('confirm', 'Confirmado')
        ],
        required=True,
        string='Estado',
        readonly=True
    )
    calendar_id = fields.Many2one('resource.calendar', 'Calendario')

    @api.multi
    def action_confirm(self):
        self.write({'state': 'confirm'})
        return True


class HrCheckInOut(models.TransientModel):
    _name = 'hr.register.inout'

    path = fields.Char(
        'Path de DB',
        required=True,
        default='/var/tmp/*.sqlite'
    )
    state = fields.Selection(
        [('draft', 'Importar'), ('done', 'Realizado')],
        string='Estado',
        default='draft',
        required=True
    )
    file_errors = fields.Binary('Errores')
    date_start = fields.Date('Desde', required=True)
    date_end = fields.Date('Hasta', required=True)
    calendar_ids = fields.Many2many(
        'resource.calendar',
        string='Horarios'
    )

    @api.multi
    def create_engine(self):
        con = sqlite3.connect(self.path)
        cur = con.cursor()
        return cur

    def fix_date(self, fecha):
        f = fields.Datetime.from_string(fecha)
        f = f + timedelta(hours=5)
        return fields.Datetime.to_string(f)

    @api.multi
    def action_register(self):

        class Check(object):
            def __init__(self, cedula=False, checkin=False, check_type=False):
                self.cedula = cedula
                self.checkin = checkin
                self.check_type = check_type

            def __repr__(self):
                return '<Check cedula={0}, date={1}, check_type={2}>'.format(self.cedula, self.checkin, self.check_type)  # noqa

            def __str__(self):
                return '<Check cedula={0}, date={1}, check_type={2}>'.format(self.cedula, self.checkin, self.check_type)  # noqa

            def __eq__(self, other):
                # new + delta == last
                DELTA = 5
                if self.cedula == other.cedula:
                    if self.to_date(DELTA) >= other.to_date():
                        return True
                return False

            def to_date(self, delta=0):
                return fields.Datetime.from_string(self.checkin) + timedelta(minutes=delta)  # noqa

            def to_cols(self):
                return [self.cedula, self.checkin, self.check_type]

        delta = 2
        empl = self.env['hr.employee']
        atten = self.env['hr.attendance']
        # TODO: revisar que rango controlar
        cur = self.create_engine()
        SQL_CHECKIN = """
        SELECT us.SSN, datetime("20"||substr(io.CHECKTIME, 7, 2)||"-"||substr(io.CHECKTIME, 1, 2)||"-"||SUBSTR(io.CHECKTIME, 4, 2)||" "||substr(io.CHECKTIME, 10, 8)) as fecha,
        io.CHECKTYPE, io.SENSORID
        FROM userinfo us INNER JOIN checkinout io ON us.userid = io.userid
        WHERE fecha >= datetime("%s", '-%s hours')
        AND fecha < datetime("%s", '+%s hours')
        ORDER BY io.CHECKTIME;
        """ % (self.date_start, delta, self.date_start, 0)
        rows_in = cur.execute(SQL_CHECKIN).fetchall()
        SQL = """
        SELECT us.SSN, datetime("20"||substr(io.CHECKTIME, 7, 2)||"-"||substr(io.CHECKTIME, 1, 2)||"-"||SUBSTR(io.CHECKTIME, 4, 2)||" "||substr(io.CHECKTIME, 10, 8)) as fecha,
        io.CHECKTYPE, io.SENSORID
        FROM userinfo us INNER JOIN checkinout io ON us.userid = io.userid
        WHERE fecha >= datetime("%s", '+%s hours')
        AND fecha < datetime("%s", '+%s hours')
        ORDER BY io.CHECKTIME;
        """ % (self.date_start, delta, self.date_end, delta)
        print SQL
        rows = cur.execute(SQL).fetchall()
        cur.close()
        rows = rows_in + rows
        errores = []
        for cedula, fecha, checktype, sensorid in rows:
            new_check = Check(cedula, fecha, checktype)
            employee = empl.search([('identification_id', '=', cedula)], limit=1)  # noqa
            if not employee.exists():
                errores.append(new_check)
                continue

            if checktype == 'I' and employee.attendance_state != 'checked_in':
                atten.create({
                    'employee_id': employee.id,
                    'check_in': self.fix_date(fecha)
                })
                del new_check
            else:
                if checktype == 'I':
                    continue
                attendance = atten.search([
                    ('employee_id', '=', employee.id),
                    ('no_valid', '=', False),
                    ('check_out', '=', False)], limit=1)
                if attendance and checktype == 'O':
                    attendance.check_out = self.fix_date(fecha)
                else:
                    errores.append(new_check.to_cols())
#                    raise UserError(_('Cannot perform check out on %(ident)s %(empl_name)s, could not find corresponding check in. '  # noqa
#                                      'Your attendances have probably been modified manually by human resources.') % {'empl_name': employee.name,  # noqa
#                                                                                                                      'ident': employee.identification_id})  # noqa
        self.write({'state': 'done'})
        return True
