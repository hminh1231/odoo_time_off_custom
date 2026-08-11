/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";
import { download } from "@web/core/network/download";
import { rpc } from "@web/core/network/rpc";
import { patch } from "@web/core/utils/patch";
import { ExportAll } from "@web/views/list/export_all/export_all";

/** Models whose "Export All" uses get_migration_export_fields (import-compatible). */
const FULL_EXPORT_ERROR = {
    "res.users": _t("Không xuất được danh sách người dùng. Thử lại hoặc F12 xem lỗi."),
    "lug.group": _t("Không xuất được nhóm quyền. Thử lại hoặc F12 xem lỗi."),
};

/**
 * IMPORTANT: do not use useService("orm") here. ExportAll lives inside the
 * cog dropdown; closing the menu destroys the component and protected ORM
 * promises hang forever (never reach download).
 */
patch(ExportAll.prototype, {
    async onDirectExportData() {
        const root = this.env.model?.root;
        const model = root?.resModel;
        if (!model || !(model in FULL_EXPORT_ERROR)) {
            return super.onDirectExportData(...arguments);
        }

        // Snapshot before dropdown unmounts this component.
        const context = { ...root.context };
        const domain = [...root.domain];
        const groupby = [...(root.groupBy || [])];
        const notification = this.env.services.notification;

        try {
            const fields = await rpc(
                `/web/dataset/call_kw/${model}/get_migration_export_fields`,
                {
                    model,
                    method: "get_migration_export_fields",
                    args: [],
                    kwargs: {},
                }
            );
            const exportedFields = [
                { name: "id", label: _t("External ID") },
                ...fields.map((field) => ({
                    name: field.name,
                    label: field.label,
                    store: field.store,
                    type: field.type,
                })),
            ];

            await download({
                data: {
                    data: JSON.stringify({
                        import_compat: true,
                        context: {
                            ...context,
                            lug_migration_export: true,
                        },
                        domain,
                        fields: exportedFields,
                        groupby,
                        ids: false,
                        model,
                    }),
                },
                url: "/web/export/xlsx",
            });
        } catch (error) {
            console.error(error);
            notification?.add(FULL_EXPORT_ERROR[model], { type: "danger" });
        }
    },
});
