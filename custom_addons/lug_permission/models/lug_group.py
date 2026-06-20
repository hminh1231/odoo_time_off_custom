# -*- coding: utf-8 -*-

from odoo import api, fields, models


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

    def _permission_codes_for_app(self, app):
        self.ensure_one()
        line = self.permission_line_ids.filtered(lambda l: l.app_id == app)[:1]
        return line._active_permission_codes() if line else set()
