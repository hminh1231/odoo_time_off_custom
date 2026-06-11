# -*- coding: utf-8 -*-

from odoo import api, fields, models

_APPOINTMENT_MONTHLY_LEAVE_CUTOFF_DAY = 15
_QUALIFICATION_TRIGGER_FIELDS = frozenset({
    "ngay_bo_nhiem",
    "ngay_vao_lam",
    "job_id",
    "job_title",
    "mien",
    "ma_bo_phan_id",
})


class HrEmployeeTenureMonthlyLeave(models.Model):
    _inherit = "hr.employee"

    def _blocks_appointment_monthly_leave_bonus(self, bonus_date):
        """Skip bonus when appointment is missing or on/after day 15."""
        self.ensure_one()
        appointment_date = self.sudo().ngay_bo_nhiem
        if not appointment_date:
            return True
        return appointment_date.day >= _APPOINTMENT_MONTHLY_LEAVE_CUTOFF_DAY

    def _blocks_monthly_leave_bonus(self, bonus_date):
        self.ensure_one()
        if super()._blocks_monthly_leave_bonus(bonus_date):
            return True
        return self._blocks_appointment_monthly_leave_bonus(bonus_date)

    def _monthly_leave_bonus_eligible(self, bonus_date=None):
        self.ensure_one()
        bonus_date = bonus_date or self._monthly_leave_bonus_date()
        if not self._mien_tenure_unpaid_applies():
            return False
        if not self._mien_tenure_has_four_years(reference_date=bonus_date):
            return False
        if self._blocks_monthly_leave_bonus(bonus_date):
            return False
        return True

    def _apply_monthly_leave_bonus_if_newly_eligible(self, before_eligible=None):
        for employee in self:
            was_eligible = (
                before_eligible.get(employee.id)
                if before_eligible is not None
                else False
            )
            if not was_eligible and employee._monthly_leave_bonus_eligible():
                employee._apply_monthly_leave_bonus()

    @api.model_create_multi
    def create(self, vals_list):
        employees = super().create(vals_list)
        employees._apply_monthly_leave_bonus_if_newly_eligible(before_eligible={})
        return employees

    def write(self, vals):
        qualification_before = {}
        if _QUALIFICATION_TRIGGER_FIELDS & set(vals):
            for employee in self:
                qualification_before[employee.id] = (
                    employee._monthly_leave_bonus_eligible()
                )
        res = super().write(vals)
        if _QUALIFICATION_TRIGGER_FIELDS & set(vals):
            self._apply_monthly_leave_bonus_if_newly_eligible(qualification_before)
        return res

    @api.model
    def cron_apply_monthly_leave_bonus(self):
        """Monthly accrual: +1 ``tong_so_phep`` for eligible Nhóm trưởng (Bắc/Nam/ĐTT)."""
        today = fields.Date.context_today(self)
        bonus_date = today.replace(day=1)
        employees = self.sudo().search([("active", "=", True)])
        eligible = employees.filtered(
            lambda employee: employee._monthly_leave_bonus_eligible(today)
        )
        if eligible:
            eligible._apply_monthly_leave_bonus(bonus_date)
