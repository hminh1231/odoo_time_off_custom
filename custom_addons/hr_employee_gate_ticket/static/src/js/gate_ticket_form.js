/** @odoo-module **/

import { Chatter } from "@mail/chatter/web_portal/chatter";
import { patch } from "@web/core/utils/patch";

patch(Chatter.prototype, {
    setup() {
        super.setup(...arguments);

        // Auto-expand attachments for gate ticket model
        if (this.props.threadModel === "hr.employee.gate.ticket") {
            // Set initial state to show attachment box
            this.state.isAttachmentBoxOpened = true;
        }
    },
});
