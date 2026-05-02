from odoo import _, api, fields, models
from odoo.exceptions import UserError

_HANDOVER_PEER_RESPONSE_FIELDS = frozenset({"state", "responded_at", "refusal_reason"})


class HrLeaveHandoverAcceptance(models.Model):
    _name = "hr.leave.handover.acceptance"
    _description = "Xác nhận bàn giao công việc"
    _order = "sequence, id"

    sequence = fields.Integer(string="STT", default=1)

    leave_id = fields.Many2one(
        comodel_name="hr.leave",
        string="Nghỉ phép",
        required=True,
        ondelete="cascade",
        index=True,
    )
    employee_id = fields.Many2one(
        comodel_name="hr.employee",
        string="Người nhận bàn giao",
        required=True,
        ondelete="cascade",
        index=True,
    )
    handover_work_content = fields.Text(string="Nội dung công việc")
    state = fields.Selection(
        selection=[
            ("pending", "Chờ phản hồi"),
            ("accepted", "Đã chấp nhận"),
            ("refused", "Đã từ chối"),
        ],
        string="Phản hồi",
        default="pending",
        required=True,
    )
    responded_at = fields.Datetime(string="Thời điểm phản hồi")
    refusal_reason = fields.Text(string="Lý do từ chối")
    assigned_by_user_id = fields.Many2one(
        comodel_name="res.users",
        string="Được gán bởi",
        copy=False,
        help="Nếu có giá trị, người nhận này được chọn bởi user này (ví dụ: trưởng bộ phận sau khi bàn giao quá hạn).",
    )
    reassigned_by_escalation_owner = fields.Boolean(
        string="Được chọn bởi trưởng bộ phận sau chuyển cấp",
        default=False,
        copy=False,
        help="Đúng khi trưởng bộ phận (người phụ trách chuyển cấp) đã gán người nhận này sau khi quá hạn.",
    )

    _sql_constraints = [
        (
            "leave_employee_unique",
            "unique(leave_id, employee_id)",
            "Mỗi đồng nghiệp chỉ có một dòng bàn giao công việc cho mỗi đơn nghỉ phép.",
        ),
    ]

    @api.onchange("employee_id", "handover_work_content")
    def _onchange_resequence_lines_realtime(self):
        for line in self:
            leave = line.leave_id
            if not leave:
                continue
            for idx, sibling in enumerate(leave.handover_acceptance_ids, start=1):
                sibling.sequence = idx

    def _handover_line_is_recipient_pending_response_write(self, vals):
        """Allow accept/refuse to update status fields only for this recipient's pending row."""
        self.ensure_one()
        if self.state != "pending":
            return False
        if not vals:
            return False
        if set(vals) - _HANDOVER_PEER_RESPONSE_FIELDS:
            return False
        viewer = self.env.user.sudo().employee_id
        if not viewer or viewer != self.employee_id:
            return False
        return "state" in vals and vals.get("state") in ("accepted", "refused")

    def _resequence_by_leave(self, leave_ids):
        if not leave_ids:
            return
        for leave_id in set(leave_ids):
            lines = self.search([("leave_id", "=", leave_id)], order="sequence,id")
            for idx, line in enumerate(lines, start=1):
                if line.sequence != idx:
                    line.with_context(skip_handover_resequence=True).write({"sequence": idx})

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            leave_id = vals.get("leave_id")
            if leave_id:
                leave = self.env["hr.leave"].browse(leave_id)
                if leave.exists() and not leave._viewer_can_manage_handover_acceptance_sheet():
                    raise UserError(
                        _(
                            "Bạn không được phép chỉnh sửa danh sách người nhận bàn giao trên đơn này. "
                            "Chỉ người nộp đơn (hoặc nhân sự được phép) mới được thêm hoặc xóa người bàn giao."
                        )
                    )
            if "sequence" in vals and vals.get("sequence"):
                continue
            leave_id = vals.get("leave_id")
            if not leave_id:
                vals["sequence"] = 1
                continue
            siblings = self.search([("leave_id", "=", leave_id)])
            vals["sequence"] = (max(siblings.mapped("sequence")) + 1) if siblings else 1
        lines = super().create(vals_list)
        lines._resequence_by_leave(lines.mapped("leave_id").ids)
        return lines

    def write(self, vals):
        if self.env.su:
            return super().write(vals)
        for line in self:
            leave = line.leave_id
            if not leave:
                continue
            if leave._viewer_can_manage_handover_acceptance_sheet():
                continue
            if line._handover_line_is_recipient_pending_response_write(vals):
                continue
            raise UserError(
                _(
                    "Bạn không được phép chỉnh sửa danh sách người nhận bàn giao trên đơn này. "
                    "Chỉ người nộp đơn (hoặc nhân sự được phép) mới được thêm, sửa hoặc xóa người bàn giao."
                )
            )
        if self.env.context.get("skip_handover_resequence"):
            return super().write(vals)
        old_leave_ids = self.mapped("leave_id").ids
        res = super().write(vals)
        new_leave_ids = self.mapped("leave_id").ids
        if "sequence" in vals or "leave_id" in vals:
            self._resequence_by_leave(old_leave_ids + new_leave_ids)
        return res

    def unlink(self):
        if not self.env.su:
            for line in self:
                leave = line.leave_id
                if leave.exists() and not leave._viewer_can_manage_handover_acceptance_sheet():
                    raise UserError(
                        _(
                            "Bạn không được phép xóa dòng người nhận bàn giao. "
                            "Chỉ người nộp đơn (hoặc nhân sự được phép) mới được thay đổi danh sách này."
                        )
                    )
        leave_ids = self.mapped("leave_id").ids
        res = super().unlink()
        self._resequence_by_leave(leave_ids)
        return res
