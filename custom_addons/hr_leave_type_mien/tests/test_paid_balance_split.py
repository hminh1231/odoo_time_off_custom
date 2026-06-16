from datetime import date

from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestPaidBalanceSplit(TransactionCase):
    def test_zero_paid_balance_assigns_all_days_to_o(self):
        Leave = self.env["hr.leave"]

        segments, paid_used = Leave._monthly_mien_split_plan_for_month(
            days_before=0,
            date_from=date(2026, 6, 1),
            date_to=date(2026, 6, 5),
            paid_budget=0,
            monthly_cap=10,
        )

        self.assertEqual(segments, [("o", date(2026, 6, 1), date(2026, 6, 5))])
        self.assertEqual(paid_used, 0)

    def test_days_exceeding_paid_balance_are_assigned_to_o(self):
        Leave = self.env["hr.leave"]

        segments, paid_used = Leave._monthly_mien_split_plan_for_month(
            days_before=0,
            date_from=date(2026, 6, 1),
            date_to=date(2026, 6, 5),
            paid_budget=4,
            monthly_cap=10,
        )

        self.assertEqual(
            segments,
            [
                ("p1", date(2026, 6, 1), date(2026, 6, 1)),
                ("p2", date(2026, 6, 2), date(2026, 6, 4)),
                ("o", date(2026, 6, 5), date(2026, 6, 5)),
            ],
        )
        self.assertEqual(paid_used, 4)

    def test_monthly_cap_still_limits_paid_days(self):
        Leave = self.env["hr.leave"]

        segments, paid_used = Leave._monthly_mien_split_plan_for_month(
            days_before=0,
            date_from=date(2026, 6, 1),
            date_to=date(2026, 6, 5),
            paid_budget=4,
            monthly_cap=3,
        )

        self.assertEqual(
            segments,
            [
                ("p1", date(2026, 6, 1), date(2026, 6, 1)),
                ("p2", date(2026, 6, 2), date(2026, 6, 3)),
                ("o", date(2026, 6, 4), date(2026, 6, 5)),
            ],
        )
        self.assertEqual(paid_used, 3)

    def test_maternity_license_on_first_day_splits_first_day_to_paid(self):
        employee = self.env["hr.employee"].create(
            {
                "name": "Maternity First Day",
                "thai_san_ngay_cap_phep": date(2026, 2, 1),
            }
        )

        segments = self.env["hr.leave"]._maternity_leave_split_plan(
            employee,
            date(2026, 2, 10),
            date(2026, 2, 12),
        )

        self.assertEqual(
            segments,
            [
                ("maternity_p", date(2026, 2, 10), date(2026, 2, 10)),
                ("o", date(2026, 2, 11), date(2026, 2, 12)),
            ],
        )

    def test_maternity_license_on_other_day_assigns_all_to_unpaid(self):
        employee = self.env["hr.employee"].create(
            {
                "name": "Maternity Other Day",
                "thai_san_ngay_cap_phep": date(2026, 2, 2),
            }
        )

        segments = self.env["hr.leave"]._maternity_leave_split_plan(
            employee,
            date(2026, 2, 10),
            date(2026, 2, 12),
        )

        self.assertEqual(
            segments,
            [("o", date(2026, 2, 10), date(2026, 2, 12))],
        )
