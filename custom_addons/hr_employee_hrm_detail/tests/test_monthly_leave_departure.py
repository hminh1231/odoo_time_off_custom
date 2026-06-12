from datetime import date

from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestMonthlyLeaveDeparture(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.employee = cls.env["hr.employee"].create(
            {
                "name": "Monthly Leave Cutoff Employee",
                "tong_so_phep": 5,
            }
        )

    def _record_monthly_bonus(self, bonus_date):
        bonus_month = bonus_date.replace(day=1)
        self.employee.with_context(
            skip_departure_monthly_leave_cutoff=True,
        ).write(
            {
                "tong_so_phep": (self.employee.tong_so_phep or 0.0) + 1.0,
                "last_monthly_leave_bonus_date": bonus_month,
            }
        )

    def test_departure_before_day_20_blocks_monthly_bonus(self):
        self.employee.ngay_nghi_viec = date(2026, 10, 15)

        self.employee.with_context(
            monthly_leave_bonus_date=date(2026, 10, 1)
        ).write({"tong_so_phep": 6})

        self.assertEqual(self.employee.tong_so_phep, 5)

    def test_departure_on_day_20_keeps_monthly_bonus(self):
        self.employee.ngay_nghi_viec = date(2026, 10, 20)

        self.employee.with_context(
            monthly_leave_bonus_date=date(2026, 10, 1)
        ).write({"tong_so_phep": 6})

        self.assertEqual(self.employee.tong_so_phep, 6)

    def test_departure_in_another_month_keeps_monthly_bonus(self):
        self.employee.ngay_nghi_viec = date(2026, 11, 15)

        self.employee.with_context(
            monthly_leave_bonus_date=date(2026, 10, 1)
        ).write({"tong_so_phep": 6})

        self.assertEqual(self.employee.tong_so_phep, 6)

    def test_previous_month_bonus_is_not_affected(self):
        self.employee.ngay_nghi_viec = date(2026, 10, 15)

        self.employee.with_context(
            monthly_leave_bonus_date=date(2026, 9, 1)
        ).write({"tong_so_phep": 6})

        self.assertEqual(self.employee.tong_so_phep, 6)

    def test_non_bonus_total_update_is_not_blocked(self):
        self.employee.ngay_nghi_viec = date(2026, 10, 15)

        self.employee.with_context(
            monthly_leave_bonus_date=date(2026, 10, 1)
        ).write({"tong_so_phep": 7})

        self.assertEqual(self.employee.tong_so_phep, 7)

    def test_current_month_departure_before_day_20_deducts_one_day(self):
        self.employee.with_context(
            skip_departure_monthly_leave_cutoff=True,
        ).write({"tong_so_phep": 8})

        self.employee.with_context(
            monthly_leave_bonus_date=date(2026, 6, 12)
        ).write({"ngay_nghi_viec": date(2026, 6, 18)})

        self.assertEqual(self.employee.tong_so_phep, 7)
        self.assertEqual(
            self.employee.departure_monthly_leave_reversal_date,
            date(2026, 6, 1),
        )

    def test_departure_reversal_is_only_applied_once(self):
        employee = self.employee.with_context(
            monthly_leave_bonus_date=date(2026, 10, 1)
        )
        employee.write({"ngay_nghi_viec": date(2026, 10, 15)})

        employee.write({"ngay_nghi_viec": date(2026, 10, 16)})

        self.assertEqual(self.employee.tong_so_phep, 4)

    def test_corrected_early_departure_recomputes_exactly_one_deduction(self):
        employee = self.employee.with_context(
            monthly_leave_bonus_date=date(2026, 10, 1)
        )
        employee.write({"ngay_nghi_viec": date(2026, 10, 15)})

        employee.write({"ngay_nghi_viec": date(2026, 10, 18)})

        self.assertEqual(self.employee.tong_so_phep, 4)
        self.assertEqual(
            self.employee.departure_monthly_leave_reversal_date,
            date(2026, 10, 1),
        )

    def test_corrected_departure_after_cutoff_restores_deduction(self):
        employee = self.employee.with_context(
            monthly_leave_bonus_date=date(2026, 10, 1)
        )
        employee.write({"ngay_nghi_viec": date(2026, 10, 15)})

        employee.write({"ngay_nghi_viec": date(2026, 10, 20)})

        self.assertEqual(self.employee.tong_so_phep, 5)
        self.assertFalse(
            self.employee.departure_monthly_leave_reversal_date
        )

    def test_clearing_departure_date_restores_deduction(self):
        employee = self.employee.with_context(
            monthly_leave_bonus_date=date(2026, 10, 1)
        )
        employee.write({"ngay_nghi_viec": date(2026, 10, 15)})

        employee.write({"ngay_nghi_viec": False})

        self.assertEqual(self.employee.tong_so_phep, 5)
        self.assertFalse(
            self.employee.departure_monthly_leave_reversal_date
        )

    def test_correcting_departure_to_early_date_applies_deduction(self):
        employee = self.employee.with_context(
            monthly_leave_bonus_date=date(2026, 10, 1)
        )
        employee.write({"ngay_nghi_viec": date(2026, 10, 20)})

        employee.write({"ngay_nghi_viec": date(2026, 10, 15)})

        self.assertEqual(self.employee.tong_so_phep, 4)
        self.assertEqual(
            self.employee.departure_monthly_leave_reversal_date,
            date(2026, 10, 1),
        )

    def test_future_departure_does_not_remove_current_month_bonus(self):
        self._record_monthly_bonus(date(2026, 10, 1))

        self.employee.with_context(
            monthly_leave_bonus_date=date(2026, 10, 1)
        ).write({"ngay_nghi_viec": date(2026, 11, 15)})

        self.assertEqual(self.employee.tong_so_phep, 6)

        self.employee.with_context(
            monthly_leave_bonus_date=date(2026, 11, 1)
        ).write({"tong_so_phep": 7})

        self.assertEqual(self.employee.tong_so_phep, 6)
