/** @odoo-module **/

import { loadBundle } from "@web/core/assets";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Component, onWillStart, useEffect, useRef, useState } from "@odoo/owl";
import { standardActionServiceProps } from "@web/webclient/actions/action_service";
const MIEN_COLORS = {
    Nam: "#2563eb",
    "Bắc": "#dc2626",
    "ĐTT": "#16a34a",
    VP: "#9333ea",
};

const STATUS_CHART_DEFS = [
    { key: "approved", label: "Đã duyệt", color: "#16a34a" },
    { key: "pending_approval", label: "Chờ duyệt", color: "#eab308" },
    { key: "pending_handover", label: "Chờ bàn giao", color: "#f97316" },
    { key: "refused", label: "Từ chối", color: "#dc2626" },
];

/** ~1.5 cm at 96dpi */
const MIEN_BAR_MAX_WIDTH_PX = 57;

const KPI_DRILL_TITLES = {
    on_leave_today: "Nhân viên đang nghỉ hôm nay",
    pending_approval: "Đơn chờ duyệt",
    approved_period: "Đơn đã duyệt trong kỳ",
    refused_period: "Đơn từ chối trong kỳ",
};

function normalizeDashboardData(data) {
    const empty = {
        kpi: {},
        request_status: {},
        filter_options: {},
        kpi_drill: {},
        mien_comparison: [],
        top_stores: [],
        on_leave_today_list: [],
        leave_workflow_tables: {},
        monthly_trend: [],
        pending_actions: {},
        staff_alerts: [],
        leave_details: [],
    };
    if (!data || typeof data !== "object") {
        return empty;
    }
    return {
        ...data,
        kpi: data.kpi || {},
        kpi_drill: data.kpi_drill || {},
        pending_actions: data.pending_actions || {},
        on_leave_today_list: Array.isArray(data.on_leave_today_list) ? data.on_leave_today_list : [],
        leave_workflow_tables: data.leave_workflow_tables || {},
        monthly_trend: Array.isArray(data.monthly_trend) ? data.monthly_trend : [],
        staff_alerts: Array.isArray(data.staff_alerts) ? data.staff_alerts : [],
        mien_comparison: Array.isArray(data.mien_comparison) ? data.mien_comparison : [],
        top_stores: Array.isArray(data.top_stores) ? data.top_stores : [],
        leave_details: Array.isArray(data.leave_details) ? data.leave_details : [],
    };
}

export class LeaveAnalyticsDashboard extends Component {
    static template = "hr_leave_analytics.LeaveAnalyticsDashboard";
    static props = { ...standardActionServiceProps };

    setup() {
        this.orm = useService("orm");
        this.actionService = useService("action");
        this.notification = useService("notification");
        this.statusChartRef = useRef("statusDonutChart");
        this.mienBarChartRef = useRef("mienBarChart");
        this.trendChartRef = useRef("trendLineChart");
        this.kpiDrillPanelRef = useRef("kpiDrillPanel");
        this.charts = { status: null, mienBar: null, trend: null };

        const actionContext = this.props.action.context || {};
        this.fixedMien = actionContext.dashboard_mien || false;

        const today = new Date();
        this.state = useState({
            loading: true,
            data: null,
            filterYear: today.getFullYear(),
            filterMonth: today.getMonth() + 1,
            filterStoreId: false,
            filterDepartmentId: false,
            activeKpiDrill: null,
            kpiDrillTitle: "",
            kpiDrillRows: [],
        });

        onWillStart(async () => {
            await loadBundle("web.chartjs_lib");
            await this.loadDashboard();
        });

        useEffect(() => {
            if (!this.state.loading && this.state.data) {
                this.renderAllCharts();
            }
            return () => this.destroyCharts();
        });
    }

    get filtersPayload() {
        return {
            employee_mien: this.fixedMien || false,
            year: this.state.filterYear,
            month: this.state.filterMonth,
            store_id: this.state.filterStoreId || false,
            department_id: this.state.filterDepartmentId || false,
        };
    }

    get dashboardTitle() {
        return this.state.data?.dashboard_title || "Dashboard";
    }

    get reportSubtitle() {
        return this.state.data?.report_subtitle || "Bảng thống kê Ngày nghỉ phép";
    }

