# -*- coding: utf-8 -*-

from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestHrStore(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Store = cls.env['hr.store']
        cls.StorePlace = cls.env['hr.store.place']
        cls.Employee = cls.env['hr.employee']

        # Create store places
        cls.place_go = cls.StorePlace.create({
            'name': 'GO Mall',
            'code': 'GO_TEST',
            'sequence': 10,
        })
        cls.place_tttm = cls.StorePlace.create({
            'name': 'TTTM Vincom',
            'code': 'TTTM_TEST',
            'sequence': 20,
        })

        # Create employees
        cls.manager_1 = cls.Employee.create({
            'name': 'Store Manager 1 Test',
        })
        cls.manager_2 = cls.Employee.create({
            'name': 'Store Manager 2 Test',
        })
        cls.accountant_1 = cls.Employee.create({
            'name': 'Accountant 1 Test',
        })
        cls.accountant_2 = cls.Employee.create({
            'name': 'Accountant 2 Test',
        })

    def test_store_place_creation_and_count(self):
        """Test hr.store.place creation and store_count computation."""
        store = self.Store.create({
            'name': 'Store 1',
            'store_place_id': self.place_go.id,
            'manager_ids': [(6, 0, [self.manager_1.id])],
        })
        self.place_go._compute_store_count()
        self.assertEqual(self.place_go.store_count, 1)
        self.assertIn(store, self.place_go.store_ids)

        action = self.place_go.action_view_stores()
        self.assertEqual(action.get('domain'), [('store_place_id', '=', self.place_go.id)])

    def test_store_place_backward_compatibility(self):
        """Test store_place compute and inverse synchronization."""
        store = self.Store.create({
            'name': 'Store Compatibility Test',
            'store_place_id': self.place_tttm.id,
        })
        # Compute store_place string
        self.assertEqual(store.store_place, 'TTTM Vincom')

        # Inverse write on store_place
        store.write({'store_place': 'GO Mall'})
        self.assertEqual(store.store_place_id, self.place_go)

    def test_store_managers_multi_choice(self):
        """Test adding multiple managers to a store and verifying inverse relation on employee."""
        store = self.Store.create({
            'name': 'Store Multi Managers',
            'store_place_id': self.place_go.id,
            'manager_ids': [(6, 0, [self.manager_1.id, self.manager_2.id])],
        })

        self.assertEqual(len(store.manager_ids), 2)
        self.assertIn(self.manager_1, store.manager_ids)
        self.assertIn(self.manager_2, store.manager_ids)

        # Check backward-compatible manager_id (points to first manager)
        self.assertEqual(store.manager_id, self.manager_1)

        # Check inverse relation on hr.employee (managed_store_ids)
        self.assertIn(store, self.manager_1.managed_store_ids)
        self.assertIn(store, self.manager_2.managed_store_ids)

    def test_store_accountants_many2many(self):
        """Test adding multiple accountants to a store and verifying inverse relation on employee."""
        store = self.Store.create({
            'name': 'Store With Accountants',
            'store_place_id': self.place_go.id,
            'manager_ids': [(6, 0, [self.manager_1.id])],
            'accountant_ids': [(6, 0, [self.accountant_1.id, self.accountant_2.id])],
        })

        self.assertEqual(len(store.accountant_ids), 2)
        self.assertIn(self.accountant_1, store.accountant_ids)
        self.assertIn(self.accountant_2, store.accountant_ids)

        # Check inverse relation on hr.employee
        self.assertIn(store, self.accountant_1.accountant_store_ids)
        self.assertIn(store, self.accountant_2.accountant_store_ids)
        self.assertNotIn(store, self.manager_1.accountant_store_ids)

    def test_web_read_with_managers_and_accountants(self):
        """Test web_read method returns without errors when manager_ids and accountant_ids are specified."""
        store = self.Store.create({
            'name': 'Store Web Read Test',
            'manager_ids': [(6, 0, [self.manager_1.id, self.manager_2.id])],
            'accountant_ids': [(6, 0, [self.accountant_1.id])],
        })
        spec = {
            'name': {},
            'manager_ids': {'fields': {'display_name': {}}},
            'manager_id': {'fields': {'display_name': {}}},
            'accountant_ids': {'fields': {'display_name': {}}},
            'store_place_id': {'fields': {'display_name': {}}},
        }
        res = store.web_read(spec)
        self.assertTrue(res)
        self.assertEqual(res[0]['name'], 'Store Web Read Test')
