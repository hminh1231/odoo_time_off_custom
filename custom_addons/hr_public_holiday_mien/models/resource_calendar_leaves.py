# -*- coding: utf-8 -*-

from odoo import api, fields, models
from odoo.fields import Domain

HOLIDAY_SCOPE_VP = "vp"
HOLIDAY_SCOPE_CH = "ch"


class ResourceCalendarLeaves(models.Model):
    _inherit = "resource.calendar.leaves"

    holiday_scope = fields.Selection(
        [
            (HOLIDAY_SCOPE_VP, "Văn Phòng"),
            (HOLIDAY_SCOPE_CH, "Cửa Hàng"),
        ],
        string="Phạm vi ngày lễ",
        required=True,
        default=HOLIDAY_SCOPE_VP,
        index=True,
    )

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if "holiday_scope" in fields_list and "holiday_scope" not in res:
            res["holiday_scope"] = self.env.context.get(
                "default_holiday_scope", HOLIDAY_SCOPE_VP
            )
        return res

    @api.model
    def _search(self, domain, offset=0, limit=None, order=None, **kwargs):
        domain = Domain(domain)
        if not self.env.user.has_group("hr_holidays.group_hr_holidays_manager"):
            scope = self.env["hr.employee"]._public_holiday_scope_for_current_user()
            if scope:
                domain &= Domain("holiday_scope", "=", scope)
        return super()._search(
            domain,
            offset=offset,
            limit=limit,
            order=order,
            **kwargs,
        )
