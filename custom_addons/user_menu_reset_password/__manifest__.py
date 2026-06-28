{
    "name": "User Menu Enhancements",
    "version": "19.0.1.2.2",
    "category": "Administration",
    "summary": "Show user identity in navbar and Change Password in the backend user menu",
    "depends": ["web"],
    "assets": {
        "web.assets_backend": [
            "user_menu_reset_password/static/src/js/reset_password_user_menu.js",
            "user_menu_reset_password/static/src/xml/user_menu.xml",
            "user_menu_reset_password/static/src/scss/user_menu.scss",
        ],
    },
    "installable": True,
    "application": False,
    "auto_install": False,
    "author": "Custom",
    "license": "LGPL-3",
}
