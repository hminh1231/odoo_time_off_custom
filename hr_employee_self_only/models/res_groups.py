# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, models, tools


class ResGroups(models.Model):
    _inherit = "res.groups"

    @api.model
    @tools.ormcache("self.env.lang", cache="groups")
    def _get_view_group_hierarchy(self):
        """Expose Employees / No group id for backend JS reordering of the privilege dropdown."""
        base = super()._get_view_group_hierarchy()
        no = self.env.ref("hr_employee_self_only.group_hr_employees_no", raise_if_not_found=False)
        if not no:
            return base
        return {
            **base,
            "hr_employee_self_only": {"employees_no_group_id": no.id},
        }
