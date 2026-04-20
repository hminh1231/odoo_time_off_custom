/** @odoo-module **/

import { deserializeDate, deserializeDateTime } from "@web/core/l10n/dates";
import { patch } from "@web/core/utils/patch";
import { FormController } from "@web/views/form/form_controller";
import { useBus } from "@web/core/utils/hooks";

const CCCD_IMPORT_BUS = "hr_employee_cccd_scan:import";

patch(FormController.prototype, {
    setup() {
        super.setup(...arguments);
        useBus(this.env.bus, CCCD_IMPORT_BUS, (ev) => {
            const detail = ev.detail;
            if (!detail || this.props.resModel !== "hr.employee") {
                return;
            }
            const values = detail.values;
            if (!values || typeof values !== "object") {
                return;
            }
            const root = this.model.root;
            const changes = {};
            for (const [key, val] of Object.entries(values)) {
                if (val === undefined || val === null || val === false) {
                    continue;
                }
                if (!(key in root.fields)) {
                    continue;
                }
                const field = root.fields[key];
                // Record.update expects Luxon DateTime for date/datetime (not raw ISO strings).
                if (field.type === "date" && typeof val === "string") {
                    changes[key] = deserializeDate(val);
                } else if (field.type === "datetime" && typeof val === "string") {
                    changes[key] = deserializeDateTime(val);
                } else if (field.type === "many2one" && typeof val === "number") {
                    // Integer alone breaks _completeMany2OneValue (expects { id }); UI then stays empty.
                    changes[key] = { id: val };
                } else {
                    changes[key] = val;
                }
            }
            if (Object.keys(changes).length) {
                root.update(changes);
            }
        });
    },

    async beforeExecuteActionButton(clickParams) {
        // Allow opening camera on new employee forms without forcing save first.
        if (clickParams?.type === "object" && clickParams?.name === "action_scan_id_card") {
            return true;
        }
        return super.beforeExecuteActionButton(...arguments);
    },
});
