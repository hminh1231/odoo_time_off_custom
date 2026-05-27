# -*- coding: utf-8 -*-
"""Sync en_US display names for active leave types (match Vietnamese codes in parentheses)."""

from odoo import SUPERUSER_ID, api

# vi_VN name (exact) -> en_US name
LEAVE_TYPE_EN_NAMES = {
    "Nghỉ Phép (P)": "Annual Leave (P)",
    "Nghỉ phép (P1)": "Annual Leave (P1)",
    "Nghỉ phép (P2)": "Annual Leave (P2)",
    "Nghỉ phép không lương": "Unpaid Time Off",
    "Nghỉ không lương (O)": "Unpaid Leave (O)",
    "Làm Online (O)": "Work Online (O)",
    "1/2 Online và 1/2 Phép (PO)": "1/2 Online and 1/2 Paid Leave (PO)",
    "1/2 Online và 1/2 không lương (NO)": "1/2 Online and 1/2 Unpaid (NO)",
    "1/2 Phép và 1/2 Không Lương (PN)": "1/2 Paid Leave and 1/2 Unpaid (PN)",
    "1/2 Không Lương (XN)": "1/2 Unpaid Leave (XN)",
    "Nghỉ Phép Tang (PT)": "Bereavement Leave (PT)",
    "Nghỉ Phép Cưới (PC)": "Marriage Leave (PC)",
}


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    LeaveType = env["hr.leave.type"].with_context(active_test=False)
    for leave_type in LeaveType.search([]):
        vi_name = (leave_type.with_context(lang="vi_VN").name or "").strip()
        en_name = LEAVE_TYPE_EN_NAMES.get(vi_name)
        if not en_name:
            continue
        if (leave_type.with_context(lang="en_US").name or "").strip() == en_name:
            continue
        leave_type.with_context(lang="en_US").write({"name": en_name})
