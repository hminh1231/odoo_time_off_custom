from odoo import api, models

# Non-sensitive hr.version fields needed by time-off / org-chart flows (not wage/payroll).
_TIMEOFF_VERSION_READ_FIELDS = frozenset(
    {
        "job_title",
        "job_id",
        "resource_calendar_id",
        "date_version",
        "employee_id",
        "company_id",
        "department_id",
        "active",
        "name",
        "date_start",
        "date_end",
        "contract_date_start",
        "contract_date_end",
    }
)


class HrVersionTimeoff(models.Model):
    _inherit = "hr.version"

    def _check_access(self, operation):
        """Allow time-off users to read contract versions they need."""
        if operation == "read" and not self.env.su:
            user = self.env.user
            if user.has_group("hr.group_hr_user") and not user.has_group(
                "hr.group_hr_manager"
            ):
                if not self:
                    return None
                employee_ids = self.mapped("employee_id").ids
                if employee_ids:
                    visible_count = self.env["hr.employee"].search_count(
                        [("id", "in", employee_ids)]
                    )
                    if visible_count == len(set(employee_ids)):
                        return None
            elif not user.has_group("hr.group_hr_user"):
                own = user.employee_id
                if own:
                    if not self:
                        return None
                    if not self.filtered(
                        lambda version: version.employee_id.id != own.id
                    ):
                        return None
        return super()._check_access(operation)

    @api.model
    def _has_field_access(self, field, operation):
        """HR officers may read org/time-off fields on contracts but not wage (manager-only)."""
        if (
            operation == "read"
            and not self.env.su
            and field.name in _TIMEOFF_VERSION_READ_FIELDS
            and (
                self.env.user.has_group("hr.group_hr_user")
                or self.env.user.employee_id
            )
        ):
            return True
        return super()._has_field_access(field, operation)
