/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { registry } from "@web/core/registry";
import { onWillRender } from "@odoo/owl";
import { toRaw } from "@odoo/owl";

/**
 * After core trims the Employees privilege options (Time Off can imply HR Officer),
 * move "No" to the first position after the empty placeholder so UX matches intent.
 */
const reg = registry.category("fields").get("res_user_group_ids");
if (reg?.component) {
    patch(reg.component.prototype, {
        setup() {
            super.setup(...arguments);
            onWillRender(() => {
                const raw = toRaw(this.props.record.data.view_group_hierarchy);
                const noGid = raw.hr_employee_self_only?.employees_no_group_id;
                if (!noGid) {
                    return;
                }
                const { groups } = raw;
                const privId = groups[noGid]?.privilege_id;
                if (!privId) {
                    return;
                }
                const fieldName = `field_${privId}`;
                const sel = this.fields[fieldName]?.selection;
                if (!sel || sel.length < 3) {
                    return;
                }
                const placeholder = sel[0];
                const rest = sel.slice(1);
                const noOpt = rest.find((opt) => opt[0] === noGid);
                if (!noOpt || rest[0]?.[0] === noGid) {
                    return;
                }
                const others = rest.filter((opt) => opt[0] !== noGid);
                this.fields[fieldName].selection = [placeholder, noOpt, ...others];
            });
        },
    });
}
