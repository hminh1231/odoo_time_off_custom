# -*- coding: utf-8 -*-

import functools

from odoo import api, models
from odoo.fields import Domain


class HrEmployeeAccessMixin(models.AbstractModel):
    _inherit = "hr.employee.access.mixin"

    @api.model
    def _lug_user_zone_legacy_miens(self, user=None):
        user = (user or self.env.user).sudo()
        if (user.lug_hr_employee_edit_policy or "none") != "zones":
            return []
        return [
            (zone.legacy_mien or "").strip()
            for zone in user.lug_hr_employee_edit_mien_zone_ids
            if (zone.legacy_mien or "").strip()
        ]

    @api.model
    def _hr_employee_policy_domain(self, user=None):
        """LUG zone editors read employees in their configured Miền zones."""
        user = user or self.env.user
        if user.sudo()._lug_permission_is_enforced():
            legacy_miens = self._lug_user_zone_legacy_miens(user)
            if legacy_miens:
                return Domain([("mien", "in", legacy_miens)])
        return super()._hr_employee_policy_domain(user)

    @api.model
    def _hr_employee_visibility_read_domain(self, user=None, model_name=None):
        """When LUG is active, enforce visibility_policy strictly."""
        user = user or self.env.user
        if not user.sudo()._lug_permission_is_enforced():
            return super()._hr_employee_visibility_read_domain(
                user, model_name=model_name
            )
        if self._hr_employee_user_has_full_visibility(user):
            return None
        policy = self._hr_employee_policy_domain(user)
        self_only = Domain(
            [
                "|",
                "|",
                ("user_id", "=", user.id),
                ("id", "=", user.sudo().employee_id.id),
                ("leave_manager_id", "=", user.id),
            ]
        )
        company = self._hr_employee_company_domain(user)
        if policy is None:
            return self_only & company
        return (policy | self_only) & company

    @api.model
    def _hr_employee_access_org_reference_readable_ids(self, user=None):
        """Manager/coach of the current user (employee form parent_id widget)."""
        user = user or self.env.user
        if not user.sudo()._lug_permission_is_enforced():
            return []
        own = user.sudo().employee_id
        if not own:
            return []
        # Read FKs in SQL: hr.employee parent_id/coach_id can be cleared in the
        # ORM cache by visibility helpers before this runs (MissingError on forms).
        self.env.cr.execute(
            "SELECT parent_id, coach_id FROM hr_employee WHERE id = %s",
            (own.id,),
        )
        row = self.env.cr.fetchone()
        if not row:
            return []
        return [rel_id for rel_id in row if rel_id]

    @api.model
    def _hr_employee_access_zone_parent_reference_readable_ids(self, user=None):
        """Managers/coaches linked from employees inside the user's LUG zones."""
        user = user or self.env.user
        if not user.sudo()._lug_permission_is_enforced():
            return []
        legacy_miens = self._lug_user_zone_legacy_miens(user)
        if not legacy_miens:
            return []
        self.env.cr.execute(
            """
            SELECT DISTINCT rel_id
            FROM (
                SELECT parent_id AS rel_id FROM hr_employee WHERE mien = ANY(%s)
                UNION
                SELECT coach_id AS rel_id FROM hr_employee WHERE mien = ANY(%s)
            ) refs
            WHERE rel_id IS NOT NULL
            """,
            (legacy_miens, legacy_miens),
        )
        return [row[0] for row in self.env.cr.fetchall()]

    @api.model
    def _hr_employee_access_user_linked_reference_readable_ids(self, user=None):
        """Employees linked to res.users the current user may open (LUG user list)."""
        user = user or self.env.user
        if not user.sudo()._lug_permission_is_enforced():
            return []
        readable_users = self.env["res.users"].with_user(user).search([])
        return [
            emp_id
            for emp_id in readable_users.sudo().employee_id.ids
            if emp_id
        ]

    @api.model
    def _hr_employee_access_leave_reference_readable_ids(self, user=None):
        """Employee ids from leave rows visible to the user (Time Off list)."""
        user = user or self.env.user
        if not user.sudo()._lug_permission_is_enforced():
            return []
        if self.env.context.get("_hr_emp_leave_scan"):
            return []
        Leave = self.env.get("hr.leave")
        if not Leave:
            return []
        leaves = (
            Leave.with_user(user)
            .with_context(_hr_emp_leave_scan=True)
            .search([])
            .sudo()
        )
        return [i for i in leaves.employee_id.ids if i]

    @api.model
    def _hr_employee_access_reference_readable_ids(self, user=None):
        """Linked records readable for UI widgets (not employee directory search)."""
        ids = set(self._hr_employee_access_org_reference_readable_ids(user))
        ids.update(self._hr_employee_access_zone_parent_reference_readable_ids(user))
        ids.update(self._hr_employee_access_user_linked_reference_readable_ids(user))
        return list(ids)

    @api.model
    def _hr_employee_leave_approval_emp_ids(self, user=None):
        user = user or self.env.user
        if not user.sudo()._lug_permission_is_enforced():
            return super()._hr_employee_leave_approval_emp_ids(user)
        return []


def _lug_employee_access_denied(recordset, operation):
    forbidden = recordset
    return (
        forbidden,
        functools.partial(
            recordset.env["ir.rule"]._make_access_error,
            operation,
            forbidden,
        ),
    )


def _lug_filter_readable_field_names(recordset, field_names):
    if not field_names or recordset.env.su:
        return field_names
    readable = []
    for fname in field_names:
        field = recordset._fields.get(fname)
        if field and recordset._has_field_access(field, "read"):
            readable.append(fname)
    return readable


def _lug_filter_web_read_specification(recordset, specification):
    if not specification or recordset.env.su:
        return specification
    return {
        fname: spec
        for fname, spec in specification.items()
        if fname in recordset._fields
        and recordset._has_field_access(recordset._fields[fname], "read")
    }