    get periodLabel() {
        return this.state.data?.period_label || "";
    }

    get kpi() {
        return this.state.data?.kpi || {};
    }

    get kpiCards() {
        const k = this.kpi;
        return [
            { key: "total_employees", label: "Tổng NV", value: k.total_employees || 0, suffix: "", tier: "primary", drill: null },
            { key: "on_leave_today", label: "Đang nghỉ", value: k.on_leave_today || 0, suffix: "", tier: "info", drill: "on_leave_today" },
            { key: "pending_approval", label: "Chờ duyệt", value: k.pending_approval || 0, suffix: "", tier: k.pending_approval ? "warning" : "primary", drill: "pending_approval" },
            { key: "approved_count", label: "Đã duyệt", value: k.approved_count || 0, suffix: "", tier: "success", drill: "approved_period" },
            { key: "refused_count", label: "Từ chối", value: k.refused_count || 0, suffix: "", tier: k.refused_count ? "danger" : "primary", drill: "refused_period" },
            { key: "leave_rate_period", label: "Tỷ lệ nghỉ", value: k.leave_rate_period || 0, suffix: "%", tier: this.rateTier(k.leave_rate_period), drill: null },
        ];
    }

    get filterOptions() {
        return this.state.data?.filter_options || {};
    }

    get mienComparison() {
        return this.state.data?.mien_comparison || [];
    }

    get topStores() {
        return this.state.data?.top_stores || [];
    }

    get onLeaveTodayList() {
        return this.leaveWorkflowTables.on_leave_today || [];
    }

    get pendingApprovalTable() {
        return this.leaveWorkflowTables.pending_approval || [];
    }

    get pendingHandoverTable() {
        return this.leaveWorkflowTables.pending_handover || [];
    }

    get leaveWorkflowTables() {
        return this.state.data?.leave_workflow_tables || {};
    }

    get workflowKanbanColumns() {
        return [
            {
                key: "on_leave_today",
                title: "Nhân viên nghỉ hôm nay",
                headerClass: "o_kanban_col_header_employee",
                rows: this.onLeaveTodayList,
                emptyText: "Không có ai nghỉ hôm nay",
                drill: "on_leave_today",
            },
            {
                key: "pending_approval",
                title: "Đơn chờ duyệt",
                headerClass: "o_kanban_col_header_pending",
                rows: this.pendingApprovalTable,
                emptyText: "Không có đơn chờ duyệt",
                drill: "pending_approval",
            },
            {
                key: "pending_handover",
                title: "Đơn chờ bàn giao",
                headerClass: "o_kanban_col_header_handover",
                rows: this.pendingHandoverTable,
                emptyText: "Không có đơn chờ bàn giao",
                drill: "pending_handover",
            },
        ];
    }

    get monthlyTrend() {
        return this.state.data?.monthly_trend || [];
    }

    get pendingActions() {
        return this.state.data?.pending_actions || {};
    }

    get staffAlerts() {
        return this.state.data?.staff_alerts || [];
    }

    get leaveDetails() {
        return this.state.data?.leave_details || [];
    }

    get leaveDetailsPreview() {
        return this.leaveDetails.slice(0, 30);
    }

    getMienColor(mien) {
        return MIEN_COLORS[mien] || "#6b7280";
    }

    rateTier(rate) {
        const value = Number(rate) || 0;
        if (value >= 10) return "danger";
        if (value >= 5) return "warning";
        return "success";
    }

    rateTierClass(rate) {
        return `o_rate_${this.rateTier(rate)}`;
    }

    kpiCardClass(card) {
        const map = {
            primary: "o_kpi_card o_kpi_card_primary",
            info: "o_kpi_card o_kpi_card_info",
            success: "o_kpi_card o_kpi_card_success",
            warning: "o_kpi_card o_kpi_card_warning",
            danger: "o_kpi_card o_kpi_card_danger",
        };
        let base = map[card.tier] || map.primary;
        if (card.key === "leave_rate_period") {
            base = `o_kpi_card o_kpi_card_${this.rateTier(card.value)}`;
        }
        if (card.drill && this.state.activeKpiDrill === card.drill) {
            base += " o_kpi_card_active";
        }
        return base;
    }

    alertClass(alert) {
        return `o_staff_alert o_staff_alert_${alert.level || "info"}`;
    }

