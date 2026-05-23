/** @odoo-module **/

import { TimeOffDashboard } from "@hr_holidays/dashboard/time_off_dashboard";
import { patch } from "@web/core/utils/patch";

patch(TimeOffDashboard.prototype, {
    setup() {
        super.setup(...arguments);
        this.state.daSuDung = 0;
        this.state.conLai = 0;
    },

    async loadDashboardData(date = false) {
        const context = this.getContext();
        if (date) {
            this.state.date = date;
        }
        const data = await this.orm.call(
            "hr.employee",
            "get_time_off_dashboard_data",
            [this.state.date],
            { context }
        );
        this.state.holidays = data.allocation_data;
        this.state.allocationRequests = data.allocation_request_amount;
        this.hasAccrualAllocation = data.has_accrual_allocation;
        this.state.daSuDung = data.da_su_dung ?? 0;
        this.state.conLai = data.con_lai ?? 0;
    },
});
