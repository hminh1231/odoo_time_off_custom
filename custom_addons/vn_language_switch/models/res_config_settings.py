from odoo import _, fields, models
from odoo.exceptions import UserError


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    enable_user_language_switch = fields.Boolean(
        string="Enable user language switch",
        config_parameter="vn_language_switch.enable_user_language_switch",
        help="Allow each user to switch their own interface language between English and Vietnamese.",
    )

    def _ensure_language_is_available(self, lang_code):
        lang_model = self.env["res.lang"].with_context(active_test=False)
        lang = lang_model.search([("code", "=", lang_code)], limit=1)
        if not lang:
            raise UserError(
                _(
                    "Language %(code)s is not installed yet. Please install it from "
                    "Settings > Languages first, then try again.",
                    code=lang_code,
                )
            )
        if not lang.active:
            lang.active = True
        return lang

    def set_values(self):
        super().set_values()
        self.ensure_one()
        if self.enable_user_language_switch:
            self._ensure_language_is_available("en_US")
            self._ensure_language_is_available("vi_VN")
