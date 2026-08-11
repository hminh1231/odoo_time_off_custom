# -*- coding: utf-8 -*-

from odoo import api, fields, models

from .lug_constants import LUG_PERMISSION_FIELDS


class LugGroup(models.Model):
    _name = "lug.group"
    _description = "LUG Permission Group"
    _order = "name"

    name = fields.Char(required=True, translate=True)
    code = fields.Char(index=True)
    active = fields.Boolean(default=True)
    description = fields.Text()
    user_ids = fields.Many2many(
        "res.users",
        "lug_user_groups",
        "group_id",
        "user_id",
        string="Users",
    )
    permission_line_ids = fields.One2many(
        "lug.group.permission",
        "group_id",
        string="Application Permissions",
    )
    user_count = fields.Integer(compute="_compute_user_count")


    @api.depends("user_ids")
    def _compute_user_count(self):
        for group in self:
            group.user_count = len(group.user_ids)

    def action_open_users(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": self.name,
            "res_model": "res.users",
            "view_mode": "list,form",
            "domain": [("id", "in", self.user_ids.ids)],
        }

    def write(self, vals):
        res = super().write(vals)
        if {"permission_line_ids", "user_ids"} & set(vals):
            users = self.mapped("user_ids")
            users._sync_lug_odoo_groups()
            users._sync_lug_visibility_policy()
            self.env["res.users"]._lug_clear_menu_cache_global(self.env)
        return res

    @api.model
    def _migration_export_field_paths(self):
        """Import-compatible field paths for Groups 'Export All'."""
        perm_fields = [name for name, _code in LUG_PERMISSION_FIELDS]
        return [
            "name",
            "code",
            "active",
            "description",
            # Prefer login for cross-DB user matching
            "user_ids/login",
            # Permission lines
            "permission_line_ids/id",
            # Prefer app code (stable across DBs) over xml id
            "permission_line_ids/app_id/code",
            *[f"permission_line_ids/{name}" for name in perm_fields],
        ]

    @api.model
    def get_migration_export_fields(self):
        """Field descriptors for full lug.group export (import-compatible)."""
        paths = self._migration_export_field_paths()
        fields_info = self.fields_get(
            ["name", "code", "active", "description", "user_ids", "permission_line_ids"],
            attributes=["type", "string", "store"],
        )
        line_info = self.env["lug.group.permission"].fields_get(
            ["app_id"] + [name for name, _code in LUG_PERMISSION_FIELDS],
            attributes=["type", "string", "store"],
        )
        app_info = self.env["lug.app"].fields_get(
            ["code"],
            attributes=["type", "string", "store"],
        )

        result = []
        for path in paths:
            parts = path.split("/")
            root = parts[0]
            if root not in fields_info:
                continue
            root_meta = fields_info[root]

            if len(parts) == 1:
                label = root_meta["string"]
                ftype = root_meta["type"]
                store = root_meta.get("store", True)
            elif root == "user_ids" and len(parts) == 2:
                label = f"{root_meta['string']} / Login"
                ftype = "many2many"
                store = True
            elif root == "permission_line_ids":
                if parts[1] == "id" and len(parts) == 2:
                    label = f"{root_meta['string']} / External ID"
                    ftype = "one2many"
                    store = True
                elif parts[1] == "app_id":
                    app_meta = app_info.get("code", line_info.get("app_id", {}))
                    label = (
                        f"{root_meta['string']} / "
                        f"{line_info.get('app_id', {}).get('string', 'App')} / "
                        f"{app_meta.get('string', 'Code')}"
                    )
                    ftype = "many2one"
                    store = True
                else:
                    sub = line_info.get(parts[1], {})
                    label = f"{root_meta['string']} / {sub.get('string', parts[1])}"
                    ftype = sub.get("type", "boolean")
                    store = sub.get("store", True)
            else:
                continue

            result.append(
                {
                    "name": path,
                    "label": label,
                    "type": ftype,
                    "store": bool(store),
                }
            )
        return result

