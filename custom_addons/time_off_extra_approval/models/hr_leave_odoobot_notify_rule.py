# -*- coding: utf-8 -*-

from datetime import datetime, timedelta

from odoo import api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools.translate import _

from odoo.addons.hr_job_title_vn.models.hr_version import JOB_TITLE_SELECTION

MIEN_SELECTION = [
    ("Bắc", "Bắc"),
    ("Nam", "Nam"),
    ("ĐTT", "ĐTT"),
    ("VP", "VP"),
]

_JOB_TITLE_MIN_KEY = "trưởng nhóm"
NOTIFY_JOB_TITLE_SELECTION = []
_include = False
for _key, _label in JOB_TITLE_SELECTION:
    if _key == _JOB_TITLE_MIN_KEY:
        _include = True
    if _include:
        NOTIFY_JOB_TITLE_SELECTION.append((_key, _label))
if not NOTIFY_JOB_TITLE_SELECTION:
    NOTIFY_JOB_TITLE_SELECTION = [
        ("trưởng nhóm", "Trưởng nhóm"),
        ("trưởng bộ phận", "Trưởng bộ phận"),
        ("giám đốc", "Giám đốc"),
    ]

BOT_TYPE_SELECTION = [
    ("approval", "OdooBot Duyệt đơn"),
    ("handover", "OdooBot Bàn giao việc"),
]

_CRON_MATCH_MINUTES = 8


class HrLeaveOdoobotNotifyRemindTime(models.Model):
    _name = "hr.leave.odoobot.notify.remind.time"
    _description = "OdooBot scheduled reminder time"
    _order = "remind_time, id"

    rule_id = fields.Many2one(
        comodel_name="hr.leave.odoobot.notify.rule",
        required=True,
        ondelete="cascade",
        index=True,
    )
    remind_time = fields.Float(
        string="Reminder time",
        required=True,
        help="Time of day (e.g. 08:00, 14:30) when OdooBot sends a reminder.",
    )

    @api.constrains("remind_time")
    def _check_remind_time(self):
        for line in self:
            if line.remind_time < 0 or line.remind_time >= 24:
                raise ValidationError(_("Giờ nhắc phải từ 00:00 đến 23:59."))


