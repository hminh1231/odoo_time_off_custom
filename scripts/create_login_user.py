# Example: pipe into Odoo shell (Odoo 19 uses group_ids, not groups_id).
#   Get-Content scripts\create_login_user.py | .\venv\Scripts\python.exe odoo-bin shell -c odoo.conf -d odoo_db
# Edit LOGIN / PASSWORD / NAME before running.

LOGIN = "user@example.com"
PASSWORD = "change-me"
NAME = "Your Name"

existing = env["res.users"].search([("login", "=", LOGIN)])
if existing:
    existing.write({"password": PASSWORD})
    print("Updated password for:", LOGIN)
else:
    env["res.users"].create(
        {
            "name": NAME,
            "login": LOGIN,
            "password": PASSWORD,
            "group_ids": [(6, 0, [env.ref("base.group_system").id])],
        }
    )
    print("Created administrator:", LOGIN)
env.cr.commit()
