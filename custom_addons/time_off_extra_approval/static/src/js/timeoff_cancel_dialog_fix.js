/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { TimeOffDialogFormController } from "@hr_holidays/views/view_dialog/form_view_dialog";

patch(TimeOffDialogFormController.prototype, {
    cancelRecord() {
        const leaveId = this.record.resId;
        if (!leaveId || this.record.isNew) {
            this.deleteRecord();
            this.props.onCancelLeave();
            return;
        }
        this.leaveCancelWizard(leaveId, () => {
            this.props.onLeaveCancelled();
        });
        this.props.onCancelLeave();
    },
});
