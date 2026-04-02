from dateutil.relativedelta import relativedelta

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class HrEmployee(models.Model):
    _inherit = "hr.employee"

    def _get_hr_responsible_domain(self):
        return "[('share', '=', False), ('company_ids', 'in', company_id), ('all_group_ids', 'in', %s)]" % self.env.ref("hr.group_hr_user").id

    additional_hr_responsible_ids = fields.Many2many(
        "res.users",
        "hr_employee_extra_responsible_rel",
        "employee_id",
        "user_id",
        string="Additional HR Responsible",
        help="Additional users responsible for this employee.",
        groups="hr.group_hr_user",
        domain=_get_hr_responsible_domain,
    )
    hr_responsible_ids = fields.Many2many(
        "res.users",
        compute="_compute_hr_responsible_ids",
        inverse="_inverse_hr_responsible_ids",
        string="HR Responsibles",
        groups="hr.group_hr_user",
        domain=_get_hr_responsible_domain,
    )

    @api.depends("hr_responsible_id", "additional_hr_responsible_ids")
    def _compute_hr_responsible_ids(self):
        for employee in self:
            employee.hr_responsible_ids = employee.hr_responsible_id | employee.additional_hr_responsible_ids

    def _inverse_hr_responsible_ids(self):
        for employee in self:
            selected_users = employee.hr_responsible_ids
            if not selected_users:
                continue

            if employee.hr_responsible_id in selected_users:
                primary_user = employee.hr_responsible_id
            else:
                primary_user = selected_users[0]

            employee.hr_responsible_id = primary_user
            employee.additional_hr_responsible_ids = selected_users - primary_user

    @api.constrains("hr_responsible_id", "additional_hr_responsible_ids")
    def _check_hr_responsible_ids_count(self):
        for employee in self:
            count = len(employee.hr_responsible_id | employee.additional_hr_responsible_ids)
            if count == 0:
                raise ValidationError(_("At least one HR Responsible is required."))
            if count > 6:
                raise ValidationError(_("You can assign at most 6 HR Responsible users per employee."))

    @api.model
    def notify_expiring_contract_work_permit(self):
        result = super().notify_expiring_contract_work_permit()

        companies = self.env["res.company"].search([])
        employees_contract_expiring = self.env["hr.employee"]
        employees_work_permit_expiring = self.env["hr.employee"]

        for company in companies:
            employees_contract_expiring += self.search([
                ("company_id", "=", company.id),
                ("contract_date_start", "!=", False),
                ("contract_date_start", "<", fields.Date.today()),
                ("contract_date_end", "=", fields.Date.today() + relativedelta(days=company.contract_expiration_notice_period)),
            ])
            employees_work_permit_expiring += self.search([
                ("company_id", "=", company.id),
                ("work_permit_expiration_date", "!=", False),
                ("work_permit_expiration_date", "=", fields.Date.today() + relativedelta(days=company.work_permit_expiration_notice_period)),
            ])

        for employee in employees_contract_expiring:
            extra_users = employee.additional_hr_responsible_ids
            for user in extra_users:
                employee.with_context(mail_activity_quick_update=True).activity_schedule(
                    "mail.mail_activity_data_todo",
                    employee.contract_date_end,
                    _("The contract of %s is about to expire.", employee.name),
                    user_id=user.id,
                )

        for employee in employees_work_permit_expiring:
            extra_users = employee.additional_hr_responsible_ids
            for user in extra_users:
                employee.with_context(mail_activity_quick_update=True).activity_schedule(
                    "mail.mail_activity_data_todo",
                    employee.work_permit_expiration_date,
                    _("The work permit of %s is about to expire.", employee.name),
                    user_id=user.id,
                )

        return result
