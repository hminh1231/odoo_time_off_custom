# -*- coding: utf-8 -*-
"""Find kanban arch fields missing from get_views models fields dict."""
import re
import subprocess
import sys
from pathlib import Path

from lxml import etree

SCRIPT = r"""
import re
from lxml import etree

def check(model_name, uid):
    user_env = env(user=uid)
    try:
        res = user_env[model_name].get_views([(False, "kanban")], {"toolbar": False})
    except Exception as exc:
        print("SKIP uid=%s %s: %s" % (uid, model_name, exc))
        return
    kanban = res["views"]["kanban"]
    arch = kanban["arch"]
    fields = res.get("models", {}).get(model_name, {}).get("fields", {})
    root = etree.fromstring(arch.encode() if isinstance(arch, str) else arch)
    names = sorted(
        {el.get("name") for el in root.xpath(".//field[@name]") if el.get("name")}
    )
    missing = [n for n in names if n not in fields]
    print(
        "uid=%s %s view=%s missing=%s"
        % (uid, model_name, kanban.get("id"), missing or "(none)")
    )

for model in ("hr.employee", "hr.employee.public", "hr.leave"):
    check(model, 1)
users = env["res.users"].search([("share", "=", False)])
for u in users:
    user_env = env(user=u.id)
    if user_env["hr.employee"].has_access("read"):
        check("hr.employee", u.id)
    elif user_env["hr.employee.public"].has_access("read"):
        check("hr.employee.public", u.id)
"""

if len(sys.argv) < 2:
    print("Usage: python diagnose_kanban_views.py <path-to-odoo.conf>")
    sys.exit(1)

conf = Path(sys.argv[1]).resolve()
root = conf.parent
odoo_bin = root / "odoo" / "odoo-bin"
if not odoo_bin.is_file():
    odoo_bin = Path(__file__).resolve().parents[2] / "odoo" / "odoo-bin"

proc = subprocess.run(
    [sys.executable, str(odoo_bin), "shell", "-c", str(conf), "--no-http"],
    input=SCRIPT,
    text=True,
    capture_output=True,
    cwd=str(root),
)
sys.stdout.write(proc.stdout)
if proc.stderr:
    sys.stderr.write(proc.stderr)
sys.exit(proc.returncode)
