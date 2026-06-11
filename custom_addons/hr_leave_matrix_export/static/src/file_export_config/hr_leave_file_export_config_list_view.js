/** @odoo-module **/

import { registry } from "@web/core/registry";
import { DynamicRecordList } from "@web/model/relational_model/dynamic_record_list";
import { RelationalModel } from "@web/model/relational_model/relational_model";
import { listView } from "@web/views/list/list_view";
import { executeButtonCallback } from "@web/views/view_button/view_button_hook";

export class HrLeaveFileExportConfigDynamicRecordList extends DynamicRecordList {
    async leaveEditMode({ discard, manualSave } = {}) {
        const editedRecord = this.editedRecord;
        if (!editedRecord) {
            return true;
        }
        if (discard) {
            return super.leaveEditMode({ discard: true });
        }
        if (manualSave) {
            if (editedRecord.isNew && !editedRecord.dirty) {
                this._removeRecords([editedRecord.id]);
                return true;
            }
            this.model._updateConfig(
                editedRecord.config,
                { mode: "readonly" },
                { reload: false }
            );
            return true;
        }

        const isDirty = await editedRecord.isDirty();
        if (isDirty) {
            return false;
        }
        if (editedRecord.isNew) {
            this._removeRecords([editedRecord.id]);
            return true;
        }
        this.model._updateConfig(
            editedRecord.config,
            { mode: "readonly" },
            { reload: false }
        );
        return true;
    }
}

export class HrLeaveFileExportConfigRelationalModel extends RelationalModel {}
HrLeaveFileExportConfigRelationalModel.DynamicRecordList =
    HrLeaveFileExportConfigDynamicRecordList;

export class HrLeaveFileExportConfigListController extends listView.Controller {
    async onClickSave() {
        return executeButtonCallback(this.rootRef.el, async () => {
            if (!this.editedRecord) {
                return;
            }
            const saved = await this.editedRecord.save();
            if (saved) {
                await this.model.root.leaveEditMode({ manualSave: true });
            }
        });
    }
}

export const hrLeaveFileExportConfigListView = {
    ...listView,
    Controller: HrLeaveFileExportConfigListController,
    Model: HrLeaveFileExportConfigRelationalModel,
};

registry.category("views").add(
    "hr_leave_file_export_config_list",
    hrLeaveFileExportConfigListView
);
