# -*- coding: utf-8 -*-

from collections import defaultdict

from odoo import api, fields, models

from .lug_constants import LUG_DATA_SCOPES


class ResUsers(models.Model):
    _inherit = "res.users"

    lug_group_ids = fields.Many2many(
        "lug.group",
        "lug_user_groups",
        "user_id",
        "group_id",
        string="Nhóm quyền LUG",
    )
    lug_data_scope = fields.Selection(
        selection=LUG_DATA_SCOPES,
        string="Phạm vi dữ liệu LUG",
        default="self",
        help="Giới hạn phạm vi dữ liệu theo mô hình LUG Permission Center.",
    )
    lug_user_permission_ids = fields.One2many(
        "lug.user.permission",
        "user_id",
        string="Quyền bổ sung riêng",
    )
    lug_permission_enforced = fields.Boolean(
        compute="_compute_lug_permission_enforced",
        string="Áp dụng LUG Permission",
    )

    @api.depends("lug_group_ids", "lug_user_permission_ids")
    def _compute_lug_permission_enforced(self):
        for user in self:
            user.lug_permission_enforced = bool(
                user.lug_group_ids
                or user.lug_user_permission_ids.filtered(
                    lambda line: line._active_permission_codes()
                )
            )

    def _lug_permission_bypass(self):
        self.ensure_one()
        return self.has_group("base.group_system")

    def _lug_permission_is_enforced(self):
        self.ensure_one()
        if self._lug_permission_bypass():
            return False
        return bool(
            self.lug_group_ids
            or self.lug_user_permission_ids.filtered(
                lambda line: line._active_permission_codes()
            )
        )

    def _lug_effective_permission_map(self):
        """Return {app_code: set(permission_code)} for the current user."""
        self.ensure_one()
        result = defaultdict(set)
        for group in self.lug_group_ids:
            for line in group.permission_line_ids:
                if not line.app_id.code:
                    continue
                result[line.app_id.code].update(line._active_permission_codes())
        for line in self.lug_user_permission_ids:
            if not line.app_id.code:
                continue
            result[line.app_id.code].update(line._active_permission_codes())
        return result

    def has_lug_permission(self, app_code, permission_code="view"):
        """Check effective LUG permission for an application action."""
        self.ensure_one()
        if not self._lug_permission_is_enforced():
            return True
        permission_map = self._lug_effective_permission_map()
        return permission_code in permission_map.get(app_code, set())

    def get_lug_data_scope(self):
        self.ensure_one()
        return self.lug_data_scope or "self"

    def _lug_hidden_menu_ids(self):
        user = self.env.user
        if not user._lug_permission_is_enforced():
            return []
        installed = self.env["lug.app"]._get_installed_module_names()
        permission_map = user._lug_effective_permission_map()
        hidden = []
        for app in self.env["lug.app"].sudo().search([("active", "=", True)]):
            if not app._is_module_available(installed):
                continue
            if "view" not in permission_map.get(app.code, set()):
                hidden.extend(app._resolve_menu_ids())
        return hidden

    def write(self, vals):
        res = super().write(vals)
        cache_keys = {"lug_group_ids", "lug_user_permission_ids", "lug_data_scope"}
        if cache_keys & set(vals):
            self.env.registry.clear_cache()
        return res

    @api.model_create_multi
    def create(self, vals_list):
        users = super().create(vals_list)
        if any(
            {"lug_group_ids", "lug_user_permission_ids", "lug_data_scope"} & set(vals)
            for vals in vals_list
        ):
            self.env.registry.clear_cache()
        return users
