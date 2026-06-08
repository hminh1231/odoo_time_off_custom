from datetime import date
from unittest.mock import patch

from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestTimeOffRemainingBalance(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.employee = cls.env["hr.employee"].create(
            {
                "name": "Remaining Balance Employee",
                "tong_so_phep": 5,
            }
        )

    def test_summary_period_uses_calendar_year(self):
        self.assertEqual(
            self.employee._time_off_summary_period_bounds(date(2026, 6, 15)),
            (date(2026, 1, 1), date(2026, 12, 31)),
        )

    def test_negative_historical_balance_is_displayed_as_zero(self):
        with patch.object(
            type(self.employee),
            "_get_leave_days_used_for_summary",
            autospec=True,
            return_value=7,
        ):
            self.employee.with_context(
                employees_no_timeoff_write=True,
                employees_no_allowed_employee_ids=self.employee.ids,
            )._compute_time_off_summary()

        self.assertEqual(self.employee.da_su_dung, 7)
        self.assertEqual(self.employee.con_lai, 0)

    def test_projected_negative_balance_is_blocked(self):
        Leave = self.env["hr.leave"]
        with patch.object(
            type(Leave),
            "_con_lai_committed_days",
            autospec=True,
            return_value=5,
        ):
            with self.assertRaises(ValidationError):
                Leave._assert_con_lai_not_negative(self.employee, 1)

    def test_projected_zero_balance_is_allowed(self):
        Leave = self.env["hr.leave"]
        with patch.object(
            type(Leave),
            "_con_lai_committed_days",
            autospec=True,
            return_value=4,
        ):
            Leave._assert_con_lai_not_negative(self.employee, 1)

    def test_date_only_request_days_are_used_for_negative_check(self):
        Leave = self.env["hr.leave"]
        days = Leave._vals_days_for_negative_check(
            {
                "employee_id": self.employee.id,
                "request_date_from": date(2026, 6, 1),
                "request_date_to": date(2026, 6, 5),
            },
            employee=self.employee,
        )

        self.assertEqual(days, 5)

    def test_negative_preview_blocks_when_request_exceeds_remaining(self):
        Leave = self.env["hr.leave"]
        vals = {
            "employee_id": self.employee.id,
            "request_date_from": date(2026, 6, 1),
            "request_date_to": date(2026, 6, 5),
        }
        with patch.object(
            type(Leave),
            "_con_lai_committed_days",
            autospec=True,
            return_value=1,
        ):
            preview = Leave.check_con_lai_negative_block(vals=vals)

        self.assertTrue(preview["blocked"])
        self.assertIn("Không đủ số phép còn lại", preview["title"])