    statusBadgeClass(row) {
        const map = {
            danger: "o_status_badge o_status_badge_danger",
            success: "o_status_badge o_status_badge_success",
            warning: "o_status_badge o_status_badge_warning",
            secondary: "o_status_badge o_status_badge_secondary",
        };
        return map[row.status_class] || map.secondary;
    }

    destroyCharts() {
        for (const key of Object.keys(this.charts)) {
            if (this.charts[key]) {
                this.charts[key].destroy();
                this.charts[key] = null;
            }
        }
    }

    async loadDashboard() {
        this.state.loading = true;
        this.closeKpiDrill();
        const raw = await this.orm.call(
            "hr.leave.analytics.dashboard",
            "get_dashboard_data",
            [],
            { filters: this.filtersPayload }
        );
        const data = normalizeDashboardData(raw);
        if (data.filters) {
            this.state.filterYear = data.filters.year || this.state.filterYear;
            this.state.filterMonth = data.filters.month || this.state.filterMonth;
            this.state.filterStoreId = data.filters.store_id || false;
            this.state.filterDepartmentId = data.filters.department_id || false;
        }
        this.state.data = data;
        this.state.loading = false;
    }

    async onFilterChange() {
        await this.loadDashboard();
    }

    async resetFilters() {
        const today = new Date();
        this.state.filterYear = today.getFullYear();
        this.state.filterMonth = today.getMonth() + 1;
        this.state.filterStoreId = false;
        this.state.filterDepartmentId = false;
        await this.loadDashboard();
    }

    renderAllCharts() {
        this.renderStatusChart();
        this.renderMienBarChart();
        this.renderTrendChart();
    }

    renderStatusChart() {
        const canvas = this.statusChartRef.el;
        const rs = this.state.data?.request_status || {};
        if (!canvas) {
            return;
        }

        const segments = STATUS_CHART_DEFS.map((def) => ({
            ...def,
            value: Number(rs[def.key]) || 0,
        }));
        const activeSegments = segments.filter((seg) => seg.value > 0);
        const chartSegments = activeSegments.length
            ? activeSegments
            : [{ label: "Không có dữ liệu", value: 1, color: "#e5e7eb" }];
        const hasData = activeSegments.length > 0;

        if (this.charts.status) {
            this.charts.status.destroy();
        }

        this.charts.status = new Chart(canvas, {
            type: "doughnut",
            data: {
                labels: chartSegments.map((seg) => seg.label),
                datasets: [{
                    data: chartSegments.map((seg) => seg.value),
                    backgroundColor: chartSegments.map((seg) => seg.color),
                    hoverBackgroundColor: chartSegments.map((seg) => seg.color),
                    borderColor: "#ffffff",
                    borderWidth: 2,
                }],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                cutout: "58%",
                plugins: {
                    colors: { enabled: false },
                    legend: {
                        position: "bottom",
                        labels: {
                            boxWidth: 12,
                            boxHeight: 12,
                            padding: 10,
                            font: { size: 10 },
                            generateLabels: () =>
                                segments.map((seg, index) => ({
                                    text: `${seg.label} (${seg.value})`,
                                    fillStyle: seg.color,
                                    strokeStyle: seg.color,
                                    fontColor: "#374151",
                                    hidden: false,
                                    index,
                                })),
                        },
                        onClick: () => {},
                    },
                    tooltip: {
                        enabled: hasData,
                        callbacks: {
                            label: (ctx) => {
                                const seg = chartSegments[ctx.dataIndex];
                                return `${seg.label}: ${seg.value}`;
                            },
                        },
                    },
                },
            },
        });
    }

