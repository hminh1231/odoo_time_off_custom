# -*- coding: utf-8 -*-

from odoo import models


class IrUiMenu(models.Model):
    _inherit = "ir.ui.menu"

    def _load_menus_blacklist(self):
        res = super()._load_menus_blacklist()
        user = self.env.user
        hidden = list(res)
        hidden.extend(user._lug_hidden_discuss_config_menu_ids())
        if user._lug_permission_is_enforced():
            hidden.extend(user._lug_hidden_menu_ids())
        return hidden
