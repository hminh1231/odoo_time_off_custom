from datetime import date, datetime, time
from unittest.mock import patch

from odoo import Command
from odoo.addons.hr.models.hr_employee import _ALLOW_READ_HR_EMPLOYEE
from odoo.exceptions import AccessError
from odoo.fields import Domain
from odoo.tests import TransactionCase, new_test_user, tagged


@tagged("post_install", "-at_install")
class TestHandoverEmployeeRead(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = new_test_user(
            cls.env,
            login="handover-employee-read",
            groups="base.group_user",
        )
        cls.handover_user = new_test_user(
            cls.env,
            login="handover-private-reason-read",
            groups="base.group_user",
        )
        cls.recipient = cls.env["hr.employee"].create(
            {
                "name": "Restricted Handover Recipient",
                "company_id": cls.user.company_id.id,
            }
        )
        cls.handover_employee = cls.env["hr.employee"].create(
            {
                "name": "Base Handover Recipient",
                "user_id": cls.handover_user.id,
                "company_id": cls.handover_user.company_id.id,
            }
        )
        cls.requester_employee = cls.env["hr.employee"].create(
            {
                "name": "Handover Requester",
                "user_id": cls.user.id,
                "company_id": cls.user.company_id.id,
            }
        )
        cls.leave_type = cls.env["hr.leave.type"].create(
            {
                "name": "Handover overlap test",
                "requires_allocation": False,
                "company_id": cls.user.company_id.id,
            }
        )

    def test_handover_onchange_uses_internal_employee_read_context(self):
        Leave = self.env["hr.leave"].with_user(self.user)

        self.assertTrue(
            Leave._is_handover_onchange(["handover_acceptance_ids"])
        )
        self.assertTrue(
            Leave._is_handover_onchange(
                ["handover_acceptance_ids.employee_id"]
            )
        )
        self.assertFalse(Leave._is_handover_onchange(["request_date_from"]))

        self.assertTrue(
            Leave._needs_handover_read_context(["request_date_from"], {})
        )
        self.assertTrue(
            Leave._needs_handover_read_context(
                [],
                {"handover_acceptance_ids": {"fields": {}}},
            )
        )
        self.assertFalse(
            Leave._needs_handover_read_context(["name"], {"name": {}})
        )

        handover_leave = Leave._with_handover_employee_read_context()
        self.assertIs(
            handover_leave.env.context.get("_allow_read_hr_employee"),
            _ALLOW_READ_HR_EMPLOYEE,
        )

        access_mixin_type = type(self.env["hr.employee.access.mixin"])
        with patch.object(
            access_mixin_type,
            "_hr_employee_access_extra_domain",
            autospec=True,
            return_value=Domain.FALSE,
        ):
            Employee = self.env["hr.employee"].with_user(self.user)
            self.assertFalse(
                Employee.search([("id", "=", self.recipient.id)])
            )

            internal_recipient = handover_leave.env["hr.employee"].browse(
                self.recipient.id
            )
            internal_recipient.invalidate_recordset(["name"])
            self.assertEqual(
                internal_recipient.name,
                self.recipient.name,
            )

    def test_handover_onchange_marks_nested_employee_serialization(self):
        Leave = self.env["hr.leave"]
        original = {
            "handover_employee_ids": {"fields": {"display_name": {}}},
            "handover_acceptance_ids": {
                "fields": {
                    "employee_id": {"fields": {"display_name": {}}},
                    "handover_work_content": {},
                }
            },
            "name": {},
        }

        prepared = Leave._handover_onchange_fields_spec(original)

        self.assertIs(
            prepared["handover_employee_ids"]["context"][
                "_allow_read_hr_employee"
            ],
            _ALLOW_READ_HR_EMPLOYEE,
        )
        self.assertIs(
            prepared["handover_acceptance_ids"]["context"][
                "_allow_read_hr_employee"
            ],
            _ALLOW_READ_HR_EMPLOYEE,
        )
        self.assertIs(
            prepared["handover_acceptance_ids"]["fields"]["employee_id"][
                "context"
            ]["_allow_read_hr_employee"],
            _ALLOW_READ_HR_EMPLOYEE,
        )
        self.assertNotIn("context", original["handover_employee_ids"])
        self.assertNotIn(
            "context",
            original["handover_acceptance_ids"]["fields"]["employee_id"],
        )

    def test_handover_web_read_uses_internal_employee_read_context(self):
        overlap_day = date(2026, 6, 27)
        start_dt = datetime.combine(overlap_day, time(7, 0))
        end_dt = datetime.combine(overlap_day, time(19, 0))
        leave = self.env["hr.leave"].sudo().create(
            {
                "name": "Handover approval read",
                "employee_id": self.requester_employee.id,
                "holiday_status_id": self.leave_type.id,
                "request_date_from": overlap_day,
                "request_date_to": overlap_day,
                "date_from": start_dt,
                "date_to": end_dt,
                "handover_employee_ids": [Command.set([self.recipient.id])],
                "state": "confirm",
            }
        )
        Leave = self.env["hr.leave"].with_user(self.user)
        spec = {
            "handover_acceptance_ids": {
                "fields": {
                    "employee_id": {"fields": {"display_name": {}}},
                    "handover_work_content": {},
                }
            }
        }
        access_mixin_type = type(self.env["hr.employee.access.mixin"])
        with patch.object(
            access_mixin_type,
            "_hr_employee_access_extra_domain",
            autospec=True,
            return_value=Domain.FALSE,
        ):
            Employee = self.env["hr.employee"].with_user(self.user)
            self.assertFalse(
                Employee.search([("id", "=", self.recipient.id)])
            )
            data = Leave.browse(leave.id).web_read(spec)
        self.assertEqual(
            data[0]["handover_acceptance_ids"][0]["employee_id"]["display_name"],
            self.recipient.display_name,
        )

    def test_handover_recipient_can_build_approval_notice_without_private_name_group(self):
        leave_day = date(2026, 6, 28)
        start_dt = datetime.combine(leave_day, time(7, 0))
        end_dt = datetime.combine(leave_day, time(19, 0))
        leave = self.env["hr.leave"].sudo().create(
            {
                "private_name": "Sensitive private reason",
                "employee_id": self.requester_employee.id,
                "holiday_status_id": self.leave_type.id,
                "request_date_from": leave_day,
                "request_date_to": leave_day,
                "date_from": start_dt,
                "date_to": end_dt,
                "handover_employee_ids": [Command.set([self.handover_employee.id])],
                "state": "confirm",
            }
        )

        self.assertFalse(
            self.handover_user.has_group("hr_holidays.group_hr_holidays_user")
        )
        handover_leave = self.env["hr.leave"].with_user(self.handover_user).browse(leave.id)
        with self.assertRaises(AccessError):
            handover_leave.private_name

        details = handover_leave._get_approval_bot_leave_notification_details()

        self.assertEqual(details["reason"], "Sensitive private reason")

    def test_unavailable_handover_employees_on_overlapping_dates(self):
        overlap_day = date(2026, 6, 26)
        start_dt = datetime.combine(overlap_day, time(7, 0))
        end_dt = datetime.combine(overlap_day, time(19, 0))

        self.env["hr.leave"].sudo().create(
            {
                "name": "Colleague leave",
                "employee_id": self.recipient.id,
                "holiday_status_id": self.leave_type.id,
                "request_date_from": overlap_day,
                "request_date_to": overlap_day,
                "date_from": start_dt,
                "date_to": end_dt,
                "state": "confirm",
            }
        )

        Leave = self.env["hr.leave"].with_user(self.user)
        draft = Leave.new(
            {
                "employee_id": self.requester_employee.id,
                "holiday_status_id": self.leave_type.id,
                "request_date_from": overlap_day,
                "request_date_to": overlap_day,
                "date_from": start_dt,
                "date_to": end_dt,
            }
        )

        access_mixin_type = type(self.env["hr.employee.access.mixin"])
        with patch.object(
            access_mixin_type,
            "_hr_employee_access_extra_domain",
            autospec=True,
            return_value=Domain.FALSE,
        ):
            Employee = self.env["hr.employee"].with_user(self.user)
            self.assertFalse(
                Employee.search([("id", "=", self.recipient.id)])
            )

            draft._compute_unavailable_handover_employee_id_list()
            unavailable = draft._unavailable_handover_employees()
            self.assertIn(self.recipient.id, unavailable.ids)
            self.assertEqual(
                unavailable.mapped("name"),
                [self.recipient.name],
            )

    def test_unavailable_handover_onchange_allows_handover_selection(self):
        overlap_day = date(2026, 6, 29)
        start_dt = datetime.combine(overlap_day, time(7, 0))
        end_dt = datetime.combine(overlap_day, time(19, 0))

        self.env["hr.leave"].sudo().create(
            {
                "name": "Out-of-scope colleague leave",
                "employee_id": self.recipient.id,
                "holiday_status_id": self.leave_type.id,
                "request_date_from": overlap_day,
                "request_date_to": overlap_day,
                "date_from": start_dt,
                "date_to": end_dt,
                "state": "validate",
            }
        )

        Leave = self.env["hr.leave"].with_user(self.user)
        values = {
            "employee_id": self.requester_employee.id,
            "holiday_status_id": self.leave_type.id,
            "request_date_from": overlap_day.isoformat(),
            "request_date_to": overlap_day.isoformat(),
            "date_from": start_dt.strftime("%Y-%m-%d %H:%M:%S"),
            "date_to": end_dt.strftime("%Y-%m-%d %H:%M:%S"),
            "handover_acceptance_ids": [
                Command.create(
                    {
                        "employee_id": self.handover_employee.id,
                        "handover_work_content": "Coverage",
                    }
                ),
            ],
        }
        fields_spec = {
            "handover_acceptance_ids": {
                "fields": {
                    "employee_id": {"fields": {"display_name": {}}},
                    "handover_work_content": {},
                }
            },
            "unavailable_handover_employee_id_list": {},
        }
        access_mixin_type = type(self.env["hr.employee.access.mixin"])
        with patch.object(
            access_mixin_type,
            "_hr_employee_access_extra_domain",
            autospec=True,
            return_value=Domain.FALSE,
        ):
            Leave.onchange(values, ["handover_acceptance_ids"], fields_spec)

    def test_asm_rsm_leave_auto_skips_work_handover(self):
        leave_day = date(2026, 7, 6)
        start_dt = datetime.combine(leave_day, time(7, 0))
        end_dt = datetime.combine(leave_day, time(19, 0))
        for job_title in ("asm", "rsm"):
            employee = self.env["hr.employee"].create(
                {
                    "name": "%s Requester" % job_title.upper(),
                    "company_id": self.user.company_id.id,
                    "job_title": job_title,
                }
            )

            leave = self.env["hr.leave"].create(
                {
                    "name": "%s leave without handover" % job_title.upper(),
                    "employee_id": employee.id,
                    "holiday_status_id": self.leave_type.id,
                    "request_date_from": leave_day,
                    "request_date_to": leave_day,
                    "date_from": start_dt,
                    "date_to": end_dt,
                }
            )

            self.assertTrue(leave.skip_work_handover)
            self.assertTrue(leave._should_skip_work_handover())

    def test_regular_leave_does_not_auto_skip_work_handover(self):
        leave_day = date(2026, 7, 7)
        start_dt = datetime.combine(leave_day, time(7, 0))
        end_dt = datetime.combine(leave_day, time(19, 0))
        regular_employee = self.env["hr.employee"].create(
            {
                "name": "Regular Requester",
                "company_id": self.user.company_id.id,
                "job_title": "nhân viên vp",
            }
        )

        leave = self.env["hr.leave"].create(
            {
                "name": "Regular leave without handover",
                "employee_id": regular_employee.id,
                "holiday_status_id": self.leave_type.id,
                "request_date_from": leave_day,
                "request_date_to": leave_day,
                "date_from": start_dt,
                "date_to": end_dt,
            }
        )

        self.assertFalse(leave.skip_work_handover)
        self.assertFalse(leave._should_skip_work_handover())

    def test_store_region_non_leader_auto_skips_work_handover(self):
        leave_day = date(2026, 7, 8)
        start_dt = datetime.combine(leave_day, time(7, 0))
        end_dt = datetime.combine(leave_day, time(19, 0))
        for mien, job_title in (
            ("Bắc", "nhân viên ch"),
            ("Nam", "giám sát"),
            ("ĐTT", "asm"),
        ):
            employee = self.env["hr.employee"].create(
                {
                    "name": "%s %s" % (mien, job_title),
                    "company_id": self.user.company_id.id,
                    "mien": mien,
                    "job_title": job_title,
                }
            )
            leave = self.env["hr.leave"].create(
                {
                    "name": "%s leave without handover" % mien,
                    "employee_id": employee.id,
                    "holiday_status_id": self.leave_type.id,
                    "request_date_from": leave_day,
                    "request_date_to": leave_day,
                    "date_from": start_dt,
                    "date_to": end_dt,
                }
            )
            self.assertTrue(
                leave.skip_work_handover,
                "%s / %s should auto-skip handover" % (mien, job_title),
            )
            self.assertTrue(leave._should_skip_work_handover())

    def test_store_region_leader_requires_work_handover(self):
        leave_day = date(2026, 7, 9)
        start_dt = datetime.combine(leave_day, time(7, 0))
        end_dt = datetime.combine(leave_day, time(19, 0))
        for job_title in ("nhóm trưởng", "cửa hàng trưởng"):
            employee = self.env["hr.employee"].create(
                {
                    "name": "%s Leader" % job_title,
                    "company_id": self.user.company_id.id,
                    "mien": "Bắc",
                    "job_title": job_title,
                }
            )
            leave = self.env["hr.leave"].create(
                {
                    "name": "%s leave requires handover" % job_title,
                    "employee_id": employee.id,
                    "holiday_status_id": self.leave_type.id,
                    "request_date_from": leave_day,
                    "request_date_to": leave_day,
                    "date_from": start_dt,
                    "date_to": end_dt,
                }
            )
            self.assertFalse(leave.skip_work_handover)
            self.assertFalse(leave._should_skip_work_handover())
            self.assertFalse(leave.can_skip_work_handover)
