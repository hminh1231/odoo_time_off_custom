#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""One-off: fix Owl Kanban crash caused by duplicate hr.leave inherit views."""
import subprocess
import sys
from pathlib import Path

SCRIPT = """
from odoo.addons.time_off_work_handover.hooks import cleanup_duplicate_hr_leave_views

removed = cleanup_duplicate_hr_leave_views(env)
env.cr.commit()
print("Removed %s duplicate hr.leave view(s)." % removed)
for name in (
    "validation_type",
    "can_responsible_approve",
    "can_multi_step_approve",
    "approval_current_step_label",
):
    print("hr.leave.%s:" % name, name in env["hr.leave"]._fields)
print("Done. Restart Odoo and hard-refresh the browser (Ctrl+F5).")
"""

if len(sys.argv) < 2:
    print("Usage: python fix_kanban_login_error.py <path-to-odoo.conf>")
    sys.exit(1)

conf = Path(sys.argv[1]).resolve()
root = conf.parent
odoo_bin = root / "odoo" / "odoo-bin"
if not odoo_bin.is_file():
    odoo_bin = Path(__file__).resolve().parents[2] / "odoo" / "odoo-bin"

db_name = None
for line in conf.read_text(encoding="utf-8").splitlines():
    line = line.strip()
    if line.startswith("db_name"):
        db_name = line.split("=", 1)[1].strip()
        break
if not db_name:
    print("Could not read db_name from config.")
    sys.exit(1)

proc = subprocess.run(
    [sys.executable, str(odoo_bin), "shell", "-c", str(conf), "-d", db_name, "--no-http"],
    input=SCRIPT,
    text=True,
    capture_output=True,
    cwd=str(root),
)
sys.stdout.write(proc.stdout)
if proc.stderr:
    sys.stderr.write(proc.stderr)
sys.exit(proc.returncode)
