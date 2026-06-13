/** @odoo-module **/

import { Chatter } from "@mail/chatter/web_portal/chatter";
import { onMounted, onPatched } from "@odoo/owl";
import { patch } from "@web/core/utils/patch";

patch(Chatter.prototype, {
    setup() {
        super.setup(...arguments);
        onMounted(() => this._syncTimeOffChatterVisibility());
        onPatched(() => this._syncTimeOffChatterVisibility());
    },

    _syncTimeOffChatterVisibility() {
        const root = this.rootRef.el;
        if (!root) {
            return;
        }
        const hideCommunication = this.props.threadModel === "hr.leave";
        const selectors = [
            ".o-mail-Chatter-sendMessage",
            ".o-mail-Chatter-logNote",
            ".o-mail-SearchMessageResult",
            ".o-mail-Thread",
        ];
        for (const selector of selectors) {
            for (const element of root.querySelectorAll(selector)) {
                element.hidden = hideCommunication;
            }
        }
        const searchButton = root
            .querySelector(".o-mail-Chatter-topbar .oi-search")
            ?.closest("button");
        if (searchButton) {
            searchButton.hidden = hideCommunication;
        }
    },

    toggleComposer(mode = false, options = {}) {
        if (mode && this.props.threadModel === "hr.leave") {
            return;
        }
        return super.toggleComposer(mode, options);
    },
});