class HrLeaveOdoobotNotifyRule(models.Model):
    _name = "hr.leave.odoobot.notify.rule"
    _description = "Time Off OdooBot notification rule"
    _order = "mien, bot_type, job_title, id"
    _rec_name = "display_name"

    company_id = fields.Many2one(
        comodel_name="res.company",
        string="Company",
        default=lambda self: self.env.company,
        index=True,
    )
    mien = fields.Selection(
        selection=MIEN_SELECTION,
        string="Miền",
        required=True,
        index=True,
    )
    job_title = fields.Selection(
        selection=NOTIFY_JOB_TITLE_SELECTION,
        string="Chức danh",
        required=True,
        index=True,
    )
    bot_type = fields.Selection(
        selection=BOT_TYPE_SELECTION,
        string="Loại OdooBot",
        required=True,
        index=True,
    )
    is_final_level = fields.Boolean(
        string="Mức duyệt cuối cùng",
        help="If enabled, this step is never auto-skipped; only scheduled reminders are sent.",
    )
    skip_level_hours = fields.Float(
        string="Skip current step after (hours)",
        default=2.0,
        help="Auto-skip to the next level after this many hours (only when not final level).",
    )
    remind_time_ids = fields.One2many(
        comodel_name="hr.leave.odoobot.notify.remind.time",
        inverse_name="rule_id",
        string="Reminder times",
    )
    active = fields.Boolean(default=True)
    color = fields.Integer(string="Color Index", default=0)
    display_name = fields.Char(compute="_compute_display_name", store=True)
    job_title_label = fields.Char(compute="_compute_display_labels", store=True)
    bot_type_label = fields.Char(compute="_compute_display_labels", store=True)
    remind_time_count = fields.Integer(
        string="Reminder slots",
        compute="_compute_remind_display",
        store=True,
    )
    remind_times_display = fields.Char(
        string="Reminder schedule",
        compute="_compute_remind_display",
        store=True,
    )
    skip_level_display = fields.Char(
        string="Skip display",
        compute="_compute_skip_level_display",
        store=True,
    )
    remind_time_count_label = fields.Char(
        string="Reminders label",
        compute="_compute_remind_display",
        store=True,
    )

    _rule_unique = models.Constraint(
        "unique (company_id, mien, job_title, bot_type)",
        "Each Miền / chức danh / loại OdooBot can only be configured once per company.",
    )

    @api.depends("mien", "job_title", "bot_type")
    def _compute_display_name(self):
        bot_labels = dict(BOT_TYPE_SELECTION)
        title_labels = dict(NOTIFY_JOB_TITLE_SELECTION)
        for rule in self:
            rule.display_name = "%s · %s · %s" % (
                rule.mien or "?",
                title_labels.get(rule.job_title, rule.job_title or "?"),
                bot_labels.get(rule.bot_type, rule.bot_type or "?"),
            )

    @api.depends("job_title", "bot_type")
    def _compute_display_labels(self):
        bot_labels = dict(BOT_TYPE_SELECTION)
        title_labels = dict(NOTIFY_JOB_TITLE_SELECTION)
        for rule in self:
            rule.job_title_label = title_labels.get(rule.job_title, rule.job_title or "")
            rule.bot_type_label = bot_labels.get(rule.bot_type, rule.bot_type or "")

    @api.depends("remind_time_ids", "remind_time_ids.remind_time")
    def _compute_remind_display(self):
        for rule in self:
            slots = rule.remind_time_ids.sorted("remind_time")
            rule.remind_time_count = len(slots)
            labels = []
            for slot in slots:
                hours = int(slot.remind_time)
                minutes = int(round((slot.remind_time - hours) * 60))
                labels.append("%02d:%02d" % (hours, minutes))
            rule.remind_times_display = ", ".join(labels) if labels else _("Chưa có giờ nhắc")
            rule.remind_time_count_label = _("%s giờ nhắc") % rule.remind_time_count

    @api.depends("is_final_level", "skip_level_hours")
    def _compute_skip_level_display(self):
        for rule in self:
            if rule.is_final_level:
                rule.skip_level_display = _("Mức duyệt cuối — không tự skip")
            else:
                hours = int(rule.skip_level_hours or 0)
                minutes = int(round(((rule.skip_level_hours or 0) - hours) * 60))
                rule.skip_level_display = _("Bỏ qua sau %02d:%02d") % (hours, minutes)

    @api.constrains("is_final_level", "skip_level_hours", "remind_time_ids")
    def _check_rule(self):
        for rule in self:
            if not rule.is_final_level and rule.skip_level_hours <= 0:
                raise ValidationError(
                    _("Thời gian bỏ qua cấp phải lớn hơn 0 khi không phải mức duyệt cuối cùng.")
                )
            if rule.is_final_level and rule.skip_level_hours:
                raise ValidationError(
                    _("Mức duyệt cuối cùng không được có thời gian bỏ qua cấp.")
                )

    @api.onchange("is_final_level")
    def _onchange_is_final_level(self):
        if self.is_final_level:
            self.skip_level_hours = 0.0

    @api.model
    def _find_rule(self, *, company, mien, job_title, bot_type):
        if not mien or not job_title or not bot_type:
            return self.browse()
        company = company or self.env.company
        domain = [
            ("active", "=", True),
            ("mien", "=", mien),
            ("job_title", "=", job_title),
            ("bot_type", "=", bot_type),
            "|",
            ("company_id", "=", False),
            ("company_id", "=", company.id),
        ]
        return self.search(domain, order="company_id desc", limit=1)

    @api.model
    def _float_time_to_minutes(self, float_time):
        """Convert Odoo float_time (hours.fraction) to minutes since midnight."""
        hours = int(float_time)
        minutes = int(round((float_time - hours) * 60))
        return hours * 60 + minutes

    @api.model
    def _local_now_minutes(self, dt=None):
        dt = dt or fields.Datetime.now()
        local_dt = fields.Datetime.context_timestamp(
            self.env.user.with_context(tz="Asia/Ho_Chi_Minh"),
            dt,
        )
        return local_dt.hour * 60 + local_dt.minute, local_dt.date()

    def _matching_remind_slot_key(self, now_dt=None):
        """Return slot key 'YYYY-MM-DD|float_time' if now matches a configured alarm time."""
        self.ensure_one()
        if not self.remind_time_ids:
            return False
        now_minutes, today = self._local_now_minutes(now_dt)
        for slot in self.remind_time_ids:
            slot_minutes = self._float_time_to_minutes(slot.remind_time)
            if abs(now_minutes - slot_minutes) <= _CRON_MATCH_MINUTES:
                return "%s|%.4f" % (today.isoformat(), slot.remind_time)
        return False
