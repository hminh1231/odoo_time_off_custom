# Run: Get-Content scripts/create_demo_multi_step_leave.py | .\venv\Scripts\python.exe odoo-bin shell -c odoo.conf -d odoo_db
# Creates one hr.leave in To Approve for a multi_step_6 leave type (demo).

from datetime import date, timedelta

Lt = env["hr.leave.type"].search([("leave_validation_type", "=", "multi_step_6")], limit=1)
if not Lt:
    print("ERROR: No Time Off Type with 'By 6-Step Approval (Demo)'. Configure one first.")
else:
    emp = env["hr.employee"].search([("user_id", "!=", False)], limit=1)
    if not emp:
        print("ERROR: No employee with a linked user.")
    else:
        start = date.today() + timedelta(days=7)
        end = start + timedelta(days=1)
        vals = {
            "employee_id": emp.id,
            "holiday_status_id": Lt.id,
            "request_date_from": start,
            "request_date_to": end,
            "private_name": "Demo multi-step approval (script)",
        }
        leave = env["hr.leave"].create(vals)
        leave.invalidate_recordset()
        print("OK: Created hr.leave id=%s state=%s employee=%s type=%s" % (leave.id, leave.state, emp.name, Lt.name))
        print("Open: Time Off > To Approve, or search leave id %s" % leave.id)
