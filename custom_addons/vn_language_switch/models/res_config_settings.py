from odoo import _, fields, models
from odoo.exceptions import UserError


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    ui_language_mode = fields.Selection(
        selection=[
            ("en_US", "English"),
            ("vi_VN", "Tiếng Việt"),
        ],
        string="Odoo Interface Language",
        default="en_US",
        config_parameter="vn_language_switch.ui_language_mode",
        help="Choose the interface language for internal users.",
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

    def _apply_language_to_internal_users(self, lang_code):
        users = self.env["res.users"].search([("share", "=", False)])
        users.write({"lang": lang_code})

    def set_values(self):
        super().set_values()
        self.ensure_one()
        selected_lang = self.ui_language_mode or "en_US"
        self._ensure_language_is_available(selected_lang)
        self._apply_language_to_internal_users(selected_lang)
