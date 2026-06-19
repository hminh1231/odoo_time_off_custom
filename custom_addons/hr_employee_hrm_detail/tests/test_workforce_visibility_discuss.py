# -*- coding: utf-8 -*-

from odoo.tests import TransactionCase, new_test_user, tagged


@tagged("post_install", "-at_install")
class TestWorkforceVisibilityDiscuss(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        company = cls.env.company
        StoreCode = cls.env["hr.store.code"]
        cls.store_nam_a = StoreCode.search([("code", "=", "TEST-NAM-A")], limit=1)
        if not cls.store_nam_a:
            cls.env["hr.store"].create(
                {"name": "Test Store Nam A", "code": "TEST-NAM-A", "mien": "Nam"}
            )
            cls.store_nam_a = StoreCode.search([("code", "=", "TEST-NAM-A")], limit=1)
        cls.store_nam_b = StoreCode.search([("code", "=", "TEST-NAM-B")], limit=1)
        if not cls.store_nam_b:
            cls.env["hr.store"].create(
                {"name": "Test Store Nam B", "code": "TEST-NAM-B", "mien": "Nam"}
            )
            cls.store_nam_b = StoreCode.search([("code", "=", "TEST-NAM-B")], limit=1)

        cls.vp_user = new_test_user(
            cls.env, login="workforce_vp_officer", groups="hr.group_hr_user"
        )
        cls.vp_officer = cls.env["hr.employee"].create(
            {
                "name": "VP Officer",
                "user_id": cls.vp_user.id,
                "company_id": company.id,
                "mien": "VP",
                "employee_visibility": "office",
            }
        )
        cls.vp_colleague = cls.env["hr.employee"].create(
            {
                "name": "VP Colleague",
                "company_id": company.id,
                "mien": "VP",
                "employee_visibility": "office",
            }
        )

        cls.ch_user = new_test_user(
            cls.env, login="workforce_ch_officer", groups="hr.group_hr_user"
        )
        cls.ch_officer = cls.env["hr.employee"].create(
            {
                "name": "CH Officer Nam",
                "user_id": cls.ch_user.id,
                "company_id": company.id,
                "mien": "Nam",
                "ma_bo_phan_id": cls.store_nam_a.id,
                "employee_visibility": "store",
            }
        )
        cls.ch_colleague = cls.env["hr.employee"].create(
            {
                "name": "CH Colleague Nam Same Store",
                "company_id": company.id,
                "mien": "Nam",
                "ma_bo_phan_id": cls.store_nam_a.id,
                "employee_visibility": "store",
            }
        )
        cls.ch_other_store = cls.env["hr.employee"].create(
            {
                "name": "CH Colleague Nam Other Store",
                "company_id": company.id,
                "mien": "Nam",
                "ma_bo_phan_id": cls.store_nam_b.id,
                "employee_visibility": "store",
            }
        )
        cls.ch_bac_colleague = cls.env["hr.employee"].create(
            {
                "name": "CH Colleague Bac",
                "company_id": company.id,
                "mien": "Bắc",
                "employee_visibility": "store",
            }
        )

        cls.admin_user = new_test_user(
            cls.env, login="workforce_hr_admin", groups="hr.group_hr_manager"
        )

        # Visibility policies (independent of permission groups).
        cls.vp_user.visibility_policy = "region"
        cls.ch_user.visibility_policy = "region"
        cls.env.flush_all()
        cls.vp_user.invalidate_recordset(["employee_mien", "group_ids"])
        cls.ch_user.invalidate_recordset(["employee_mien", "group_ids"])

    def test_discuss_layer_not_filtered_by_hr_visibility(self):
        mixin = self.env["hr.employee.access.mixin"]
        self.assertFalse(mixin._hr_employee_discuss_access_applies(self.vp_user))
        self.assertFalse(mixin._hr_employee_discuss_access_applies(self.ch_user))

    def test_region_policy_vp_sees_only_vp_mien(self):
        self.assertEqual(self.vp_user.employee_mien, "VP")
        visible_ids = set(
            self.env["hr.employee"].with_user(self.vp_user).search([]).ids
        )
        self.assertIn(self.vp_officer.id, visible_ids)
        self.assertIn(self.vp_colleague.id, visible_ids)
        self.assertNotIn(self.ch_colleague.id, visible_ids)
        self.assertNotIn(self.ch_bac_colleague.id, visible_ids)

    def test_region_policy_ch_sees_same_mien_only(self):
        self.assertEqual(self.ch_user.employee_mien, "Nam")
        visible_ids = set(
            self.env["hr.employee"].with_user(self.ch_user).search([]).ids
        )
        self.assertIn(self.ch_officer.id, visible_ids)
        self.assertIn(self.ch_colleague.id, visible_ids)
        self.assertIn(self.ch_other_store.id, visible_ids)
        self.assertNotIn(self.ch_bac_colleague.id, visible_ids)
        self.assertNotIn(self.vp_colleague.id, visible_ids)

    def test_self_policy_sees_only_self(self):
        self.ch_user.visibility_policy = "self"
        self.env.flush_all()
        self.ch_user.invalidate_recordset(["visibility_policy"])
        visible_ids = set(
            self.env["hr.employee"].with_user(self.ch_user).search([]).ids
        )
        self.assertIn(self.ch_officer.id, visible_ids)
        self.assertNotIn(self.ch_colleague.id, visible_ids)
        self.assertNotIn(self.ch_other_store.id, visible_ids)

    def test_ma_bo_phan_policy_sees_only_same_code_and_self(self):
        # ch_officer Mã bộ phận = NAM-A: sees NAM-A colleagues + self,
        # but not NAM-B (same Miền) nor other Miền.
        self.ch_user.write({"visibility_policy": "ma_bo_phan"})
        self.env.flush_all()
        self.ch_user.invalidate_recordset(
            ["visibility_policy", "employee_ma_bo_phan_id"]
        )
        self.assertEqual(
            self.ch_user.employee_ma_bo_phan_id.id, self.store_nam_a.id
        )
        visible_ids = set(
            self.env["hr.employee"].with_user(self.ch_user).search([]).ids
        )
        self.assertIn(self.ch_officer.id, visible_ids)  # self / same code
        self.assertIn(self.ch_colleague.id, visible_ids)  # code NAM-A
        self.assertNotIn(self.ch_other_store.id, visible_ids)  # code NAM-B
        self.assertNotIn(self.ch_bac_colleague.id, visible_ids)
        self.assertNotIn(self.vp_colleague.id, visible_ids)

    def test_assigned_policy_sees_only_assigned_codes_and_self(self):
        # Assign store code NAM-B: ch_user should see employees of that code + self.
        self.ch_user.write(
            {
                "visibility_policy": "assigned",
                "assigned_ma_bo_phan_ids": [(6, 0, [self.store_nam_b.id])],
            }
        )
        self.env.flush_all()
        self.ch_user.invalidate_recordset(
            ["visibility_policy", "assigned_ma_bo_phan_ids"]
        )
        visible_ids = set(
            self.env["hr.employee"].with_user(self.ch_user).search([]).ids
        )
        self.assertIn(self.ch_officer.id, visible_ids)  # self
        self.assertIn(self.ch_other_store.id, visible_ids)  # code NAM-B
        self.assertNotIn(self.ch_colleague.id, visible_ids)  # code NAM-A
        self.assertNotIn(self.vp_colleague.id, visible_ids)

    def test_admin_sees_all_profiles(self):
        visible_ids = set(
            self.env["hr.employee"].with_user(self.admin_user).search([]).ids
        )
        self.assertIn(self.vp_colleague.id, visible_ids)
        self.assertIn(self.ch_colleague.id, visible_ids)
        self.assertIn(self.ch_bac_colleague.id, visible_ids)

    def test_discuss_can_find_cross_group_partner(self):
        partner_model = self.env["res.partner"].with_user(self.vp_user)
        domain = [
            ("user_ids", "!=", False),
            ("user_ids.share", "=", False),
            ("id", "=", self.ch_user.partner_id.id),
        ]
        self.assertTrue(partner_model.search_count(domain))
