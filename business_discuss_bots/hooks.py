# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def post_init_hook(cr):
    env = api.Environment(cr, SUPERUSER_ID, {})
    bot_users = env["res.users"].browse(
        [
            env.ref("business_discuss_bots.user_bot_handover").id,
            env.ref("business_discuss_bots.user_bot_approval").id,
        ]
    ).filtered(lambda u: u.partner_id and u.active)
    if not bot_users:
        return

    internal_users = env["res.users"].sudo().search([("share", "=", False), ("active", "=", True)])
    for user in internal_users:
        if not user.partner_id:
            continue
        for bot_user in bot_users:
            if user.id == bot_user.id:
                continue
            try:
                env["discuss.channel"].with_user(user).sudo()._get_or_create_chat([bot_user.partner_id.id], pin=True)
            except Exception:
                _logger.exception(
                    "business_discuss_bots: failed to initialize chat user_id=%s bot_user_id=%s",
                    user.id,
                    bot_user.id,
                )
