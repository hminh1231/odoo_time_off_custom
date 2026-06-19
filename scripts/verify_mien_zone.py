zones = env["hr.mien.zone"].search([])
for z in zones:
    print(z.id, z.name, "parent=", z.parent_id.name or "-", "assignable=", z.is_assignable)
print("---")
user = env["res.users"].search([("login", "=", "nhi.cao@sangtam.com")], limit=1)
visible = env["hr.employee"].with_user(user).search([])
print("nhi scope", user.hr_user_workforce_scope, "visible", len(visible))
by_zone = {}
for e in visible:
    name = e.mien_zone_id.name or "none"
    by_zone[name] = by_zone.get(name, 0) + 1
print("by_zone", by_zone)
