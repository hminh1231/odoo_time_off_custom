{
    "name": "User Menu Change Password",
    "version": "19.0.1.1.0",
    "category": "Administration",
    "summary": "Add Change Password option to the backend user menu",
    "depends": ["web"],
    "assets": {
        "web.assets_backend": [
            "user_menu_reset_password/static/src/js/reset_password_user_menu.js",
        ],
    },
    "installable": True,
    "application": False,
    "auto_install": False,
    "author": "Custom",
    "license": "LGPL-3",
}
