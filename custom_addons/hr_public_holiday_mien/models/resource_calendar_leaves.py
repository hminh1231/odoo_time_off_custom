# -*- coding: utf-8 -*-

from odoo import api, fields, models
from odoo.exceptions import ValidationError
from odoo.fields import Domain
from odoo.tools.translate import _

HOLIDAY_SCOPE_VP = "vp"
HOLIDAY_SCOPE_CH = "ch"
# Skip ir.rule-like scope injection when resolving holidays for an employee record.
SKIP_HOLIDAY_SCOPE_SEARCH_CTX = "hr_public_holiday_mien_skip_scope_search"


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
        if (
            not self.env.context.get(SKIP_HOLIDAY_SCOPE_SEARCH_CTX)
            and not self.env.user.has_group("hr_holidays.group_hr_holidays_manager")
        ):
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

    @api.model
    def _ensure_public_holiday_scope_vals(self, vals):
        """Inline list rows on the CH tab may omit holiday_scope and default to VP."""
        vals = dict(vals)
        if vals.get("resource_id"):
            return vals
        scope = self.env.context.get("default_holiday_scope")
        if scope:
            vals.setdefault("holiday_scope", scope)
        return vals

    @api.model_create_multi
    def create(self, vals_list):
        vals_list = [self._ensure_public_holiday_scope_vals(vals) for vals in vals_list]
        return super().create(vals_list)

    @api.constrains("date_from", "date_to", "calendar_id")
    def _check_compare_dates(self):
        """Allow VP and CH holidays on the same dates; only block overlap within one scope."""
        if not self:
            return
        all_existing_leaves = self.env["resource.calendar.leaves"].search(
            [
                ("resource_id", "=", False),
                ("company_id", "in", self.company_id.ids),
                ("date_from", "<=", max(self.mapped("date_to"))),
                ("date_to", ">=", min(self.mapped("date_from"))),
            ]
        )
        for record in self:
            if record.resource_id:
                continue
            existing_leaves = all_existing_leaves.filtered(
                lambda leave: (
                    record.id != leave.id
                    and record.company_id == leave.company_id
                    and record.date_from <= leave.date_to
                    and record.date_to >= leave.date_from
                    and leave.holiday_scope == record.holiday_scope
                )
            )
            if record.calendar_id:
                existing_leaves = existing_leaves.filtered(
                    lambda leave: not leave.calendar_id
                    or leave.calendar_id == record.calendar_id
                )
            if existing_leaves:
                raise ValidationError(
                    _(
                        "Hai ngày nghỉ lễ không thể trùng nhau trong cùng một "
                        "phạm vi (Văn Phòng / Cửa Hàng) và giờ làm việc."
                    )
                )
