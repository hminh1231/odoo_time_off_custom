# -*- coding: utf-8 -*-

from odoo import api, fields, models


class LugApp(models.Model):
    _name = "lug.app"
    _description = "LUG Application"
    _order = "sequence, name"

    name = fields.Char(required=True, translate=True)
    code = fields.Char(
        required=True,
        index=True,
        help="Technical code, e.g. attendance, expense, gatepass.",
    )
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    module_name = fields.Char(
        string="Odoo Module",
        help="Optional. When set, the app is only available if this module is installed.",
    )
    menu_xmlid = fields.Char(
        string="Root Menu XML ID",
        help="External ID of the root menu to hide when the user lacks View permission.",
    )
    extra_menu_xmlids = fields.Text(
        string="Extra Menu XML IDs",
        help="Comma-separated external IDs of additional menus tied to this application.",
    )
    description = fields.Text()

    _code_unique = models.Constraint(
        "unique(code)",
        "Application code must be unique.",
    )

    @api.model
    def _get_installed_module_names(self):
        return set(
            self.env["ir.module.module"]
            .sudo()
            .search([("state", "=", "installed")])
            .mapped("name")
        )

    def _is_module_available(self, installed=None):
        self.ensure_one()
        if not self.module_name:
            return True
        installed = installed if installed is not None else self._get_installed_module_names()
        return self.module_name in installed

    def _menu_xmlid_list(self):
        self.ensure_one()
        xmlids = []
        if self.menu_xmlid:
            xmlids.append(self.menu_xmlid.strip())
        if self.extra_menu_xmlids:
            xmlids.extend(
                part.strip()
                for part in self.extra_menu_xmlids.split(",")
                if part.strip()
            )
        return xmlids

    def _resolve_menu_ids(self):
        menu_ids = []
        for xmlid in self._menu_xmlid_list():
            menu = self.env.ref(xmlid, raise_if_not_found=False)
            if menu:
                menu_ids.append(menu.id)
        return menu_ids
