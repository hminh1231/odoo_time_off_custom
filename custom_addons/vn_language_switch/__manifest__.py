{
    "name": "Vietnamese Language Switch",
    "version": "19.0.1.0.0",
    "category": "Administration",
    "summary": "Per-user language switch between English and Vietnamese",
    "depends": ["base", "base_setup", "web"],
    "data": [
        "views/res_config_settings_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "vn_language_switch/static/src/js/language_switch_user_menu.js",
        ],
    },
    "installable": True,
    "application": True,
    "auto_install": False,
    "author": "Custom",
    "license": "LGPL-3",
}
