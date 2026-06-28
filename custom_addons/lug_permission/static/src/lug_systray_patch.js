/** @odoo-module **/

import { registry } from "@web/core/registry";
import { session } from "@web/session";

const systray = registry.category("systray");
const userMenu = registry.category("user_menuitems");

if (session.lug_ui?.hide_messaging && systray.contains("mail.messaging_menu")) {
    systray.remove("mail.messaging_menu");
}
if (session.lug_ui?.hide_activities && systray.contains("mail.activity_menu")) {
    systray.remove("mail.activity_menu");
}
if (session.lug_ui?.hide_help && userMenu.contains("support")) {
    userMenu.remove("support");
}
