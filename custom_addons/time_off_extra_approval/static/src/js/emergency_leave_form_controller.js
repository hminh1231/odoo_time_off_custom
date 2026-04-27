/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";
import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { patch } from "@web/core/utils/patch";
import { FormController } from "@web/views/form/form_controller";

const EMERGENCY_CTX = "emergency_leave_confirmed";

patch(FormController.prototype, {
    async onWillSaveRecord(record, changes) {
        const sup = await super.onWillSaveRecord(...arguments);
        if (sup === false) {
            return false;
        }
        if (record.resModel !== "hr.leave") {
            return true;
        }
        const preview = await this.orm.call("hr.leave", "check_emergency_leave_lead_time", [], {
            res_id: record.resId || false,
            vals: changes,
        });
        if (!preview.needs_confirmation) {
            return true;
        }
        const confirmed = await new Promise((resolve) => {
            this.dialogService.add(ConfirmationDialog, {
                title: preview.title || _t("Emergency leave confirmation"),
                body: preview.message,
                confirm: () => resolve(true),
                cancel: () => resolve(false),
            });
        });
        if (!confirmed) {
            return false;
        }
        Object.assign(this.model.config.context, { [EMERGENCY_CTX]: true });
        return true;
    },
    async onRecordSaved(record, changes) {
        const res = await super.onRecordSaved(...arguments);
        if (record.resModel === "hr.leave" && EMERGENCY_CTX in this.model.config.context) {
            delete this.model.config.context[EMERGENCY_CTX];
        }
        return res;
    },
});
