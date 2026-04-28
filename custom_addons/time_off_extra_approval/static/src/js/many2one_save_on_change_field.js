import { registry } from "@web/core/registry";
import {
    Many2OneField,
    buildM2OFieldDescription,
} from "@web/views/fields/many2one/many2one_field";
import { computeM2OProps } from "@web/views/fields/many2one/many2one";

/**
 * Saves the form right after the many2one value changes (existing records only).
 *
 * Important: `record.update(..., { save: true })` sets `withoutOnchange: true` in the web client,
 * which skips @api.onchange (no warning popups, no server-side `value` clears). We therefore apply
 * the change with `save: false` first so onchanges run, then call `record.save()`.
 */
export class Many2OneSaveOnChangeField extends Many2OneField {
    get m2oProps() {
        const props = computeM2OProps(this.props);
        const originalUpdate = props.update;
        const record = this.props.record;
        return {
            ...props,
            update: async (value, options = {}) => {
                await originalUpdate(value, { ...options, save: false });
                if (!record.isNew && record.canSaveOnUpdate) {
                    await record.save();
                }
            },
        };
    }
}

registry.category("fields").add("many2one_save_on_change", {
    ...buildM2OFieldDescription(Many2OneSaveOnChangeField),
});
