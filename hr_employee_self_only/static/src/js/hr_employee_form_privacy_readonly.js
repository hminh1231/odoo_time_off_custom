/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { onMounted, onWillStart, status } from "@odoo/owl";
import { user } from "@web/core/user";
import { effect } from "@web/core/utils/reactive";

import { EmployeeFormController } from "@hr/views/form_view";

/**
 * Employees=No: employee form is always readonly (no typing), including own profile.
 * Flag is computed on hr.employee (HR Manager bypasses).
 */
patch(EmployeeFormController.prototype, {
    setup() {
        super.setup(...arguments);
        this._employeesNoUiLock = false;
        onWillStart(async () => {
            this._employeesNoUiLock = await user.hasGroup(
                "hr_employee_self_only.group_hr_employees_no"
            );
            if (this._employeesNoUiLock) {
                this.canCreate = false;
            }
        });
        onMounted(() => {
            effect(
                (model) => {
                    if (status(this) !== "mounted") {
                        return;
                    }
                    const root = model.root;
                    if (!root || root.isNew || !root.resId) {
                        return;
                    }
                    if (!root.fields.employee_form_force_readonly_ui) {
                        return;
                    }
                    const forceReadonly = root.data.employee_form_force_readonly_ui;
                    if (forceReadonly === undefined) {
                        return;
                    }
                    if (forceReadonly) {
                        if (root.config.mode !== "readonly") {
                            root.switchMode("readonly");
                        }
                    } else if (this.canEdit && root.config.mode === "readonly") {
                        root.switchMode("edit");
                    }
                },
                [this.model]
            );
        });
    },

    get cogMenuProps() {
        const props = super.cogMenuProps;
        if (!this._employeesNoUiLock) {
            return props;
        }
        return {
            ...props,
            items: {},
        };
    },
});
