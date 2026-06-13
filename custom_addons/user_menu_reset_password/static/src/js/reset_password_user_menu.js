/** @odoo-module **/

import { Component } from "@odoo/owl";

import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { user } from "@web/core/user";
import { imageUrl } from "@web/core/utils/urls";
import { session } from "@web/session";

class UserMenuIdentity extends Component {
    static template = "user_menu_reset_password.UserMenuIdentity";
    static props = {};

    setup() {
        this.userName = user.name;
        this.dbName = session.db;
        this.avatarSource = imageUrl("res.partner", user.partnerId, "avatar_128", {
            unique: user.writeDate,
        });
    }
}

function userIdentityItem(env) {
    return {
        type: "component",
        contentComponent: UserMenuIdentity,
        hide: env.isSmall,
        sequence: 1,
    };
}

function changePasswordItem(env) {
    return {
        type: "item",
        id: "change_password",
        description: _t("Change Password"),
        callback: async () => {
            const action = await env.services.orm.call("res.users", "preference_change_password", [
                [user.userId],
            ]);
            if (action) {
                env.services.action.doAction(action);
            }
        },
        sequence: 56,
    };
}

registry.category("user_menuitems").add("user_identity", userIdentityItem);
registry.category("user_menuitems").add("change_password", changePasswordItem);
