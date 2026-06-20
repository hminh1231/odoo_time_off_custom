# -*- coding: utf-8 -*-

from odoo import api, fields, models
from odoo.exceptions import ValidationError

from .lug_constants import LUG_PERMISSION_FIELDS


class LugPermissionLineMixin(models.AbstractModel):
    _name = "lug.permission.line.mixin"
    _description = "LUG Permission Line Mixin"

    app_id = fields.Many2one("lug.app", required=True, ondelete="cascade", index=True)
    perm_view = fields.Boolean(string="Xem", default=False)
    perm_create = fields.Boolean(string="Thêm", default=False)
    perm_edit = fields.Boolean(string="Sửa", default=False)
    perm_delete = fields.Boolean(string="Xóa", default=False)
    perm_approve = fields.Boolean(string="Duyệt", default=False)
    perm_export = fields.Boolean(string="Xuất", default=False)
    perm_import = fields.Boolean(string="Nhập", default=False)
    perm_print = fields.Boolean(string="In", default=False)

    def _active_permission_codes(self):
        self.ensure_one()
        return {
            code
            for field_name, code in LUG_PERMISSION_FIELDS
            if self[field_name]
        }


class LugGroupPermission(models.Model):
    _name = "lug.group.permission"
    _description = "LUG Group Application Permission"
    _inherit = "lug.permission.line.mixin"
    _order = "app_id"

    group_id = fields.Many2one(
        "lug.group",
        required=True,
        ondelete="cascade",
        index=True,
    )

    _group_app_unique = models.Constraint(
        "unique(group_id, app_id)",
        "Each application can only appear once per group.",
    )

    @api.constrains(
        "perm_view",
        "perm_create",
        "perm_edit",
        "perm_delete",
        "perm_approve",
        "perm_export",
        "perm_import",
        "perm_print",
    )
    def _check_view_required_for_actions(self):
        for line in self:
            if line.perm_view:
                continue
            if any(
                line[field_name]
                for field_name, _code in LUG_PERMISSION_FIELDS
                if field_name != "perm_view"
            ):
                raise ValidationError(
                    self.env._(
                        "Application '%(app)s': enable View before granting other actions.",
                        app=line.app_id.display_name,
                    )
                )
