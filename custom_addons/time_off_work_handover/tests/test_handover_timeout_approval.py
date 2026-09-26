# -*- coding: utf-8 -*-
from datetime import date, datetime, time, timedelta

from odoo import Command, fields
from odoo.exceptions import UserError
from odoo.tests import TransactionCase, new_test_user, tagged


@tagged("post_install", "-at_install")
class TestHandoverTimeoutApproval(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.manager_user = new_test_user(
            cls.env,
            login="handover-manager-user",
            groups="base.group_user,hr_holidays.group_hr_holidays_manager",
        )
        cls.requester_user = new_test_user(
            cls.env,
            login="handover-requester-user",
            groups="base.group_user",
        )
        cls.handover_user = new_test_user(
            cls.env,
            login="handover-recipient-user",
            groups="base.group_user",
        )
        cls.escalation_user = new_test_user(
            cls.env,
            login="handover-escalation-owner",
            groups="base.group_user",
        )
        cls.requester_employee = cls.env["hr.employee"].create(
            {
                "name": "Requester Employee",
                "user_id": cls.requester_user.id,
                "company_id": cls.requester_user.company_id.id,
            }
        )
        cls.handover_employee = cls.env["hr.employee"].create(
            {
                "name": "Handover Colleague",
                "user_id": cls.handover_user.id,
                "company_id": cls.handover_user.company_id.id,
            }
        )
        cls.leave_type = cls.env["hr.leave.type"].create(
            {
                "name": "Annual Leave with Handover",
                "requires_allocation": False,
                "handover_escalation_after_hours": 2.0,
                "company_id": cls.requester_user.company_id.id,
            }
        )

    def _create_leave_with_handover(self, state="confirm"):
        leave_day = date(2026, 8, 10)
        start_dt = datetime.combine(leave_day, time(8, 0))
        end_dt = datetime.combine(leave_day, time(17, 0))
        leave = self.env["hr.leave"].sudo().create(
            {
                "name": "Leave requiring handover",
                "employee_id": self.requester_employee.id,
                "holiday_status_id": self.leave_type.id,
                "request_date_from": leave_day,
                "request_date_to": leave_day,
                "date_from": start_dt,
                "date_to": end_dt,
                "handover_employee_ids": [Command.set([self.handover_employee.id])],
                "state": state,
            }
        )
        return leave

    def test_can_respond_handover_persists_before_and_after_timeout(self):
        """Handover employee can see Accept/Refuse buttons before and after the interaction timeout."""
        leave = self._create_leave_with_handover(state="confirm")

        # Before timeout: handover employee can respond
        leave_as_handover = leave.with_user(self.handover_user)
        self.assertTrue(leave_as_handover.can_respond_handover)

        # Requester cannot respond
        leave_as_requester = leave.with_user(self.requester_user)
        self.assertFalse(leave_as_requester.can_respond_handover)

        # Manager cannot respond to handover
        leave_as_manager = leave.with_user(self.manager_user)
        self.assertFalse(leave_as_manager.can_respond_handover)

        # Simulate timeout: 3 hours past handover_requested_at (configured timeout is 2h)
        past_time = fields.Datetime.now() - timedelta(hours=3)
        leave.sudo().write({"handover_requested_at": past_time, "handover_escalated": True})

        # After timeout: handover employee still has action buttons available
        leave_as_handover.invalidate_recordset(["can_respond_handover"])
        self.assertTrue(leave_as_handover.can_respond_handover)

    def test_handover_ready_for_approval_after_timeout(self):
        """Approval is unblocked after handover interaction timeout passes."""
        leave = self._create_leave_with_handover(state="confirm")

        # Before timeout: not ready for approval
        self.assertFalse(leave._handover_past_due_for_approval())
        self.assertFalse(leave._handover_ready_for_approval())
        self.assertTrue(leave.handover_status_waiting)
        self.assertEqual(leave.status_display_label, "Đang chờ bàn giao công việc")

        # Approval guard raises error
        with self.assertRaises(UserError):
            leave._ensure_handover_ready_for_approval()

        # Check approval update returns False or raises
        with self.assertRaises(UserError):
            leave._check_approval_update("validate")

        # Simulate timeout (exceeded configured 2.0h)
        past_time = fields.Datetime.now() - timedelta(hours=2.5)
        leave.sudo().write({"handover_requested_at": past_time})

        # After timeout: past due and ready for approval
        self.assertTrue(leave._handover_past_due_for_approval())
        self.assertTrue(leave._handover_ready_for_approval())
        self.assertFalse(leave.handover_status_waiting)
        self.assertEqual(leave.status_display_label, "Đang chờ duyệt")

        # Approval guard now passes without raising UserError
        self.assertTrue(leave._ensure_handover_ready_for_approval())
        # _check_approval_update allows state update
        self.assertTrue(leave._check_approval_update("validate"))

    def test_handover_accept_after_timeout(self):
        """Handover employee can still accept handover even after timeout has passed."""
        leave = self._create_leave_with_handover(state="confirm")
        past_time = fields.Datetime.now() - timedelta(hours=4)
        leave.sudo().write({"handover_requested_at": past_time, "handover_escalated": True})

        # Handover employee accepts
        leave.with_user(self.handover_user).action_handover_accept()

        line = leave.handover_acceptance_ids.filtered(lambda l: l.employee_id == self.handover_employee)
        self.assertEqual(line.state, "accepted")
        self.assertFalse(leave.with_user(self.handover_user).can_respond_handover)

    def test_handover_refuse_after_timeout(self):
        """Handover employee can still refuse handover even after timeout has passed."""
        leave = self._create_leave_with_handover(state="confirm")
        past_time = fields.Datetime.now() - timedelta(hours=4)
        leave.sudo().write({"handover_requested_at": past_time, "handover_escalated": True})

        # Handover employee refuses with reason
        leave.with_user(self.handover_user).action_handover_refuse_with_reason("Busy with project deadline")

        line = leave.handover_acceptance_ids.filtered(lambda l: l.employee_id == self.handover_employee)
        self.assertEqual(line.state, "refused")
        self.assertEqual(line.refusal_reason, "Busy with project deadline")
        self.assertFalse(leave.with_user(self.handover_user).can_respond_handover)

    def test_handover_escalation_owner_can_approve(self):
        """Escalation owner has approval rights and can approve after handover timeout."""
        leave = self._create_leave_with_handover(state="confirm")
        past_time = fields.Datetime.now() - timedelta(hours=3)
        leave.sudo().write({
            "handover_requested_at": past_time,
            "handover_escalated": True,
            "handover_escalation_user_id": self.escalation_user.id,
        })

        leave_as_esc = leave.with_user(self.escalation_user)
        self.assertTrue(leave_as_esc.can_approve or leave_as_esc.can_responsible_approve)
        self.assertIn(self.escalation_user, leave.approval_actionable_user_ids)

        if leave_as_esc.can_approve:
            leave_as_esc.action_approve()
        else:
            leave_as_esc.action_responsible_approve()
        self.assertEqual(leave.state, "validate")

    def test_handover_escalation_owner_can_refuse(self):
        """Escalation owner can refuse leave request after handover timeout."""
        leave = self._create_leave_with_handover(state="confirm")
        past_time = fields.Datetime.now() - timedelta(hours=3)
        leave.sudo().write({
            "handover_requested_at": past_time,
            "handover_escalated": True,
            "handover_escalation_user_id": self.escalation_user.id,
        })

        leave_as_esc = leave.with_user(self.escalation_user)
        self.assertTrue(leave_as_esc.can_refuse or leave_as_esc.can_responsible_approve)

        if leave_as_esc.can_refuse:
            leave_as_esc.action_refuse(reason="Handover could not be resolved")
        else:
            leave_as_esc.action_responsible_refuse(reason="Handover could not be resolved")
        self.assertEqual(leave.state, "refuse")

