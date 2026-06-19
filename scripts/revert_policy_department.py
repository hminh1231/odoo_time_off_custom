# -*- coding: utf-8 -*-
"""Revert the two test users back to 'department' policy (safe original state)."""

for login in ("an.lac@sangtam.com", "nhi.cao@sangtam.com"):
    user = env["res.users"].search([("login", "=", login)], limit=1)
    if user:
        user.visibility_policy = "department"
        print("reverted", login, "-> department")
env.cr.commit()
env.registry.clear_cache()
print("done")
