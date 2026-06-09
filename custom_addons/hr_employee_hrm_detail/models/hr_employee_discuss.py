# -*- coding: utf-8 -*-

from odoo import api, models
from odoo.fields import Domain

from odoo.addons.hr.models.hr_employee import _ALLOW_READ_HR_EMPLOYEE


class HrEmployee(models.Model):
    _inherit = "hr.employee"

    def _hr_employee_read_is_restricted(self):
        """True when HR scope rules limit which employee rows may be read."""
        if (
            self.env.context.get("_allow_read_hr_employee")
            is _ALLOW_READ_HR_EMPLOYEE
        ):
            return False
        return (
            self.env["hr.employee.access.mixin"]._hr_employee_access_extra_domain()
            is not None
        )

    def _hr_employee_filter_accessible(self):
        """Keep only records the current user may read under HR scope rules."""
        if not self._hr_employee_read_is_restricted():
            return self
        if not self.ids:
            return self
        mixin = self.env["hr.employee.access.mixin"]
        domain = mixin._hr_employee_apply_access_domain(
            [("id", "in", self.ids)],
            model_name="hr.employee",
        )
        return self.search(domain)

    def _filtered_access(self, operation):
        records = super()._filtered_access(operation)
        if operation == "read" and self._hr_employee_read_is_restricted():
            allowed = self.browse(records.ids)._hr_employee_filter_accessible()
            return records.browse(allowed.ids)
        return records

    def _check_access(self, operation):
        if (
            operation == "read"
            and self.env.context.get("_allow_read_hr_employee") is _ALLOW_READ_HR_EMPLOYEE
        ):
            return None
        if operation == "read" and self.ids and self._hr_employee_read_is_restricted():
            allowed = self._hr_employee_filter_accessible()
            if allowed:
                return super(HrEmployee, allowed)._check_access(operation)
            return None
        return super()._check_access(operation)

    def _read_via_public_fallback(self, records, field_names, load="_classic_read"):
        """Read public fields for employees outside the HR scope (Discuss, etc.)."""
        if not field_names:
            return []
        public_model = self.env["hr.employee.public"]
        public_names = [name for name in field_names if name in public_model._fields]
        if not public_names:
            return []
        mixin = self.env["hr.employee.access.mixin"]
        domain = list(
            mixin._hr_employee_apply_access_domain(
                [("id", "in", records.ids)],
                model_name="hr.employee.public",
            )
        )
        public = public_model.search(domain)
        if not public:
            return []
        return public.read(public_names, load)

    def fetch(self, field_names):
        if not self._hr_employee_read_is_restricted():
            return super().fetch(field_names)
        allowed = self._hr_employee_filter_accessible()
        if allowed:
            super(HrEmployee, allowed).fetch(field_names)
        forbidden = self - allowed
        if forbidden and field_names:
            public_names = [
                name for name in field_names if name in self.env["hr.employee.public"]._fields
            ]
            if public_names:
                mixin = self.env["hr.employee.access.mixin"]
                domain = list(
                    mixin._hr_employee_apply_access_domain(
                        [("id", "in", forbidden.ids)],
                        model_name="hr.employee.public",
                    )
                )
                public = self.env["hr.employee.public"].search(domain)
                if public:
                    public.fetch(public_names)
                    forbidden.browse(public.ids)._copy_cache_from(public, public_names)
        return

    def read(self, fields=None, load="_classic_read"):
        if not self._hr_employee_read_is_restricted():
            return super().read(fields, load)
        allowed = self._hr_employee_filter_accessible()
        forbidden = self - allowed
        result = super(HrEmployee, allowed).read(fields, load) if allowed else []
        if forbidden:
            result.extend(self._read_via_public_fallback(forbidden, fields, load))
        return result

    def get_avatar_card_data(self, fields):
        return super(HrEmployee, self._hr_employee_filter_accessible()).get_avatar_card_data(
            fields
        )

    def _get_store_avatar_card_fields(self, target):
        employees = self._hr_employee_filter_accessible()
        return super(HrEmployee, employees)._get_store_avatar_card_fields(target)

    @api.model
    def search_fetch(self, domain, field_names, offset=0, limit=None, order=None):
        domain = list(domain or [])
        if self._hr_employee_read_is_restricted():
            extra = self.env["hr.employee.access.mixin"]._hr_employee_apply_access_domain(
                domain, model_name="hr.employee"
            )
            if extra is not None:
                domain = list(Domain(domain) & extra)
        return super().search_fetch(domain, field_names, offset=offset, limit=limit, order=order)

    @api.model
    def search_read(self, domain=None, fields=None, offset=0, limit=None, order=None, **read_kwargs):
        domain = list(domain or [])
        if self._hr_employee_read_is_restricted():
            extra = self.env["hr.employee.access.mixin"]._hr_employee_apply_access_domain(
                domain, model_name="hr.employee"
            )
            if extra is not None:
                domain = list(Domain(domain) & extra)
        return super().search_read(
            domain, fields, offset, limit, order, **read_kwargs
        )

    def web_read(self, specification):
        return super(HrEmployee, self._hr_employee_filter_accessible()).web_read(
            specification
        )

    @api.model
    def web_search_read(self, domain, specification, offset=0, limit=None, order=None, count_limit=None):
        domain = list(domain or [])
        if self._hr_employee_read_is_restricted():
            extra = self.env["hr.employee.access.mixin"]._hr_employee_apply_access_domain(
                domain, model_name="hr.employee"
            )
            if extra is not None:
                domain = list(Domain(domain) & extra)
        return super().web_search_read(
            domain, specification, offset=offset, limit=limit, order=order, count_limit=count_limit
        )

    @api.model
    def _read_group(self, domain, groupby=(), aggregates=(), having=(), offset=0, limit=None, order=None):
        if self._hr_employee_read_is_restricted():
            extra = self.env["hr.employee.access.mixin"]._hr_employee_apply_access_domain(
                list(domain or []), model_name="hr.employee"
            )
            if extra is not None:
                domain = list(Domain(domain or []) & extra)
        return super()._read_group(
            domain, groupby, aggregates, having, offset=offset, limit=limit, order=order
        )
