/** @odoo-module **/

import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Component, onWillStart, useState } from "@odoo/owl";
import { standardActionServiceProps } from "@web/webclient/actions/action_service";

export class LugSessionList extends Component {
    static template = "lug_security_audit.LugSessionList";
    static props = { ...standardActionServiceProps };

    setup() {
        this.orm = useService("orm");
        this.actionService = useService("action");
        const today = new Date();
        this.state = useState({
            loading: true,
            data: null,
            filterYear: today.getFullYear(),
            filterMonth: today.getMonth() + 1,
            filterDay: today.getDate(),
            searchText: "",
        });
        onWillStart(() => this.loadSessions());
    }

    get filtersPayload() {
        return {
            year: this.state.filterYear,
            month: this.state.filterMonth,
            day: this.state.filterDay,
            search: this.state.searchText.trim(),
        };
    }

    async loadSessions() {
        this.state.loading = true;
        try {
            const data = await this.orm.call(
                "lug.security.dashboard",
                "get_session_list_data",
                [],
                { filters: this.filtersPayload }
            );
            this.state.data = data;
        } finally {
            this.state.loading = false;
        }
    }

    async onFilterChange() {
        await this.loadSessions();
    }

    async onSearchKeydown(ev) {
        if (ev.key === "Enter") {
            await this.loadSessions();
        }
    }

    async clearSearch() {
        this.state.searchText = "";
        await this.loadSessions();
    }

    async resetFilters() {
        const today = new Date();
        this.state.filterYear = today.getFullYear();
        this.state.filterMonth = today.getMonth() + 1;
        this.state.filterDay = today.getDate();
        this.state.searchText = "";
        await this.loadSessions();
    }

    async exportExcel() {
        const action = await this.orm.call(
            "lug.security.dashboard",
            "action_export_sessions",
            [],
            { filters: this.filtersPayload }
        );
        this.actionService.doAction(action);
    }
}

registry.category("actions").add("lug_security_session_list", LugSessionList);
