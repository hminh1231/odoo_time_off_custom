/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { ExportAll } from "@web/views/list/export_all/export_all";
import { DropdownItem } from "@web/core/dropdown/dropdown_item";
import { useService } from "@web/core/utils/hooks";
import { onWillStart } from "@odoo/owl";
import { xml } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";

// ExportAll is only mounted when the standard "Export All" cog rules already pass
// (list/kanban, export group, export_xlsx, no selection). Restrict to Time Off model only.
patch(ExportAll, {
    components: { DropdownItem },
    template: xml`
        <DropdownItem class="'o_export_all_menu'" onSelected.bind="onDirectExportData">
            <i class="fa fa-fw fa-upload me-1"/>Export All
        </DropdownItem>
        <DropdownItem
            t-if="showHrLeaveMatrixExport and matrixExportAccess.show_vp"
            class="'o_hr_leave_matrix_export_menu'"
            onSelected.bind="onMatrixExport">
            <i class="fa fa-fw fa-table me-1"/>Kết xuất nghỉ phép VP
        </DropdownItem>
        <DropdownItem
            t-if="showHrLeaveMatrixExport and matrixExportAccess.show_ch"
            class="'o_hr_leave_store_export_menu'"
            onSelected.bind="onStoreExport">
            <i class="fa fa-fw fa-file-excel-o me-1"/>Kết xuất nghỉ phép CH
        </DropdownItem>
        <DropdownItem
            t-if="showHrLeaveMatrixExport and matrixExportAccess.show_ch"
            class="'o_hr_leave_import_capnhatcong_menu'"
            onSelected.bind="onImportCapnhatcongExport">
            <i class="fa fa-fw fa-file-excel-o me-1"/>import_capnhatcong CUA HANG
        </DropdownItem>
    `,
});

patch(ExportAll.prototype, {
    setup() {
        super.setup(...arguments);
        this.orm = useService("orm");
        this.matrixExportAccess = { show_vp: false, show_ch: false };
        this.showHrLeaveMatrixExport = false;
        onWillStart(async () => {
            if (this.env.model?.root?.resModel === "hr.leave") {
                this.showHrLeaveMatrixExport = true;
                this.matrixExportAccess = await this.orm.call(
                    "hr.leave",
                    "get_matrix_export_menu_access",
                    []
                );
            }
        });
    },

    async onMatrixExport() {
        await this._openLeaveExportWizard("hr.leave.matrix.export.wizard", _t("Kết xuất nghỉ phép VP"), {
            form_view_ref: "hr_leave_matrix_export.view_hr_leave_matrix_export_wizard_form",
        });
    },

    async onStoreExport() {
        await this._openLeaveExportWizard("hr.leave.matrix.export.wizard", _t("Kết xuất nghỉ phép CH"), {
            form_view_ref: "hr_leave_matrix_export.view_hr_leave_store_export_wizard_form",
        });
    },

    async onImportCapnhatcongExport() {
        await this._openLeaveExportWizard(
            "hr.leave.matrix.export.wizard",
            _t("import_capnhatcong CUA HANG"),
            {
                form_view_ref: "hr_leave_matrix_export.view_hr_leave_import_capnhatcong_wizard_form",
            }
        );
    },

    async _openLeaveExportWizard(resModel, title, extraContext = {}) {
        const sm = this.env.searchModel;
        const domain = sm ? sm.domain : [];
        const today = luxon.DateTime.local();
        await this.env.services.action.doAction({
            type: "ir.actions.act_window",
            name: title,
            res_model: resModel,
            views: [[false, "form"]],
            target: "new",
            context: {
                default_year: today.year,
                default_month: today.month,
                matrix_export_domain_json: JSON.stringify(domain),
                ...extraContext,
            },
        });
    },
});
