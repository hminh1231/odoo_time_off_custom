# -*- coding: utf-8 -*-

from odoo import api, fields, models


class HrLeave(models.Model):
    _inherit = "hr.leave"

    employee_id_hrm = fields.Char(
        string="ID HRM",
        compute="_compute_employee_hrm_display",
        readonly=True,
    )
    employee_ma_bo_phan = fields.Char(
        string="Mã bộ phận",
        compute="_compute_employee_hrm_display",
        readonly=True,
    )

    @api.depends("employee_id")
    def _compute_employee_hrm_display(self):
        for leave in self:
            employee = leave.employee_id.sudo()
            id_hrm = (getattr(employee, "id_hrm", None) or "").strip()
            leave.employee_id_hrm = f"ID {id_hrm}" if id_hrm else ""
            leave.employee_ma_bo_phan = (getattr(employee, "ma_bo_phan", None) or "").strip()
