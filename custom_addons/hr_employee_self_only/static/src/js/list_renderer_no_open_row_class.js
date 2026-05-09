/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { ListRenderer } from "@web/views/list/list_renderer";

/**
 * Core đã có .o_data_row.o_list_no_open { cursor: default } nhưng không ai gắn class.
 * Khi archInfo.noOpen (gồm many2many Managed Departments), thêm class để đồng bộ hàng.
 * Ô vẫn có .cursor-pointer trên td — xử lý bằng SCSS riêng.
 */
patch(ListRenderer.prototype, {
    getRowClass(record) {
        const cls = super.getRowClass(record);
        if (this.props.archInfo?.noOpen) {
            return cls ? `${cls} o_list_no_open` : "o_list_no_open";
        }
        return cls;
    },
});
