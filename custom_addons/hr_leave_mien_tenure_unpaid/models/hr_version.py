# -*- coding: utf-8 -*-

from odoo import api, models

_VERSION_QUALIFICATION_FIELDS = frozenset({
    "job_title",
    "job_id",
})


class HrVersionMonthlyLeave(models.Model):
    _inherit = "hr.version"

    def _employees_for_monthly_leave_bonus_sync(self):
        return self.mapped("employee_id").filtered("id")

    @api.model_create_multi
    def create(self, vals_list):
        versions = super().create(vals_list)
        versions._employees_for_monthly_leave_bonus_sync()._sync_monthly_leave_bonus()
        return versions

    def write(self, vals):
        res = super().write(vals)
        if _VERSION_QUALIFICATION_FIELDS & set(vals):
            self._employees_for_monthly_leave_bonus_sync()._sync_monthly_leave_bonus()
        return res
