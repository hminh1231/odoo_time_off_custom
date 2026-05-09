/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { X2ManyField } from "@web/views/fields/x2many/x2many_field";

/**
 * Employees=No (employee_form_force_readonly_ui): Managed Departments chỉ xem —
 * không mở form phòng ban, không thêm / xóa dòng (many2many link/unlink).
 */
patch(X2ManyField.prototype, {
    get rendererProps() {
        const props = super.rendererProps;
        if (this.props.name !== "managed_department_ids") {
            return props;
        }
        const lock = Boolean(this.props.record?.data?.employee_form_force_readonly_ui);
        if (!lock) {
            return props;
        }
        props.readonly = true;
        props.editable = false;
        if (props.archInfo) {
            props.archInfo = {
                ...props.archInfo,
                noOpen: true,
            };
        }
        const z = {
            create: false,
            createEdit: false,
            delete: false,
            edit: false,
            write: false,
            link: false,
            unlink: false,
        };
        props.activeActions = { ...props.activeActions, ...z };
        props.hasOpenFormViewButton = false;
        props.onAdd = () => {};
        return props;
    },
});
