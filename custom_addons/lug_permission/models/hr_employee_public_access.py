# -*- coding: utf-8 -*-

from odoo import SUPERUSER_ID, api, models

from .hr_employee_access import (
    _lug_employee_access_denied,
    _lug_filter_readable_field_names,
    _lug_filter_web_read_specification,
)

RELATED_EMPLOYEE_PUBLIC_FIELDS = ("parent_id", "coach_id")
# employee_id on public is hr.employee with the same pk; nested web_read breaks under LUG.
PUBLIC_SELF_MANY2ONE_FIELDS = ("employee_id",)


class HrEmployeePublicLugAccess(models.Model):
    _inherit = "hr.employee.public"

    def _lug_reference_readable_ids(self):
        return self.env["hr.employee.access.mixin"]._hr_employee_access_reference_readable_ids(
            self.env.user
        )

    def _lug_public_related_fk_map(self, fname):
        if fname not in RELATED_EMPLOYEE_PUBLIC_FIELDS or not self.ids:
            return {}
        self.env.cr.execute(
            f"SELECT id, {fname} FROM hr_employee_public WHERE id IN %s",
            (tuple(self.ids),),
        )
        return dict(self.env.cr.fetchall())

    def _lug_web_read_related_public(self, related, rel_spec):
        if not isinstance(rel_spec, dict):
            return {"id": related.id, "display_name": related.display_name}
        if "fields" not in rel_spec:
            if rel_spec:
                return related.web_read(rel_spec)[0]
            return {"id": related.id, "display_name": related.display_name}
        inner = dict(rel_spec["fields"])
        want_display = "display_name" in inner
        inner.pop("display_name", None)
        if inner:
            data = related.web_read(inner)[0]
        else:
            data = {"id": related.id}
        if want_display:
            data["display_name"] = related.display_name
        return data.get("id") and data

    def _lug_split_policy_and_ref(self):
        """Split accessible records into policy-visible vs org-reference-only."""
        allowed = self._hr_employee_filter_accessible()
        if not allowed:
            return self.browse(), self.browse()
        policy = self._lug_policy_accessible()
        ref_only = allowed - policy
        return allowed - ref_only, ref_only

    def _hr_employee_filter_accessible(self):
        if not self._hr_employee_read_is_restricted():
            return super()._hr_employee_filter_accessible()
        ref_ids = set(
            self.env["hr.employee.access.mixin"]._hr_employee_access_reference_readable_ids(
                self.env.user
            )
        )
        allowed = super()._hr_employee_filter_accessible()
        if not ref_ids:
            return allowed
        include_ids = set(allowed.ids)
        for rec_id in self.ids:
            if rec_id in ref_ids:
                include_ids.add(rec_id)
        return self.browse(list(include_ids))

    def _lug_policy_accessible(self):
        return super(HrEmployeePublicLugAccess, self)._hr_employee_filter_accessible()

    def _filtered_access(self, operation):
        if operation == "read" and self._hr_employee_read_is_restricted():
            allowed = self._hr_employee_filter_accessible()
            if not allowed:
                return self.browse()
            policy_allowed, ref_only = self._lug_split_policy_and_ref()
            result = self.browse(ref_only.ids)
            if policy_allowed:
                result |= super(
                    HrEmployeePublicLugAccess, policy_allowed
                )._filtered_access(operation)
            return result
        return super()._filtered_access(operation)

    def _check_access(self, operation):
        if operation == "read" and self.ids and self._hr_employee_read_is_restricted():
            allowed = self._hr_employee_filter_accessible()
            forbidden = self - allowed
            if forbidden:
                return _lug_employee_access_denied(forbidden, operation)
            policy_allowed, ref_only = self._lug_split_policy_and_ref()
            if policy_allowed:
                result = super(
                    HrEmployeePublicLugAccess, policy_allowed
                )._check_access(operation)
                if result:
                    return result
            return None
        return super()._check_access(operation)

    def read(self, fields=None, load="_classic_read"):
        if fields:
            fields = _lug_filter_readable_field_names(self, list(fields))
        if not self._hr_employee_read_is_restricted():
            return super().read(fields, load)
        allowed = self._hr_employee_filter_accessible()
        if not allowed:
            return []
        ref_ids = set(self._lug_reference_readable_ids())
        policy_allowed = self._lug_policy_accessible()
        ref_only = allowed.filtered(
            lambda rec: rec.id in ref_ids and rec.id not in policy_allowed.ids
        )
        normal = allowed - ref_only
        rows = []
        if normal:
            rows.extend(super(HrEmployeePublicLugAccess, normal).read(fields, load))
        if ref_only:
            rows.extend(
                self.env["hr.employee.public"]
                .with_user(SUPERUSER_ID)
                .browse(ref_only.ids)
                .read(fields, load)
            )
        return rows

    def fetch(self, field_names=None):
        # ORM calls fetch() directly for attribute access (org chart manager
        # chain, computed fields, mail). Reference-only records (managers/coaches
        # outside the policy scope) are added to `allowed` by
        # _hr_employee_filter_accessible but fail the base fetch's ir.rule/scope
        # re-check, raising AccessError. Fill their cache via SUPERUSER instead.
        if not self._hr_employee_read_is_restricted():
            return super().fetch(field_names)
        if field_names is not None:
            field_names = _lug_filter_readable_field_names(self, list(field_names))
            if not field_names:
                return
        allowed = self._hr_employee_filter_accessible()
        if not allowed:
            return
        policy_allowed, ref_only = self._lug_split_policy_and_ref()
        if policy_allowed:
            super(HrEmployeePublicLugAccess, policy_allowed).fetch(field_names)
        if ref_only:
            self.env["hr.employee.public"].with_user(SUPERUSER_ID).browse(
                ref_only.ids
            ).fetch(field_names)
        return

    def _lug_fill_self_many2one_fields(self, result, specification):
        if "employee_id" not in specification:
            return
        for vals in result:
            emp_id = vals.get("id")
            if not emp_id:
                vals["employee_id"] = False
                continue
            vals["employee_id"] = {
                "id": emp_id,
                "display_name": vals.get("display_name") or vals.get("name") or "",
            }

    def web_read(self, specification):
        specification = _lug_filter_web_read_specification(self, specification)
        if not specification:
            return super().web_read(specification)
        spec_in = dict(specification)
        for name in PUBLIC_SELF_MANY2ONE_FIELDS:
            spec_in.pop(name, None)
        if not self._hr_employee_read_is_restricted():
            result = super().web_read(spec_in)
            self._lug_fill_self_many2one_fields(result, specification)
            return result
        spec = dict(spec_in)
        rel_fields = [name for name in RELATED_EMPLOYEE_PUBLIC_FIELDS if name in spec]
        for name in rel_fields:
            del spec[name]
        allowed = self._hr_employee_filter_accessible()
        result = super(HrEmployeePublicLugAccess, allowed).web_read(spec)
        self._lug_fill_self_many2one_fields(result, specification)
        if not rel_fields:
            return result
        ref_ids = set(self._lug_reference_readable_ids())
        fk_maps = {
            fname: self._lug_public_related_fk_map(fname) for fname in rel_fields
        }
        Public = self.env["hr.employee.public"]
        for vals in result:
            emp_id = vals.get("id")
            if not emp_id:
                for fname in rel_fields:
                    vals[fname] = False
                continue
            for fname in rel_fields:
                rel_id = fk_maps[fname].get(emp_id) or False
                if not rel_id:
                    vals[fname] = False
                    continue
                if rel_id in ref_ids:
                    related = Public.with_user(SUPERUSER_ID).browse(rel_id)
                    vals[fname] = self._lug_web_read_related_public(
                        related, specification[fname]
                    )
                    continue
                related = Public.search([("id", "=", rel_id)], limit=1)
                if related:
                    vals[fname] = self._lug_web_read_related_public(
                        related, specification[fname]
                    )
                else:
                    vals[fname] = False
        return result

    @api.model
    def search_fetch(self, domain, field_names=None, offset=0, limit=None, order=None):
        if field_names:
            field_names = _lug_filter_readable_field_names(self, list(field_names))
        return super().search_fetch(domain, field_names, offset=offset, limit=limit, order=order)

    @api.model
    def web_search_read(self, domain, specification, offset=0, limit=None, order=None, count_limit=None):
        specification = _lug_filter_web_read_specification(self, specification or {})
        return super().web_search_read(
            domain,
            specification,
            offset=offset,
            limit=limit,
            order=order,
            count_limit=count_limit,
        )
