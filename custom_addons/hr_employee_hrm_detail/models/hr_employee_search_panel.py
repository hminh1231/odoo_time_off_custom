# -*- coding: utf-8 -*-
from lxml import etree

from odoo import api, models


def _strip_inaccessible_searchpanel_fields(recordset, result):
    """Drop searchpanel nodes when the field is absent from the live registry."""
    search = result.get("views", {}).get("search")
    if not search or not search.get("arch"):
        return
    arch = search["arch"]
    root = etree.fromstring(arch.encode() if isinstance(arch, str) else arch)
    model_fields = recordset._fields
    changed = False
    for node in root.xpath("//searchpanel/field[@name]"):
        if node.get("name") not in model_fields:
            parent = node.getparent()
            if parent is not None:
                parent.remove(node)
                changed = True
    for node in root.xpath("//filter[@name='group_mien_zone']"):
        if "mien_zone_id" not in model_fields:
            parent = node.getparent()
            if parent is not None:
                parent.remove(node)
                changed = True
    if changed:
        search["arch"] = etree.tostring(root, encoding="unicode")


class HrEmployeeSearchPanel(models.Model):
    _inherit = "hr.employee"

    @api.model
    def get_views(self, views, options=None):
        result = super().get_views(views, options)
        _strip_inaccessible_searchpanel_fields(self, result)
        return result

    @api.model
    def search_panel_select_range(self, field_name, **kwargs):
        if field_name not in self._fields:
            return {"parent_field": False, "values": []}
        return super().search_panel_select_range(field_name, **kwargs)


class HrEmployeePublicSearchPanel(models.Model):
    _inherit = "hr.employee.public"

    @api.model
    def get_views(self, views, options=None):
        result = super().get_views(views, options)
        _strip_inaccessible_searchpanel_fields(self, result)
        return result

    @api.model
    def search_panel_select_range(self, field_name, **kwargs):
        if field_name not in self._fields:
            return {"parent_field": False, "values": []}
        return super().search_panel_select_range(field_name, **kwargs)
