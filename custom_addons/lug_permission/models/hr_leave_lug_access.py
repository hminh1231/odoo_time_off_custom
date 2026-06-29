# -*- coding: utf-8 -*-
"""Align hr.leave visibility with LUG employee scope (VP-only users, etc.)."""

from odoo import api, models
from odoo.exceptions import AccessError, MissingError
from odoo.tools.sql import SQL


def _lug_leave_scope_active(env):
    user = env.user
    return (
        not env.su
        and user.sudo()._lug_permission_is_enforced()
        and not user.has_group("hr.group_hr_manager")
    )


def _lug_visible_employee_ids(env):
    user = env.user
    mixin = env["hr.employee.access.mixin"]
    visible = set(env["hr.employee.public"].with_user(user).search([]).ids)
    visible.update(mixin._hr_employee_access_reference_readable_ids(user))
    if user.sudo().employee_id:
        visible.add(user.sudo().employee_id.id)
    return list(visible)


def _lug_leave_employee_ids_for_records(recordset):
    if not recordset:
        return {}
    ids = [rid for rid in recordset.ids if isinstance(rid, int)]
    if not ids:
        # Onchange/new records have no DB id yet; read employee from cache.
        return {
            rec.id: rec.employee_id.id
            for rec in recordset
            if rec.employee_id
        }
    table = recordset._table
    recordset.env.cr.execute(
        f"SELECT id, employee_id FROM {table} WHERE id IN %s",
        (tuple(ids),),
    )
    return {row[0]: row[1] for row in recordset.env.cr.fetchall()}


def _lug_leave_employee_web_value(env, emp_id, emp_spec, public_model):
    public = public_model.browse(emp_id)
    try:
        public.check_access("read")
        if emp_spec:
            return public.web_read(emp_spec)[0]
        return {"id": emp_id, "display_name": public.display_name}
    except (MissingError, AccessError):
        pass
    sudo_emp = env["hr.employee"].sudo().browse(emp_id)
    if not sudo_emp.exists():
        return False
    display = sudo_emp.display_name
    if emp_spec:
        inner = (
            emp_spec.get("fields") if isinstance(emp_spec.get("fields"), dict) else {}
        )
        if inner:
            data = {"id": emp_id, "display_name": display}
            if "name" in inner:
                data["name"] = sudo_emp.name
            return data
    return {"id": emp_id, "display_name": display}


def _lug_patch_read_employee(recordset, fields, load, super_read):
    if not fields or "employee_id" not in fields or not _lug_leave_scope_active(recordset.env):
        return super_read(fields, load)
    other = [field_name for field_name in fields if field_name != "employee_id"]
    rows = (
        super_read(other or ["id"], load)
        if other
        else [{"id": rec.id} for rec in recordset]
    )
    by_id = {row["id"]: row for row in rows}
    Public = recordset.env["hr.employee.public"].with_user(recordset.env.user)
    emp_by_id = _lug_leave_employee_ids_for_records(recordset)
    for record in recordset:
        row = by_id.setdefault(record.id, {"id": record.id})
        emp_id = emp_by_id.get(record.id)
        if not emp_id:
            row["employee_id"] = False
            continue
        try:
            row["employee_id"] = Public.browse(emp_id).id
        except (MissingError, AccessError):
            row["employee_id"] = emp_id
    return [by_id[record.id] for record in recordset]


class HrLeaveLugAccess(models.Model):
    _inherit = "hr.leave"

    @api.model
    def _search(
        self,
        domain,
        offset=0,
        limit=None,
        order=None,
        *,
        active_test=True,
        bypass_access=False,
    ):
        query = super()._search(
            domain,
            offset=offset,
            limit=limit,
            order=order,
            active_test=active_test,
            bypass_access=bypass_access,
        )
        if _lug_leave_scope_active(self.env):
            visible = _lug_visible_employee_ids(self.env)
            query.add_where(
                SQL(
                    "%s IN %s",
                    SQL.identifier(self._table, "employee_id"),
                    tuple(visible or [0]),
                )
            )
        return query

    def _filtered_access(self, operation):
        if operation != "read" or not _lug_leave_scope_active(self.env):
            return super()._filtered_access(operation)
        policy_visible = set(
            self.env["hr.employee.public"].with_user(self.env.user).search([]).ids
        )
        if self.env.user.sudo().employee_id:
            policy_visible.add(self.env.user.sudo().employee_id.id)
        emp_by_id = _lug_leave_employee_ids_for_records(self)
        in_scope = self.browse(
            [
                leave_id
                for leave_id in self.ids
                if emp_by_id.get(leave_id) in policy_visible
            ]
        )
        if not in_scope:
            return self.browse()
        return super(HrLeaveLugAccess, in_scope)._filtered_access(operation)

    def web_read(self, specification):
        if (
            not specification
            or "employee_id" not in specification
            or not _lug_leave_scope_active(self.env)
        ):
            return super().web_read(specification)

        spec = dict(specification)
        emp_spec = spec.pop("employee_id")
        if spec:
            rows = super().web_read(spec)
        else:
            rows = [{"id": rec.id} for rec in self]
        if not isinstance(emp_spec, dict):
            emp_spec = {}

        Public = self.env["hr.employee.public"].with_user(self.env.user)
        emp_by_id = _lug_leave_employee_ids_for_records(self)
        for row, record in zip(rows, self):
            emp_id = emp_by_id.get(record.id)
            if not emp_id:
                row["employee_id"] = False
                continue
            row["employee_id"] = _lug_leave_employee_web_value(
                self.env, emp_id, emp_spec, Public
            )
        return rows

    def read(self, fields=None, load="_classic_read"):
        return _lug_patch_read_employee(
            self, fields, load, lambda f, l: super(HrLeaveLugAccess, self).read(f, l)
        )


class HrLeaveReportCalendarLugAccess(models.Model):
    _inherit = "hr.leave.report.calendar"

    @api.model
    def _search(
        self,
        domain,
        offset=0,
        limit=None,
        order=None,
        *,
        active_test=True,
        bypass_access=False,
    ):
        if _lug_leave_scope_active(self.env):
            visible = _lug_visible_employee_ids(self.env)
            domain = list(domain) + [("employee_id", "in", visible or [0])]
        return super()._search(
            domain,
            offset=offset,
            limit=limit,
            order=order,
            active_test=active_test,
            bypass_access=bypass_access,
        )

    def web_read(self, specification):
        if (
            not specification
            or "employee_id" not in specification
            or not _lug_leave_scope_active(self.env)
        ):
            return super().web_read(specification)

        spec = dict(specification)
        emp_spec = spec.pop("employee_id")
        if spec:
            rows = super().web_read(spec)
        else:
            rows = [{"id": rec.id} for rec in self]
        if not isinstance(emp_spec, dict):
            emp_spec = {}

        Public = self.env["hr.employee.public"].with_user(self.env.user)
        emp_by_id = _lug_leave_employee_ids_for_records(self)
        for row, record in zip(rows, self):
            emp_id = emp_by_id.get(record.id)
            if not emp_id:
                row["employee_id"] = False
                continue
            row["employee_id"] = _lug_leave_employee_web_value(
                self.env, emp_id, emp_spec, Public
            )
        return rows

    def read(self, fields=None, load="_classic_read"):
        return _lug_patch_read_employee(
            self,
            fields,
            load,
            lambda f, l: super(HrLeaveReportCalendarLugAccess, self).read(f, l),
        )
