# -*- coding: utf-8 -*-
from datetime import timedelta

from odoo import api, models
from odoo.exceptions import ValidationError
from odoo.tools.translate import _

from .hr_employee import MODE_BLOCK, VP_DEPARTMENT_CODE


class HrLeave(models.Model):
    _inherit = "hr.leave"

    def _vp_sunday_block_applies(self):
        self.ensure_one()
        if not self.employee_id or self.employee_id.ma_bo_phan != VP_DEPARTMENT_CODE:
            return False
        return self.env["hr.employee"]._vp_sunday_mode() == MODE_BLOCK

    @staticmethod
    def _range_includes_sunday(date_from, date_to):
        if not date_from or not date_to:
            return False
        current = date_from
        while current <= date_to:
            if current.weekday() == 6:
                return True
            current += timedelta(days=1)
        return False

    @api.constrains("request_date_from", "request_date_to", "employee_id")
    def _check_vp_sunday_not_allowed(self):
        for leave in self.filtered(
            lambda l: l.request_date_from and l.request_date_to
        ):
            if not leave._vp_sunday_block_applies():
                continue
            if leave._range_includes_sunday(
                leave.request_date_from, leave.request_date_to
            ):
                raise ValidationError(
                    _(
                        "Nhân viên bộ phận VP không được đăng ký nghỉ phép vào ngày Chủ nhật."
                    )
                )

    @api.onchange("request_date_from", "request_date_to", "employee_id")
    def _onchange_vp_sunday_block(self):
        if not self._vp_sunday_block_applies():
            return
        if self.request_date_from and self.request_date_to and self._range_includes_sunday(
            self.request_date_from, self.request_date_to
        ):
            return {
                "warning": {
                    "title": _("Chủ nhật không được phép"),
                    "message": _(
                        "Nhân viên bộ phận VP không được chọn ngày Chủ nhật trong khoảng nghỉ phép."
                    ),
                }
            }