    renderMienBarChart() {
        const canvas = this.mienBarChartRef.el;
        const items = this.mienComparison;
        if (!canvas || !items.length) {
            return;
        }

        if (this.charts.mienBar) {
            this.charts.mienBar.destroy();
        }

        const barColors = items.map((item) => this.getMienColor(item.mien));

        this.charts.mienBar = new Chart(canvas, {
            type: "bar",
            data: {
                labels: items.map((item) => item.label),
                datasets: [{
                    label: "Ngày nghỉ đã duyệt",
                    data: items.map((item) => item.leave_days || 0),
                    backgroundColor: barColors,
                    hoverBackgroundColor: barColors,
                    borderColor: barColors,
                    borderWidth: 1,
                    borderRadius: 4,
                    maxBarThickness: MIEN_BAR_MAX_WIDTH_PX,
                }],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                layout: {
                    padding: { left: 8, right: 8 },
                },
                plugins: {
                    colors: { enabled: false },
                    legend: { display: false },
                },
                scales: {
                    x: {
                        grid: { display: false },
                        ticks: { font: { size: 11 } },
                    },
                    y: {
                        beginAtZero: true,
                        ticks: { stepSize: 1 },
                        grid: { color: "#e5e7eb" },
                    },
                },
                datasets: {
                    bar: {
                        categoryPercentage: Math.min(0.85, 0.35 * items.length),
                        barPercentage: 0.9,
                        maxBarThickness: MIEN_BAR_MAX_WIDTH_PX,
                    },
                },
            },
        });
    }

    renderTrendChart() {
        const canvas = this.trendChartRef.el;
        const trend = this.monthlyTrend;
        if (!canvas || !trend.length) return;

        if (this.charts.trend) {
            this.charts.trend.destroy();
        }

        const rates = trend.map((t) => t.leave_rate || 0);
        this.charts.trend = new Chart(canvas, {
            type: "line",
            data: {
                labels: trend.map((t) => t.label),
                datasets: [{
                    label: "Tỷ lệ nghỉ (%)",
                    data: rates,
                    borderColor: "#2563eb",
                    backgroundColor: "rgba(37, 99, 235, 0.1)",
                    fill: true,
                    tension: 0.3,
                    pointRadius: 3,
                }],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { display: false } },
                scales: {
                    y: {
                        beginAtZero: true,
                        ticks: { callback: (v) => `${v}%` },
                    },
                },
            },
        });
    }

    async openDrill(drillType) {
        if (!drillType) {
            return;
        }
        try {
            const action = await this.orm.call(
                "hr.leave.analytics.dashboard",
                "action_drill_down",
                [drillType],
                { filters: this.filtersPayload, record_id: false }
            );
            if (!action) {
                this.notification.add("Không mở được danh sách đơn nghỉ.", { type: "warning" });
                return;
            }
            await this.actionService.doAction(action);
        } catch (error) {
            this.notification.add("Không mở được danh sách đơn nghỉ.", { type: "danger" });
            console.error("openDrill failed", error);
        }
    }

    async openList(exportType) {
        const action = await this.orm.call(
            "hr.leave.analytics.dashboard",
            "action_export_excel",
            [exportType],
            { filters: this.filtersPayload }
        );
        this.actionService.doAction(action);
    }

    async drillDown(type, recordId) {
        const action = await this.orm.call(
            "hr.leave.analytics.dashboard",
            "action_drill_down",
            [type],
            { filters: this.filtersPayload, record_id: recordId || false }
        );
        this.actionService.doAction(action);
    }

    async openLeave(leaveId) {
        if (!leaveId) return;
        this.actionService.doAction({
            type: "ir.actions.act_window",
            res_model: "hr.leave",
            res_id: leaveId,
            views: [[false, "form"]],
            target: "current",
        });
    }

    showKpiDrill(drillType) {
        const cache = this.state.data?.kpi_drill || {};
        const rows = cache[drillType] || [];
        this.state.activeKpiDrill = drillType;
        const title = KPI_DRILL_TITLES[drillType] || "";
        this.state.kpiDrillTitle = rows.length ? `${title} (${rows.length})` : title;
        this.state.kpiDrillRows = rows;
        requestAnimationFrame(() => {
            const panel = this.kpiDrillPanelRef.el;
            if (panel) {
                panel.scrollIntoView({ behavior: "smooth", block: "nearest" });
            }
        });
    }

    closeKpiDrill() {
        this.state.activeKpiDrill = null;
        this.state.kpiDrillTitle = "";
        this.state.kpiDrillRows = [];
    }

    onKpiClick(drillType) {
        if (!drillType) {
            return;
        }
        if (this.state.activeKpiDrill === drillType) {
            this.closeKpiDrill();
            return;
        }
        this.showKpiDrill(drillType);
    }
}

registry.category("actions").add("hr_leave_analytics_dashboard", LeaveAnalyticsDashboard);
