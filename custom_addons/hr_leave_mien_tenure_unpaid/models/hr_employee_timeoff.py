# -*- coding: utf-8 -*-

from odoo import api, fields, models

_APPOINTMENT_MONTHLY_LEAVE_REQUIRED_DAY = 1
_QUALIFICATION_TRIGGER_FIELDS = frozenset({
    "ngay_bo_nhiem",
    "ngay_vao_lam",
    "job_id",
    "job_title",
    "mien",
    "ma_bo_phan_id",
})
_SKIP_DEPARTURE_MONTHLY_LEAVE_CUTOFF_CTX = "skip_departure_monthly_leave_cutoff"
_SKIP_DEPARTURE_MONTHLY_LEAVE_REVERSAL_CTX = "skip_departure_monthly_leave_reversal"
_MONTHLY_LEAVE_BONUS_DATE_CTX = "monthly_leave_bonus_date"


class HrEmployeeTenureMonthlyLeave(models.Model):
    _inherit = "hr.employee"

    def _monthly_leave_bonus_sync_context(self, bonus_date=None):
        bonus_date = bonus_date or self._monthly_leave_bonus_date()
        return {
            _MONTHLY_LEAVE_BONUS_DATE_CTX: bonus_date,
            _SKIP_DEPARTURE_MONTHLY_LEAVE_CUTOFF_CTX: True,
            _SKIP_DEPARTURE_MONTHLY_LEAVE_REVERSAL_CTX: True,
        }

    def _blocks_appointment_monthly_leave_bonus(self, bonus_date):
        """Skip bonus when appointment is missing or not on day 1 of the month."""
        self.ensure_one()
        appointment_date = self.sudo().ngay_bo_nhiem
        if not appointment_date:
            return True
        return appointment_date.day != _APPOINTMENT_MONTHLY_LEAVE_REQUIRED_DAY

    def _blocks_monthly_leave_bonus(self, bonus_date):
        self.ensure_one()
        if super()._blocks_monthly_leave_bonus(bonus_date):
            return True
        return self._blocks_appointment_monthly_leave_bonus(bonus_date)

    def _monthly_leave_bonus_eligible(self, bonus_date=None):
        self.ensure_one()
        bonus_date = bonus_date or self._monthly_leave_bonus_date()
        if not self._mien_monthly_leave_bonus_applies():
            return False
        if self._is_tenure_unpaid_job_position() and not self._mien_tenure_has_four_years(
            reference_date=bonus_date
        ):
            return False
        if self._blocks_monthly_leave_bonus(bonus_date):
            return False
        return True

    def _apply_monthly_leave_bonus(self, bonus_date=None):
        """Add +1 for the bonus month when not already granted this month."""
        bonus_date = bonus_date or self._monthly_leave_bonus_date()
        bonus_month = bonus_date.replace(day=1)
        to_apply = self.filtered(
            lambda employee: employee.last_monthly_leave_bonus_date != bonus_month
        )
        return super(HrEmployeeTenureMonthlyLeave, to_apply)._apply_monthly_leave_bonus(
            bonus_date
        )

    def _reverse_qualification_monthly_leave_bonus(self, bonus_date=None):
        """Remove the current month's auto +1 when qualification no longer matches."""
        bonus_date = bonus_date or self._monthly_leave_bonus_date()
        bonus_month = bonus_date.replace(day=1)
        for employee in self:
            if employee.last_monthly_leave_bonus_date != bonus_month:
                continue
            employee.with_context(
                **employee._monthly_leave_bonus_sync_context(bonus_date)
            ).write(
                {
                    "tong_so_phep": max(0.0, (employee.tong_so_phep or 0.0) - 1.0),
                    "last_monthly_leave_bonus_date": False,
                }
            )

    def _sync_monthly_leave_bonus(self):
        """Keep current-month auto +1 in sync when qualification fields are corrected."""
        bonus_date = self._monthly_leave_bonus_date()
        bonus_month = bonus_date.replace(day=1)
        for employee in self:
            if employee._monthly_leave_bonus_eligible(bonus_date):
                if employee.last_monthly_leave_bonus_date != bonus_month:
                    employee._apply_monthly_leave_bonus(bonus_date)
            elif employee.last_monthly_leave_bonus_date == bonus_month:
                employee._reverse_qualification_monthly_leave_bonus(bonus_date)

    @api.model_create_multi
    def create(self, vals_list):
        employees = super().create(vals_list)
        employees._sync_monthly_leave_bonus()
        return employees

    def write(self, vals):
        res = super().write(vals)
        if _QUALIFICATION_TRIGGER_FIELDS & set(vals):
            self._sync_monthly_leave_bonus()
        return res

    @api.model
    def cron_apply_monthly_leave_bonus(self):
        """Monthly accrual: +1 ``tong_so_phep`` for eligible employees (Bắc/Nam/ĐTT)."""
        today = fields.Date.context_today(self)
        bonus_date = today.replace(day=1)
        employees = self.sudo().search([("active", "=", True)])
        eligible = employees.filtered(
            lambda employee: employee._monthly_leave_bonus_eligible(today)
        )
        if eligible:
            eligible._apply_monthly_leave_bonus(bonus_date)
