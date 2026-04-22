# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, models

from .hr_employee_privacy import _privacy_raise_if_hr_version_no_write


class HrVersion(models.Model):
    _inherit = "hr.version"

    @api.model_create_multi
    def create(self, vals_list):
        _privacy_raise_if_hr_version_no_write(self.env)
        return super().create(vals_list)

    def write(self, vals):
        _privacy_raise_if_hr_version_no_write(self.env)
        return super().write(vals)

    def unlink(self):
        _privacy_raise_if_hr_version_no_write(self.env)
        return super().unlink()

    def message_post(self, **kwargs):
        _privacy_raise_if_hr_version_no_write(self.env)
        return super().message_post(**kwargs)
