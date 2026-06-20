# -*- coding: utf-8 -*-

from odoo import models


class IrUiMenu(models.Model):
    _inherit = "ir.ui.menu"

    def _load_menus_blacklist(self):
        res = super()._load_menus_blacklist()
        hidden_menu_ids = self.env.user._lug_hidden_menu_ids()
        return res + hidden_menu_ids
