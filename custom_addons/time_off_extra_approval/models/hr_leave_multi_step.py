from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class HrLeaveTypeApprovalStep(models.Model):
    _name = "hr.leave.type.approval.step"
    _description = "Bước duyệt nhiều cấp của nghỉ phép"
    _order = "sequence, id"

    allowed_approver_user_ids = fields.Many2many(
        comodel_name="res.users",
        compute="_compute_allowed_approver_user_ids",
        string="Người duyệt hợp lệ",
    )

    leave_type_id = fields.Many2one(
        comodel_name="hr.leave.type",
        required=True,
        ondelete="cascade",
        index=True,
    )
    sequence = fields.Integer(default=10, index=True)
    name = fields.Char(required=True)

    approver_user_ids = fields.Many2many(
        comodel_name="res.users",
        relation="hr_leave_type_approval_step_user_rel",
        column1="step_id",
        column2="user_id",
        string="Người duyệt (Người dùng)",
        domain="[('id', 'in', allowed_approver_user_ids)]",
    )
    approver_user_id = fields.Many2one(
        comodel_name="res.users",
        string="Người duyệt",
        compute="_compute_approver_user_id",
        inverse="_inverse_approver_user_id",
        store=True,
        readonly=False,
        domain="[('id', 'in', allowed_approver_user_ids)]",
    )
    approver_department_ids = fields.Many2many(
        comodel_name="hr.department",
        relation="hr_leave_type_approval_step_dept_rel",
        column1="step_id",
        column2="department_id",
        string="Người duyệt (Phòng ban)",
    )

    def _get_all_approver_users(self):
        self.ensure_one()
        users = self.approver_user_id or self.approver_user_ids[:1]
        if self.approver_department_ids:
            dept_users = self.approver_department_ids.mapped("member_ids.user_id").filtered(
                lambda u: u and not u.share
            )
            users |= dept_users
        return users

    def _get_base_allowed_users(self):
        group_ids = [
            self.env.ref("hr.group_hr_user").id,
            self.env.ref("hr_holidays.group_hr_holidays_user").id,
            self.env.ref("hr_attendance.group_hr_attendance_user").id,
        ]
        return self.env["res.users"].search([
            ("share", "=", False),
            ("all_group_ids", "in", group_ids),
        ])

    def _approver_pool_users(self):
        """Users linked to employees in the leave type's HR department tree (or group-based fallback)."""
        self.ensure_one()
        lt = self.leave_type_id
        if not lt or not lt.multi_step_hr_source_department_id:
            return self._get_base_allowed_users()
        dept = lt.multi_step_hr_source_department_id
        employees = self.env["hr.employee"].search([("department_id", "child_of", dept.id)])
        return employees.mapped("user_id").filtered(lambda u: u and not u.share)

    def _allowed_approver_user_recordset(self, base_users=None):
        """Users selectable as approver: HR department pool (or group fallback), minus duplicate steps.

        The current step's own approver stays allowed so the value remains valid in the UI.
        """
        self.ensure_one()
        if base_users is None:
            base_users = self._approver_pool_users()
        if not self.leave_type_id:
            return base_users
        taken_ids = {
            s.approver_user_id.id
            for s in self.leave_type_id.multi_approval_step_ids
            if s != self and s.approver_user_id
        }
        cur_id = self.approver_user_id.id if self.approver_user_id else None
        return base_users.filtered(lambda u: u.id not in taken_ids or u.id == cur_id)

    def _refresh_allowed_approver_cache(self):
        """Invalidate computed allowed approver users on all sibling steps (fresh read on open)."""
        leave_type = self.leave_type_id
        if not leave_type:
            return
        siblings = leave_type.multi_approval_step_ids
        if not siblings:
            return
        siblings.invalidate_recordset(["allowed_approver_user_ids"])

    def _approver_user_domain_action(self):
        self._refresh_allowed_approver_cache()
        return {
            "domain": {
                "approver_user_id": [("id", "in", self.allowed_approver_user_ids.ids)],
            }
        }

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._invalidate_step_approver_cache_for_leave_types()
        return records

    def write(self, vals):
        res = super().write(vals)
        if "approver_user_id" in vals or "approver_user_ids" in vals:
            self._invalidate_step_approver_cache_for_leave_types()
        return res

    def _invalidate_step_approver_cache_for_leave_types(self):
        leave_types = self.mapped("leave_type_id")
        if leave_types:
            leave_types.invalidate_recordset(
                ["multi_step_approver_sync"]
                + [f"multi_step_approver_employee_{i}_id" for i in range(1, 7)]
            )
        steps = leave_types.mapped("multi_approval_step_ids")
        if steps:
            steps.invalidate_recordset(["allowed_approver_user_ids"])

    @api.depends_context("uid")
    @api.depends(
        "leave_type_id",
        "leave_type_id.multi_step_hr_source_department_id",
        "leave_type_id.multi_approval_step_ids.approver_user_id",
        "approver_user_id",
    )
    def _compute_allowed_approver_user_ids(self):
        for step in self:
            base_users = step._approver_pool_users()
            step.allowed_approver_user_ids = step._allowed_approver_user_recordset(base_users)

    @api.constrains("approver_user_ids")
    def _check_single_approver_user(self):
        for step in self:
            if len(step.approver_user_ids) > 1:
                raise ValidationError(_("Mỗi bước chỉ được có một người duyệt."))

    @api.constrains("leave_type_id", "approver_user_id")
    def _check_unique_approver_per_leave_type(self):
        for step in self.filtered("approver_user_id"):
            duplicated = step.leave_type_id.multi_approval_step_ids.filtered(
                lambda s: s != step and s.approver_user_id == step.approver_user_id
            )[:1]
            if duplicated:
                raise ValidationError(
                    _("Mỗi người duyệt chỉ được gán cho một bước. %(name)s đang bị gán lặp.")
                    % {"name": step.approver_user_id.display_name}
                )

    @api.depends("approver_user_ids")
    def _compute_approver_user_id(self):
        for step in self:
            step.approver_user_id = step.approver_user_ids[:1]

    def _inverse_approver_user_id(self):
        for step in self:
            if step.approver_user_id:
                step.approver_user_ids = [(6, 0, [step.approver_user_id.id])]
            else:
                step.approver_user_ids = [(5, 0, 0)]

    @api.onchange("approver_user_id")
    def _onchange_approver_user_id_unique_per_step(self):
        for step in self.filtered("approver_user_id"):
            others = step.leave_type_id.multi_approval_step_ids - step
            if others.filtered(lambda s: s.approver_user_id == step.approver_user_id):
                user = step.approver_user_id
                step.approver_user_id = False
                action = self._approver_user_domain_action()
                action["warning"] = {
                    "title": _("Trùng người duyệt"),
                    "message": _(
                        "%(name)s đã được gán ở bước khác. Mỗi người chỉ được duyệt một bước."
                    )
                    % {"name": user.display_name},
                }
                return action
        return self._approver_user_domain_action()

    @api.onchange("leave_type_id.multi_approval_step_ids.approver_user_id")
    def _onchange_refresh_approver_domain(self):
        return self._approver_user_domain_action()



class HrLeaveMultiApproval(models.Model):
    _name = "hr.leave.multi.approval"
    _description = "Nhật ký duyệt nhiều cấp nghỉ phép"
    _order = "approved_at desc, id desc"

    leave_id = fields.Many2one(
        comodel_name="hr.leave",
        ondelete="cascade",
        index=True,
    )
    allocation_id = fields.Many2one(
        comodel_name="hr.leave.allocation",
        ondelete="cascade",
        index=True,
    )

    step_id = fields.Many2one(
        comodel_name="hr.leave.type.approval.step",
        required=True,
        ondelete="restrict",
    )
    approver_user_id = fields.Many2one(
        comodel_name="res.users",
        required=True,
        ondelete="restrict",
    )
    approved_at = fields.Datetime(default=fields.Datetime.now, required=True)

    note = fields.Char()

    _sql_constraints = [
        (
            "only_one_target",
            "CHECK((leave_id IS NOT NULL) <> (allocation_id IS NOT NULL))",
            "Chỉ được thiết lập một trong hai trường leave_id hoặc allocation_id.",
        ),
    ]

