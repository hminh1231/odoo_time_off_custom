from odoo import models


class IrHttp(models.AbstractModel):
    _inherit = "ir.http"

    def session_info(self):
        info = super().session_info()
        icp = self.env["ir.config_parameter"].sudo()
        info["enable_user_language_switch"] = icp.get_param(
            "vn_language_switch.enable_user_language_switch", "False"
        ) == "True"
        return info
