# -*- coding: utf-8 -*-
from odoo import fields, models

from .hr_employee import ICP_MODE_KEY, MODE_BLOCK, MODE_EXCLUDE


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    vp_sunday_mode = fields.Selection(
        [
            (MODE_BLOCK, "Block Sunday selection"),
            (MODE_EXCLUDE, "Allow Sunday but exclude from duration"),
        ],
        string="VP department — Sunday on time off",
        config_parameter=ICP_MODE_KEY,
        default=MODE_BLOCK,
        help=(
            "Applies to employees whose department code (Mã bộ phận) is VP. "
            "Block: Sundays are disabled on the calendar and rejected on save. "
            "Exclude: Sundays in the range are not counted in leave duration."
        ),
    )
