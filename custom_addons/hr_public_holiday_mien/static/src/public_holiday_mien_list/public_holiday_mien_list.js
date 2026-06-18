/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { listView } from "@web/views/list/list_view";
import { ListController } from "@web/views/list/list_controller";
import { onMounted, useState } from "@odoo/owl";

const SCOPE_FILTERS = {
    vp: "holiday_scope_vp",
    ch: "holiday_scope_ch",
};

export class PublicHolidayMienListController extends ListController {
    static template = "hr_public_holiday_mien.ListView";

    setup() {
        super.setup();
        this.holidayScopeState = useState({ scope: "vp" });
        onMounted(() => {
            this._syncScopeFromSearchModel();
        });
    }

    get officeButtonLabel() {
        return _t("Văn Phòng");
    }

    get storeButtonLabel() {
        return _t("Cửa Hàng");
    }

    _findSearchItemByName(name) {
        const searchModel = this.env.searchModel;
        if (!searchModel) {
            return null;
        }
        return Object.values(searchModel.searchItems).find((item) => item.name === name) || null;
    }

    _isSearchItemActive(item) {
        if (!item) {
            return false;
        }
        return this.env.searchModel.query.some((queryElem) => queryElem.searchItemId === item.id);
    }

    _syncScopeFromSearchModel() {
        const vpItem = this._findSearchItemByName(SCOPE_FILTERS.vp);
        const chItem = this._findSearchItemByName(SCOPE_FILTERS.ch);
        if (this._isSearchItemActive(chItem)) {
            this.holidayScopeState.scope = "ch";
        } else if (this._isSearchItemActive(vpItem)) {
            this.holidayScopeState.scope = "vp";
        }
        this._updateDefaultScopeContext();
    }

    _updateDefaultScopeContext() {
        if (!this.model?.config) {
            return;
        }
        this.model.config.context = {
            ...this.model.config.context,
            default_holiday_scope: this.holidayScopeState.scope,
        };
    }

    onHolidayScopeClick(scope) {
        if (this.holidayScopeState.scope === scope) {
            return;
        }
        const searchModel = this.env.searchModel;
        if (!searchModel) {
            return;
        }
        const targetName = SCOPE_FILTERS[scope];
        const otherScope = scope === "vp" ? "ch" : "vp";
        const otherName = SCOPE_FILTERS[otherScope];

        for (const filterName of [targetName, otherName]) {
            const item = this._findSearchItemByName(filterName);
            if (!item) {
                continue;
            }
            const isActive = this._isSearchItemActive(item);
            if (filterName === targetName && !isActive) {
                searchModel.toggleSearchItem(item.id);
            } else if (filterName === otherName && isActive) {
                searchModel.toggleSearchItem(item.id);
            }
        }
        this.holidayScopeState.scope = scope;
        this._updateDefaultScopeContext();
    }

    async createRecord({ group } = {}) {
        this._updateDefaultScopeContext();
        return super.createRecord({ group });
    }
}

export const publicHolidayMienListView = {
    ...listView,
    Controller: PublicHolidayMienListController,
};

registry.category("views").add("public_holiday_mien_list", publicHolidayMienListView);
