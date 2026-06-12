from datetime import date

from dateutil.relativedelta import relativedelta

from odoo import fields
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestMonthlyLeaveAppointmentBonus(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.today = fields.Date.today()
        cls.join_date = cls.today - relativedelta(years=4, days=1)

    def _create_employee(self, **extra):
        values = {
            "name": "Tenure Bonus Employee",
            "mien": "Nam",
            "ngay_vao_lam": self.join_date,
            "tong_so_phep": 0.0,
        }
        if "job_title" in self.env["hr.employee"]._fields:
            values["job_title"] = "nhóm trưởng"
        else:
            values["job_id"] = self.env["hr.job"].create({"name": "Nhóm trưởng"}).id
        values.update(extra)
        return self.env["hr.employee"].create(values)

    def test_create_with_qualifying_dates_grants_bonus(self):
        employee = self._create_employee(ngay_bo_nhiem=date(2026, 3, 10))
        self.assertEqual(employee.tong_so_phep, 1.0)
        self.assertEqual(
            employee.last_monthly_leave_bonus_date,
            self.today.replace(day=1),
        )

    def test_appointment_before_day_15_grants_bonus_on_save(self):
        employee = self._create_employee()

        employee.write({"ngay_bo_nhiem": date(2026, 3, 10)})

        self.assertEqual(employee.tong_so_phep, 1.0)

    def test_appointment_on_day_15_blocks_bonus(self):
        employee = self._create_employee()

        employee.write({"ngay_bo_nhiem": date(2026, 3, 15)})

        self.assertEqual(employee.tong_so_phep, 0.0)

    def test_missing_appointment_blocks_bonus(self):
        employee = self._create_employee()

        employee.with_context(monthly_leave_bonus_date=date(2026, 6, 1)).write(
            {"tong_so_phep": 1.0}
        )

        self.assertEqual(employee.tong_so_phep, 0.0)

    def test_legacy_current_month_bonus_is_reversed_on_departure(self):
        employee = self._create_employee(ngay_bo_nhiem=date(2026, 3, 10))
        employee.with_context(
            skip_departure_monthly_leave_cutoff=True,
            skip_departure_monthly_leave_reversal=True,
        ).write({"last_monthly_leave_bonus_date": False})

        employee.with_context(
            monthly_leave_bonus_date=self.today.replace(day=1)
        ).write(
            {
                "ngay_nghi_viec": self.today.replace(day=15),
            }
        )

        self.assertEqual(employee.tong_so_phep, 0.0)

    def test_under_four_years_blocks_bonus(self):
        employee = self._create_employee(
            ngay_vao_lam=self.today - relativedelta(years=3),
        )

        employee.write({"ngay_bo_nhiem": date(2026, 3, 10)})

        self.assertEqual(employee.tong_so_phep, 0.0)

    def test_ma_bo_phan_mien_and_job_title_grant_bonus_on_create(self):
        store = self.env["hr.store.code"].search([("code", "=", "LUG_KDV")], limit=1)
        if not store:
            self.skipTest("LUG_KDV store code is not configured")
        employee = self._create_employee(
            mien=False,
            ma_bo_phan_id=store.id,
            ngay_bo_nhiem=date(2026, 3, 10),
        )
        self.assertEqual(employee.tong_so_phep, 1.0)

    def test_cron_applies_bonus_for_eligible_employee(self):
        employee = self._create_employee(
            ngay_vao_lam=date(2020, 1, 1),
            ngay_bo_nhiem=date(2020, 1, 5),
        )

        self.assertEqual(employee.tong_so_phep, 1.0)

        self.env["hr.employee"].cron_apply_monthly_leave_bonus()

        self.assertEqual(employee.tong_so_phep, 2.0)
        self.assertEqual(
            employee.last_monthly_leave_bonus_date,
            self.today.replace(day=1),
        )
