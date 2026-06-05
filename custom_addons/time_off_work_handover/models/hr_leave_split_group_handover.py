# -*- coding: utf-8 -*-
"""Gom tin OdooBot Bàn giao việc cho đơn tách P1/P2/O (một tin, khoảng ngày đầy đủ)."""

import logging
from datetime import timedelta

from markupsafe import Markup, escape

from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)

_HANDOVER_SPLIT_NOTIFIED_CR_KEY = "hr_leave.split_group_handover_notified"


class HrLeaveSplitGroupHandover(models.Model):
    _inherit = "hr.leave"

    @api.model
    def _handover_split_notified_cache(self):
        cache = self.env.cr.cache
        if _HANDOVER_SPLIT_NOTIFIED_CR_KEY not in cache:
            cache[_HANDOVER_SPLIT_NOTIFIED_CR_KEY] = set()
        return cache[_HANDOVER_SPLIT_NOTIFIED_CR_KEY]

    def _handover_split_submission_context_key(self, split_group_id):
        return "split_group_handover_notified_%s" % (split_group_id or "")

    def _handover_recipient_cache_key(self, notify_leave, recipient):
        """One bot ping per recipient per split group (or per leave if not split)."""
        notify_leave.ensure_one()
        if notify_leave.split_group_id:
            return ("handover", "group", notify_leave.split_group_id, recipient.id)
        return ("handover", "leave", notify_leave.id, recipient.id)

    def _handover_recipient_notify_is_done(self, key):
        return key in self._handover_split_notified_cache()

    def _handover_recipient_notify_mark_done(self, key):
        self._handover_split_notified_cache().add(key)

    def _notify_split_group_handover_submit_once(self):
        """Một lần / split_group_id — gọi từ submission_once hoặc sau khi tách xong."""
        self.ensure_one()
        if not self._split_group_is_multi_segment():
            return
        primary = self._get_split_group_primary_leave()
        gid = primary.split_group_id
        ctx_key = primary._handover_split_submission_context_key(gid)
        if self.env.context.get(ctx_key):
            return
        if primary.state != "confirm" or not primary.handover_employee_ids:
            return
        if primary._handover_ready_for_approval():
            return
        primary.with_context(**{ctx_key: True})._notify_handover_recipients_submit_via_bot()

    def _get_handover_bot_notify_leave(self):
        """Record used for Discuss link, acceptance lines, and grouped period."""
        self.ensure_one()
        if self.split_group_id:
            return self._get_split_group_primary_leave()
        return self

    def _format_handover_bot_date(self, value):
        if not value:
            return ""
        if hasattr(value, "date") and callable(value.date):
            value = value.date()
        return value.strftime("%d/%m/%Y")

    def _get_handover_bot_period_text(self, group_leaves=None):
        """Ngày nghỉ trên bot: từ … đến … trên cả nhóm tách (hoặc một đơn nhiều ngày)."""
        self.ensure_one()
        if self.split_group_id:
            group_leaves = self._get_split_group_leaves_all()
        elif group_leaves is None:
            group_leaves = self

        dates_from = []
        dates_to = []
        for leave in group_leaves:
            date_from = leave.request_date_from or (
                leave.date_from and leave.date_from.date()
            )
            date_to = leave.request_date_to or (
                leave.date_to and leave.date_to.date()
            ) or date_from
            if date_from:
                dates_from.append(date_from)
            if date_to:
                dates_to.append(date_to)

        if dates_from and dates_to:
            d_min = min(dates_from)
            d_max = max(dates_to)
            if d_max != d_min:
                return _("%(from)s đến ngày %(to)s") % {
                    "from": self._format_handover_bot_date(d_min),
                    "to": self._format_handover_bot_date(d_max),
                }
            return self._format_handover_bot_date(d_min)

        date_from = self.request_date_from or (self.date_from and self.date_from.date())
        date_to = self.request_date_to or (self.date_to and self.date_to.date())
        if date_to and date_from and date_to != date_from:
            return _("%(from)s đến ngày %(to)s") % {
                "from": self._format_handover_bot_date(date_from),
                "to": self._format_handover_bot_date(date_to),
            }
        return self._format_handover_bot_date(date_from)

    def _handover_bot_message_already_sent(self, chat, marker_value, marker_attr="data-oe-handover-split-group"):
        if not marker_value:
            return False
        marker = '%s="%s"' % (marker_attr, marker_value)
        cutoff = fields.Datetime.now() - timedelta(minutes=30)
        bot_user = self.env.ref(
            "business_discuss_bots.user_bot_handover", raise_if_not_found=False
        )
        bot_partner_id = bot_user.partner_id.id if bot_user and bot_user.partner_id else False
        domain = [
            ("model", "=", "discuss.channel"),
            ("body", "ilike", marker),
            ("create_date", ">=", cutoff),
        ]
        if bot_partner_id:
            # Same split_group marker may exist in another bot↔user chat channel.
            domain.append(("author_id", "=", bot_partner_id))
        elif chat:
            domain.append(("res_id", "=", chat.id))
        else:
            return False
        return bool(self.env["mail.message"].sudo().search_count(domain, limit=1))

    def _notify_handover_recipients_submit_via_bot(self):
        to_send = self.env["hr.leave"]
        seen_keys = set()
        for leave in self.filtered("handover_employee_ids"):
            if leave.split_group_id and not leave._split_group_is_multi_segment():
                continue
            if leave.split_group_id and not leave._is_split_group_primary_leave():
                continue
            notify_leave = leave._get_handover_bot_notify_leave()
            dedupe_key = ("handover_submit", notify_leave.split_group_id or notify_leave.id)
            if dedupe_key in seen_keys:
                continue
            ctx_key = notify_leave._handover_split_submission_context_key(
                notify_leave.split_group_id
            )
            if self.env.context.get(ctx_key):
                continue
            seen_keys.add(dedupe_key)
            to_send |= notify_leave
        for leave in to_send:
            ctx_key = leave._handover_split_submission_context_key(leave.split_group_id)
            leave.with_context(**{ctx_key: True})._notify_specific_handover_recipients_via_bot(
                leave.handover_employee_ids
            )

    def _notify_specific_handover_recipients_via_bot(self, employees):
        self.ensure_one()
        if not employees:
            return
        notify_leave = self._get_handover_bot_notify_leave()
        if notify_leave != self:
            return notify_leave._notify_specific_handover_recipients_via_bot(employees)

        group = (
            notify_leave._get_split_group_leaves_all()
            if notify_leave.split_group_id
            else notify_leave
        )
        requester_name = (
            notify_leave.employee_id.name
            or notify_leave.employee_id.display_name
            or notify_leave.display_name
        )
        date_text = notify_leave._get_handover_bot_period_text(group)
        split_group_id = notify_leave.split_group_id or False
        button_html = notify_leave._notify_handover_bot_leave_form_open_button_markup()
        bot_user = self.env.ref(
            "business_discuss_bots.user_bot_handover", raise_if_not_found=False
        ) or self.env.ref("base.user_root")
        bot_partner_id = bot_user.partner_id.id if bot_user and bot_user.partner_id else False
        channel_model = self.env["discuss.channel"].sudo()
        sent_count = 0
        for recipient in employees:
            user = recipient.user_id
            if not user or not user.partner_id:
                _logger.info(
                    "time_off_work_handover: skip handover bot DM leave_id=%s employee_id=%s (no user or partner)",
                    notify_leave.id,
                    recipient.id,
                )
                continue
            cache_key = notify_leave._handover_recipient_cache_key(notify_leave, recipient)
            if notify_leave._handover_recipient_notify_is_done(cache_key):
                _logger.info(
                    "time_off_work_handover: skip duplicate handover cache leave_id=%s recipient=%s",
                    notify_leave.id,
                    recipient.id,
                )
                continue
            line = notify_leave.handover_acceptance_ids.filtered(
                lambda l: l.employee_id == recipient
            )[:1]
            work_content = (line.handover_work_content or "").strip()
            content_text = work_content or _("Không có")
            intro = Markup(
                _(
                    "Nhân viên: <b>{requester}</b> nhờ bàn giao công việc nghỉ ốm<br/>"
                    "Ngày nghỉ: <b>{date}</b><br/>"
                    "Nội dung: "
                )
            ).format(requester=requester_name, date=date_text)
            if split_group_id:
                marker = Markup(
                    '<span data-oe-handover-split-group="%s" style="display:none"></span>'
                ) % escape(split_group_id)
            else:
                marker = Markup(
                    '<span data-oe-handover-leave="%s" style="display:none"></span>'
                ) % notify_leave.id
            body = (
                marker
                + intro
                + escape(str(content_text))
                + Markup(
                    _(
                        "<br/>Vui lòng bấm vào <b>Mở Time Off</b> "
                        "để xác nhận công việc bàn giao.<br/><br/>"
                    )
                )
                + button_html
            )
            post_vals = {
                "body": body,
                "message_type": "comment",
                "subtype_xmlid": "mail.mt_comment",
            }
            if bot_partner_id:
                post_vals["author_id"] = bot_partner_id
            try:
                chat = channel_model.with_user(bot_user)._get_or_create_chat(
                    [user.partner_id.id], pin=True
                )
                marker_value = split_group_id or str(notify_leave.id)
                marker_attr = (
                    "data-oe-handover-split-group"
                    if split_group_id
                    else "data-oe-handover-leave"
                )
                if notify_leave._handover_bot_message_already_sent(
                    chat, marker_value, marker_attr=marker_attr
                ):
                    notify_leave._handover_recipient_notify_mark_done(cache_key)
                    _logger.info(
                        "time_off_work_handover: skip duplicate handover bot marker=%s recipient=%s",
                        marker_value,
                        user.login,
                    )
                    continue
                notify_leave._handover_recipient_notify_mark_done(cache_key)
                chat.with_user(bot_user).sudo().message_post(**post_vals)
                sent_count += 1
            except Exception:
                try:
                    bot_partner = bot_user.partner_id if bot_user else False
                    if not bot_partner:
                        raise ValueError("handover bot partner not found")
                    chat = (
                        self.env["discuss.channel"]
                        .sudo()
                        .with_user(user)
                        ._get_or_create_chat([bot_partner.id], pin=True)
                    )
                    marker_value = split_group_id or str(notify_leave.id)
                    marker_attr = (
                        "data-oe-handover-split-group"
                        if split_group_id
                        else "data-oe-handover-leave"
                    )
                    if notify_leave._handover_bot_message_already_sent(
                        chat, marker_value, marker_attr=marker_attr
                    ):
                        notify_leave._handover_recipient_notify_mark_done(cache_key)
                        continue
                    notify_leave._handover_recipient_notify_mark_done(cache_key)
                    chat.with_user(bot_user).sudo().message_post(**post_vals)
                    sent_count += 1
                except Exception:
                    _logger.exception(
                        "time_off_work_handover: failed handover submit bot leave_id=%s recipient_id=%s",
                        notify_leave.id,
                        recipient.id,
                    )
        if not sent_count:
            _logger.warning(
                "time_off_work_handover: handover bot DM reached no recipients leave_id=%s employee_ids=%s",
                notify_leave.id,
                employees.ids,
            )

    def _notify_split_group_after_companion_create(self):
        super()._notify_split_group_after_companion_create()
