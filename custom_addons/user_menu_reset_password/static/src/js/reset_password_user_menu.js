/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { user } from "@web/core/user";

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

registry.category("user_menuitems").add("change_password", changePasswordItem);
