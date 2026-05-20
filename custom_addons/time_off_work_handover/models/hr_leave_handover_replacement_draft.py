from odoo import _, api, fields, models
from odoo.exceptions import UserError


class HrLeaveHandoverReplacementDraft(models.Model):
    _name = "hr.leave.handover.replacement.draft"
    _description = "Handover recipient replacement line"
    _order = "sequence, id"

    leave_id = fields.Many2one(
        comodel_name="hr.leave",
        string="Time Off Request",
        required=True,
        ondelete="cascade",
        index=True,
    )
    sequence = fields.Integer(string="No.", default=1)
    replace_employee_id = fields.Many2one(
        comodel_name="hr.employee",
        string="Employee to replace",
        help="Recipient currently in the handover list and eligible for replacement (refused or escalated waiting).",
    )
    new_employee_id = fields.Many2one(
        comodel_name="hr.employee",
        string="New handover recipient",
    )
    handover_work_content = fields.Text(string="Work content")
    allowed_new_employee_ids = fields.Many2many(
        comodel_name="hr.employee",
        compute="_compute_allowed_new_employee_ids",
    )

    def _raise_if_leave_cannot_manage_drafts(self, leave):
        if not leave or not leave.exists():
            raise UserError(_("Missing time off request for handover replacement line."))
        if not leave.handover_replacement_picker_open:
            raise UserError(_("Cannot edit replacement lines after the picker is closed."))
        if not leave.can_manage_handover_replacement:
            raise UserError(
                _("Only the requester (or the assigned escalation owner) can edit this section.")
            )

    @api.depends(
        "leave_id",
        "leave_id.handover_employee_ids",
        "leave_id.employee_id",
        "leave_id.unavailable_handover_employee_ids",
        "replace_employee_id",
    )
    def _compute_allowed_new_employee_ids(self):
        Employee = self.env["hr.employee"]
        for line in self:
            leave = line.leave_id
            if not leave or not leave.employee_id:
                line.allowed_new_employee_ids = Employee
                continue
            blocked = leave.handover_employee_ids
            if line.replace_employee_id:
                blocked = blocked - line.replace_employee_id
            candidates = Employee.search(
                [
                    ("id", "!=", leave.employee_id.id),
                    ("user_id", "!=", False),
                ]
            )
            unavailable = leave.unavailable_handover_employee_ids
            line.allowed_new_employee_ids = candidates - blocked - unavailable

    @api.onchange("replace_employee_id")
    def _onchange_replace_employee_id_clear_new_if_invalid(self):
        for line in self:
            if line.new_employee_id and line.new_employee_id not in line.allowed_new_employee_ids:
                line.new_employee_id = False

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            leave = self.env["hr.leave"].browse(vals.get("leave_id") or 0)
            self._raise_if_leave_cannot_manage_drafts(leave)
            if "sequence" in vals and vals.get("sequence"):
                continue
            leave_id = vals.get("leave_id")
            if not leave_id:
                vals["sequence"] = 1
                continue
            siblings = self.search([("leave_id", "=", leave_id)])
            vals["sequence"] = (max(siblings.mapped("sequence")) + 1) if siblings else 1
        records = super().create(vals_list)
        records._resequence_by_leave(records.mapped("leave_id").ids)
        return records

    def write(self, vals):
        if not self.env.su:
            for line in self:
                self._raise_if_leave_cannot_manage_drafts(line.leave_id)
        if self.env.context.get("skip_handover_replacement_draft_resequence"):
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
                if leave.handover_replacement_picker_open and not leave.can_manage_handover_replacement:
                    raise UserError(
                        _("Only the requester (or the assigned escalation owner) can delete this line.")
                    )
        leave_ids = self.mapped("leave_id").ids
        res = super().unlink()
        self._resequence_by_leave(leave_ids)
        return res

    def _resequence_by_leave(self, leave_ids):
        if not leave_ids:
            return
        for leave_id in set(leave_ids):
            lines = self.search([("leave_id", "=", leave_id)], order="sequence,id")
            for idx, line in enumerate(lines, start=1):
                if line.sequence != idx:
                    line.with_context(skip_handover_replacement_draft_resequence=True).write({"sequence": idx})
