# Part of Odoo. See LICENSE file for full copyright and licensing details.



from calendar import monthrange

from dateutil.relativedelta import relativedelta



from odoo import api, fields, models

from odoo.exceptions import AccessError

from odoo.tools.safe_eval import safe_eval

from .res_users import MIEN_ACTION_XMLIDS





class HrLeaveAnalyticsDashboard(models.AbstractModel):

    _name = "hr.leave.analytics.dashboard"

    _inherit = ["hr.leave.analytics.job.title.mixin"]

    _description = "HR Leave Analytics Dashboard"



    _MIEN_ORDER = ("VP", "Nam", "ĐTT", "Bắc")

    _STORE_ALERT_MIN_ON_LEAVE = 2



    @api.model

    def _default_period(self):

        today = fields.Date.context_today(self)

        start = today.replace(day=1)

        return start, today



    @api.model

    def _resolve_employee_mien(self, filters=None):

        filters = filters or {}

        return filters.get("employee_mien") or self.env.context.get("dashboard_mien") or False



    @api.model

    def _parse_filters(self, filters=None):

        filters = filters or {}

        date_from = filters.get("date_from")

        date_to = filters.get("date_to")

        year = filters.get("year")

        month = filters.get("month")

        if year and month:

            year = int(year)

            month = int(month)

            date_from = fields.Date.from_string(f"{year:04d}-{month:02d}-01")

            date_to = date_from.replace(day=monthrange(year, month)[1])

        elif not date_from or not date_to:

            date_from, date_to = self._default_period()

        else:

            date_from = fields.Date.to_date(date_from)

            date_to = fields.Date.to_date(date_to)

        active_mien = self._resolve_employee_mien(filters)

        store_id = filters.get("store_id")

        department_id = filters.get("department_id")

        return {

            "date_from": date_from,

            "date_to": date_to,

            "year": date_from.year,

            "month": date_from.month,

            "employee_mien": active_mien,

            "store_id": int(store_id) if store_id else False,

            "department_id": int(department_id) if department_id else False,

        }



    @api.model

    def _mien_domain(self, filters):

        domain = [("company_id", "in", self.env.companies.ids)]

        if filters.get("employee_mien"):

            domain.append(("employee_mien", "=", filters["employee_mien"]))

        return domain



    @api.model

    def _employee_matches_filters(self, employee, filters):

        if not employee:

            return False

        if not self._employee_matches_mien(employee, filters.get("employee_mien")):

            return False

        store_id = filters.get("store_id")

        if store_id:

            store = self._employee_store_info(employee)

            if store.get("store_id") != store_id:

                return False

        department_id = filters.get("department_id")

        if department_id and employee.department_id.id != department_id:

            return False

        return True



    @api.model

    def _period_label(self, filters):

        filters = self._parse_filters(filters)

        return f"Tháng {filters['month']}/{filters['year']}"



    @api.model

    def _business_days_in_month(self, date_from, date_to):

        count = 0

        day = date_from

        while day <= date_to:

            if day.weekday() < 5:

                count += 1

            day += relativedelta(days=1)

        return count

    @api.model
    def _empty_mien_status_info(self):
        return {
            "waiting_approval": 0,
            "waiting_handover": 0,
            "refused": 0,
            "waiting_approval_items": [],
            "waiting_handover_items": [],
            "refused_items": [],
        }

    @api.model
    def _leave_status_item_label(self, leave):
        employee_name = leave.employee_id.name or ""
        leave_type = leave.holiday_status_id.name or ""
        date_from = (
            leave.request_date_from.strftime("%d/%m/%Y")
            if leave.request_date_from
            else ""
        )
        parts = [part for part in (employee_name, leave_type, date_from) if part]
        return " — ".join(parts)

    @api.model
    def _leave_handover_item_label(self, leave):
        label = self._leave_status_item_label(leave)
        recipient = getattr(leave, "handover_recipient_display", "") or ""
        if recipient:
            return f"{label} (bàn giao: {recipient})"
        return label

    @api.model
    def _resolve_leave_mien(self, leave):
        employee = leave.employee_id
        if not employee:
            return False
        if leave.employee_leave_mien:
            return leave.employee_leave_mien
        if hasattr(employee, "_get_leave_mien"):
            return employee._get_leave_mien()
        return employee.mien or False

    @api.model
    def _classify_leave_status_bucket(self, leave):
        if leave.state == "refuse":
            return "refused"
        if leave.state not in ("confirm", "validate1"):
            return False
        if "status_display_label" in leave._fields:
            label = (leave.status_display_label or "").lower()
            if "bàn giao" in label:
                return "waiting_handover"
        if "handover_status_waiting" in leave._fields and leave.handover_status_waiting:
            return "waiting_handover"
        return "waiting_approval"

    @api.model
    def _get_mien_status_info(self, mien_list, filters=None):
        """Đơn đang mở (chờ duyệt/bàn giao) + từ chối trong kỳ lọc."""
        if not mien_list:
            return {}

        filters = self._parse_filters(filters)
        date_from = filters["date_from"]
        date_to = filters["date_to"]

        Leave = self.env["hr.leave"].sudo().with_context(active_test=False)
        leaves = Leave.search(
            [
                "|",
                ("state", "in", ("confirm", "validate1")),
                "&",
                "&",
                ("state", "=", "refuse"),
                ("request_date_from", "<=", date_to),
                ("request_date_to", ">=", date_from),
            ],
            order="create_date desc, id desc",
        )
        info = {mien: self._empty_mien_status_info() for mien in mien_list}

        for leave in leaves:
            employee = leave.employee_id
            if not employee:
                continue
            if employee.company_id.id not in self.env.companies.ids:
                continue
            if not self._employee_matches_filters(employee, filters):
                continue
            mien = self._resolve_leave_mien(leave)
            if mien not in info:
                continue
            bucket = self._classify_leave_status_bucket(leave)
            if not bucket:
                continue
            item = {
                "label": self._leave_status_item_label(leave),
                "leave_id": leave.id,
            }
            if bucket == "refused":
                info[mien]["refused"] += 1
                info[mien]["refused_items"].append(item)
            elif bucket == "waiting_handover":
                handover_item = dict(item)
                handover_item["label"] = self._leave_handover_item_label(leave)
                info[mien]["waiting_handover"] += 1
                info[mien]["waiting_handover_items"].append(handover_item)
            else:
                info[mien]["waiting_approval"] += 1
                info[mien]["waiting_approval_items"].append(item)
        return info

    @api.model
    def _format_vn_short_date(self, value):
        if not value:
            return ""
        day = fields.Date.to_date(value)
        return f"{day.day} thg {day.month}"

    @api.model
    def _leave_detail_status_label(self, leave):
        if "status_display_label" in leave._fields and leave.status_display_label:
            return leave.status_display_label
        selection = dict(leave._fields["state"]._description_selection(leave.env))
        if leave.state == "validate":
            return "Được duyệt"
        if leave.state == "refuse":
            return "Bị từ chối"
        return selection.get(leave.state, leave.state or "")

    @api.model
    def _leave_detail_status_class(self, leave):
        if leave.state == "refuse":
            return "danger"
        if leave.state == "validate":
            return "success"
        if leave.state in ("confirm", "validate1"):
            return "warning"
        return "secondary"

    @api.model
    def _serialize_leave_detail_row(self, leave, stt):
        employee = leave.employee_id
        version = employee.current_version_id if employee else False
        job_title_key = (version.job_title if version else "") or (employee.job_title if employee else "")
        return {
            "stt": stt,
            "leave_id": leave.id,
            "employee_mien": self._resolve_leave_mien(leave) or "",
            "employee_id_hrm": (employee.id_hrm or "").strip() if employee else "",
            "employee_name": (employee.name or "") if employee else "",
            "ma_bo_phan": (employee.ma_bo_phan or "").strip().upper() if employee else "",
            "job_title": self._job_title_label(job_title_key, employee=employee),
            "request_date_from": self._format_vn_short_date(leave.request_date_from),
            "request_date_to": self._format_vn_short_date(leave.request_date_to),
            "number_of_days": round(leave.number_of_days or 0.0, 2),
            "state": leave.state,
            "status_label": self._leave_detail_status_label(leave),
            "status_class": self._leave_detail_status_class(leave),
            "leave_type": leave.holiday_status_id.name or "—",
        }

    @api.model
    def _get_leave_details(self, filters):
        """Chi tiết đơn nghỉ — cùng nguồn hr.leave như menu Ngày nghỉ, lọc theo tháng hiện tại."""
        filters = self._parse_filters(filters)
        date_from = filters["date_from"]
        date_to = filters["date_to"]
        active_mien = filters.get("employee_mien")

        domain = [
            ("state", "!=", "cancel"),
            ("request_date_from", "<=", date_to),
            ("request_date_to", ">=", date_from),
        ]
        if active_mien:
            domain.append(("employee_leave_mien", "=", active_mien))
        if filters.get("store_id"):
            domain.append(("employee_id.ma_bo_phan_id.store_id", "=", filters["store_id"]))
        if filters.get("department_id"):
            domain.append(("employee_id.department_id", "=", filters["department_id"]))

        Leave = self.env["hr.leave"].sudo().with_context(active_test=False)
        leaves = Leave.search(
            domain,
            order="request_date_from desc, employee_id, id",
            limit=500,
        )

        rows = []
        for idx, leave in enumerate(leaves, 1):
            employee = leave.employee_id
            if not employee:
                continue
            if employee.company_id.id not in self.env.companies.ids:
                continue
            if not self._employee_matches_filters(employee, filters):
                continue
            rows.append(self._serialize_leave_detail_row(leave, idx))
        return rows

    @api.model
    def _employee_job_title_key(self, employee):
        if not employee:
            return ""
        version = employee.current_version_id
        return (version.job_title if version else "") or employee.job_title or ""

    @api.model
    def _employee_store_info(self, employee):
        if not employee or not employee.ma_bo_phan_id:
            return {"store_name": "—", "store_id": False, "store_key": False}
        store_code = employee.ma_bo_phan_id
        store_name = (store_code.code or "").strip() or "—"
        store_id = store_code.store_id.id if store_code.store_id else store_code.id
        return {"store_name": store_name, "store_id": store_id, "store_key": store_id}

    @api.model
    def _employee_matches_mien(self, employee, active_mien):
        if not active_mien:
            return True
        mien = employee.mien or False
        if not mien and employee.ma_bo_phan_id:
            mien = employee.ma_bo_phan_id.mien or False
        return mien == active_mien

    @api.model
    def _month_validated_leaves(self, filters):
        """Đơn nghỉ đã duyệt trong tháng — nguồn hr.leave."""
        filters = self._parse_filters(filters)
        date_from = filters["date_from"]
        date_to = filters["date_to"]
        active_mien = filters.get("employee_mien")

        domain = [
            ("state", "=", "validate"),
            ("request_date_from", "<=", date_to),
            ("request_date_to", ">=", date_from),
        ]
        if active_mien:
            domain.append(("employee_leave_mien", "=", active_mien))
        if filters.get("store_id"):
            domain.append(("employee_id.ma_bo_phan_id.store_id", "=", filters["store_id"]))
        if filters.get("department_id"):
            domain.append(("employee_id.department_id", "=", filters["department_id"]))

        Leave = self.env["hr.leave"].sudo().with_context(active_test=False)
        leaves = Leave.search(domain)
        company_ids = set(self.env.companies.ids)
        result = []
        for leave in leaves:
            employee = leave.employee_id
            if not employee or employee.company_id.id not in company_ids:
                continue
            if not self._employee_matches_filters(employee, filters):
                continue
            if active_mien and self._resolve_leave_mien(leave) != active_mien:
                continue
            result.append(leave)
        return result

    @api.model
    def _get_request_status_summary(self, filters):
        """Tổng hợp đơn nghỉ theo trạng thái — tách rõ trong kỳ vs đang chờ xử lý."""
        filters = self._parse_filters(filters)
        date_from = filters["date_from"]
        date_to = filters["date_to"]
        active_mien = filters.get("employee_mien")

        period_domain = [
            ("state", "!=", "cancel"),
            ("request_date_from", "<=", date_to),
            ("request_date_to", ">=", date_from),
        ]
        if active_mien:
            period_domain.append(("employee_leave_mien", "=", active_mien))
        if filters.get("store_id"):
            period_domain.append(("employee_id.ma_bo_phan_id.store_id", "=", filters["store_id"]))
        if filters.get("department_id"):
            period_domain.append(("employee_id.department_id", "=", filters["department_id"]))

        Leave = self.env["hr.leave"].sudo().with_context(active_test=False)
        period_leaves = Leave.search(period_domain)

        approved = refused = pending_in_period = 0
        leave_days_approved = 0.0
        for leave in period_leaves:
            employee = leave.employee_id
            if not employee or not self._employee_matches_filters(employee, filters):
                continue
            if leave.state == "validate":
                approved += 1
                leave_days_approved += leave.number_of_days or 0.0
            elif leave.state == "refuse":
                refused += 1
            elif leave.state in ("confirm", "validate1"):
                pending_in_period += 1

        mien_list = (active_mien,) if active_mien else self._MIEN_ORDER
        status_info = self._get_mien_status_info(mien_list, filters)
        pending_approval = sum(info["waiting_approval"] for info in status_info.values())
        pending_handover = sum(info["waiting_handover"] for info in status_info.values())

        return {
            "total_requests": approved + refused + pending_in_period,
            "approved": approved,
            "refused": refused,
            "pending_in_period": pending_in_period,
            "pending_approval": pending_approval,
            "pending_handover": pending_handover,
            "pending_open": pending_approval + pending_handover,
            "leave_days_approved": round(leave_days_approved, 2),
            "refused_in_period": refused,
        }

    @api.model
    def _get_kpi_summary(self, filters):
        filters = self._parse_filters(filters)
        today = fields.Date.context_today(self)
        status = self._get_request_status_summary(filters)

        Employee = self.env["hr.employee"].sudo().with_context(active_test=False)
        employees = Employee.search([
            ("active", "=", True),
            ("company_id", "in", self.env.companies.ids),
        ])
        total_employees = sum(
            1 for employee in employees if self._employee_matches_filters(employee, filters)
        )

        on_leave_domain = [
            ("state", "=", "validate"),
            ("request_date_from", "<=", today),
            ("request_date_to", ">=", today),
        ]
        if filters.get("employee_mien"):
            on_leave_domain.append(("employee_leave_mien", "=", filters["employee_mien"]))
        if filters.get("store_id"):
            on_leave_domain.append(("employee_id.ma_bo_phan_id.store_id", "=", filters["store_id"]))
        if filters.get("department_id"):
            on_leave_domain.append(("employee_id.department_id", "=", filters["department_id"]))

        Leave = self.env["hr.leave"].sudo().with_context(active_test=False)
        on_leave_employee_ids = set()
        for leave in Leave.search(on_leave_domain):
            employee = leave.employee_id
            if employee and self._employee_matches_filters(employee, filters):
                on_leave_employee_ids.add(employee.id)

        on_leave_today = len(on_leave_employee_ids)
        leave_rate_today = (
            round((on_leave_today / total_employees) * 100, 2) if total_employees else 0.0
        )

        business_days = self._business_days_in_month(filters["date_from"], filters["date_to"])
        leave_rate_period = 0.0
        if total_employees and business_days:
            leave_rate_period = round(
                (status["leave_days_approved"] / (total_employees * business_days)) * 100,
                2,
            )

        return {
            "total_employees": total_employees,
            "on_leave_today": on_leave_today,
            "pending_approval": status["pending_approval"],
            "pending_handover": status["pending_handover"],
            "pending_requests": status["pending_open"],
            "approved_count": status["approved"],
            "refused_count": status["refused"],
            "leave_rate_today": leave_rate_today,
            "leave_rate_period": leave_rate_period,
            "approved_in_period": status["approved"],
            "leave_days_in_period": status["leave_days_approved"],
        }

    @api.model
    def _serialize_leave_table_row(self, leave, stt):
        employee = leave.employee_id
        store = self._employee_store_info(employee) if employee else {"store_name": "—"}
        job_title_key = self._employee_job_title_key(employee) if employee else ""
        return {
            "stt": stt,
            "leave_id": leave.id,
            "employee_name": (employee.name or "") if employee else "",
            "store_name": store["store_name"],
            "job_title": self._job_title_label(job_title_key, employee=employee) or "—",
            "number_of_days": round(leave.number_of_days or 0.0, 2),
        }

    @api.model
    def _search_leaves_for_drill(self, drill_type, filters):
        filters = self._parse_filters(filters)
        today = fields.Date.context_today(self)
        Leave = self.env["hr.leave"].sudo().with_context(active_test=False)

        if drill_type == "on_leave_today":
            domain = [
                ("state", "=", "validate"),
                ("request_date_from", "<=", today),
                ("request_date_to", ">=", today),
            ]
            order = "employee_id, request_date_from"
        elif drill_type in ("pending_approval", "pending_handover"):
            domain = [("state", "in", ("confirm", "validate1"))]
            order = "create_date desc, id desc"
        elif drill_type == "approved_period":
            domain = [
                ("state", "=", "validate"),
                ("request_date_from", "<=", filters["date_to"]),
                ("request_date_to", ">=", filters["date_from"]),
            ]
            order = "request_date_from desc, employee_id"
        elif drill_type == "refused_period":
            domain = [
                ("state", "=", "refuse"),
                ("request_date_from", "<=", filters["date_to"]),
                ("request_date_to", ">=", filters["date_from"]),
            ]
            order = "request_date_from desc, employee_id"
        else:
            return Leave.browse()

        if filters.get("employee_mien"):
            domain.append(("employee_leave_mien", "=", filters["employee_mien"]))
        if filters.get("store_id"):
            domain.append(("employee_id.ma_bo_phan_id.store_id", "=", filters["store_id"]))
        if filters.get("department_id"):
            domain.append(("employee_id.department_id", "=", filters["department_id"]))

        leaves = Leave.search(domain, order=order)
        if drill_type == "pending_approval":
            bucket = "waiting_approval"
        elif drill_type == "pending_handover":
            bucket = "waiting_handover"
        else:
            return leaves

        return leaves.filtered(
            lambda leave: self._classify_leave_status_bucket(leave) == bucket
        )

    @api.model
    def _get_leave_table(self, drill_type, filters, limit=50):
        rows = []
        for leave in self._search_leaves_for_drill(drill_type, filters):
            employee = leave.employee_id
            if not employee or not self._employee_matches_filters(employee, filters):
                continue
            rows.append(self._serialize_leave_table_row(leave, len(rows) + 1))
            if len(rows) >= limit:
                break
        return rows

    @api.model
    def _get_leave_workflow_tables(self, filters, limit=50):
        return {
            "on_leave_today": self._get_leave_table("on_leave_today", filters, limit),
            "pending_approval": self._get_leave_table("pending_approval", filters, limit),
            "pending_handover": self._get_leave_table("pending_handover", filters, limit),
        }

    @api.model
    def _get_on_leave_today_list(self, filters, limit=50):
        return self._get_leave_table("on_leave_today", filters, limit)

    @api.model
    def _serialize_drill_leave_row(self, leave):
        employee = leave.employee_id
        store = self._employee_store_info(employee) if employee else {"store_name": "—"}
        return {
            "leave_id": leave.id,
            "employee_id": employee.id if employee else False,
            "employee_name": (employee.name or "") if employee else "",
            "store_name": store["store_name"],
            "leave_type": leave.holiday_status_id.name or "—",
            "request_date_from": self._format_vn_short_date(leave.request_date_from),
            "request_date_to": self._format_vn_short_date(leave.request_date_to),
            "number_of_days": round(leave.number_of_days or 0.0, 2),
            "status_label": self._leave_detail_status_label(leave),
            "status_class": self._leave_detail_status_class(leave),
        }

    @api.model
    def _leaves_for_kpi_drill(self, drill_type, filters):
        rows = []
        for leave in self._search_leaves_for_drill(drill_type, filters):
            employee = leave.employee_id
            if not employee or not self._employee_matches_filters(employee, filters):
                continue
            rows.append(self._serialize_drill_leave_row(leave))
        return rows

    @api.model
    def get_kpi_drill_data(self, drill_type, filters=None):
        titles = {
            "on_leave_today": "Nhân viên đang nghỉ hôm nay",
            "pending_approval": "Đơn chờ duyệt",
            "approved_period": "Đơn đã duyệt trong kỳ",
            "refused_period": "Đơn từ chối trong kỳ",
        }
        if drill_type not in titles:
            return {"title": "", "rows": []}
        return {
            "title": titles[drill_type],
            "drill_type": drill_type,
            "rows": self._leaves_for_kpi_drill(drill_type, filters),
        }

    @api.model
    def _get_monthly_trend(self, filters, months=12):
        filters = self._parse_filters(filters)
        ref_date = filters["date_to"].replace(day=1)
        Employee = self.env["hr.employee"].sudo().with_context(active_test=False)
        employees = Employee.search([
            ("active", "=", True),
            ("company_id", "in", self.env.companies.ids),
        ])
        total_employees = sum(
            1 for employee in employees if self._employee_matches_filters(employee, filters)
        )

        Leave = self.env["hr.leave"].sudo().with_context(active_test=False)
        trend = []
        for offset in range(months - 1, -1, -1):
            month_start = ref_date - relativedelta(months=offset)
            month_end = month_start.replace(day=monthrange(month_start.year, month_start.month)[1])
            business_days = self._business_days_in_month(month_start, month_end)

            domain = [
                ("state", "=", "validate"),
                ("request_date_from", "<=", month_end),
                ("request_date_to", ">=", month_start),
            ]
            if filters.get("employee_mien"):
                domain.append(("employee_leave_mien", "=", filters["employee_mien"]))
            if filters.get("store_id"):
                domain.append(("employee_id.ma_bo_phan_id.store_id", "=", filters["store_id"]))
            if filters.get("department_id"):
                domain.append(("employee_id.department_id", "=", filters["department_id"]))

            leave_days = 0.0
            for leave in Leave.search(domain):
                employee = leave.employee_id
                if employee and self._employee_matches_filters(employee, filters):
                    leave_days += leave.number_of_days or 0.0

            rate = 0.0
            if total_employees and business_days:
                rate = round((leave_days / (total_employees * business_days)) * 100, 2)

            trend.append({
                "label": f"T{month_start.month}/{month_start.year}",
                "month": month_start.month,
                "year": month_start.year,
                "leave_days": round(leave_days, 2),
                "leave_rate": rate,
            })
        return trend

    @api.model
    def _get_pending_actions(self, filters):
        filters = self._parse_filters(filters)
        active_mien = filters.get("employee_mien")
        mien_list = (active_mien,) if active_mien else self._MIEN_ORDER
        status_info = self._get_mien_status_info(mien_list, filters)

        approval_items = []
        handover_items = []
        for info in status_info.values():
            approval_items.extend(info.get("waiting_approval_items", []))
            handover_items.extend(info.get("waiting_handover_items", []))

        return {
            "pending_approval": len(approval_items),
            "pending_handover": len(handover_items),
            "approval_items": approval_items[:20],
            "handover_items": handover_items[:20],
        }

    @api.model
    def _get_staff_alerts(self, filters, limit=15):
        """Cảnh báo nhân sự cho lãnh đạo."""
        filters = self._parse_filters(filters)
        today = fields.Date.context_today(self)
        alerts = []

        # Cửa hàng tỷ lệ nghỉ cao hôm nay
        for alert_row in self._get_store_alerts(filters, limit=50):
            rate = alert_row.get("on_leave_rate", 0.0)
            if rate >= 30:
                alerts.append({
                    "level": "danger",
                    "icon": "fa-exclamation-triangle",
                    "message": f"{alert_row['store_name']} nghỉ {rate}% nhân sự hôm nay.",
                    "store_id": alert_row.get("store_id"),
                    "type": "store",
                })
            elif rate >= 10:
                alerts.append({
                    "level": "warning",
                    "icon": "fa-warning",
                    "message": f"{alert_row['store_name']} nghỉ {rate}% nhân sự — cần theo dõi.",
                    "store_id": alert_row.get("store_id"),
                    "type": "store",
                })

        for row in self._get_top_stores(filters, limit=10):
            if row.get("leave_rate", 0) >= 50 and not any(
                a.get("store_id") == row.get("store_id") for a in alerts
            ):
                alerts.append({
                    "level": "warning",
                    "icon": "fa-shopping-bag",
                    "message": f"{row['store_name']} có {row['leave_rate']}% NV nghỉ trong kỳ.",
                    "store_id": row.get("store_id"),
                    "type": "store",
                })

        # Nhân viên nghỉ liên tiếp >= 5 ngày (đơn đã duyệt đang active hôm nay)
        Leave = self.env["hr.leave"].sudo().with_context(active_test=False)
        consecutive_domain = [
            ("state", "=", "validate"),
            ("request_date_from", "<=", today),
            ("request_date_to", ">=", today),
            ("number_of_days", ">=", 5),
        ]
        if filters.get("employee_mien"):
            consecutive_domain.append(("employee_leave_mien", "=", filters["employee_mien"]))
        for leave in Leave.search(consecutive_domain, limit=20):
            employee = leave.employee_id
            if not employee or not self._employee_matches_filters(employee, filters):
                continue
            days = int(leave.number_of_days or 0)
            alerts.append({
                "level": "warning",
                "icon": "fa-user-times",
                "message": f"{employee.name} nghỉ {days} ngày liên tiếp.",
                "employee_id": employee.id,
                "leave_id": leave.id,
                "type": "employee",
            })

        # Phòng ban chỉ còn <= 1 nhân sự làm việc hôm nay
        from collections import defaultdict
        dept_total = defaultdict(set)
        dept_on_leave = defaultdict(set)
        Employee = self.env["hr.employee"].sudo().with_context(active_test=False)
        for employee in Employee.search([
            ("active", "=", True),
            ("company_id", "in", self.env.companies.ids),
            ("department_id", "!=", False),
        ]):
            if not self._employee_matches_filters(employee, filters):
                continue
            dept_total[employee.department_id.id].add(employee.id)

        on_leave_domain = [
            ("state", "=", "validate"),
            ("request_date_from", "<=", today),
            ("request_date_to", ">=", today),
        ]
        if filters.get("employee_mien"):
            on_leave_domain.append(("employee_leave_mien", "=", filters["employee_mien"]))
        for leave in Leave.search(on_leave_domain):
            employee = leave.employee_id
            if not employee or not employee.department_id:
                continue
            if not self._employee_matches_filters(employee, filters):
                continue
            dept_on_leave[employee.department_id.id].add(employee.id)

        Department = self.env["hr.department"].sudo()
        for dept_id, member_ids in dept_total.items():
            if len(member_ids) < 2:
                continue
            on_leave = len(dept_on_leave.get(dept_id, set()))
            working = len(member_ids) - on_leave
            if working <= 1:
                dept = Department.browse(dept_id)
                alerts.append({
                    "level": "danger",
                    "icon": "fa-building",
                    "message": f"Phòng {dept.name} chỉ còn {working} nhân sự làm việc.",
                    "department_id": dept_id,
                    "type": "department",
                })

        level_order = {"danger": 0, "warning": 1, "info": 2}
        alerts.sort(key=lambda row: level_order.get(row["level"], 9))
        return alerts[:limit]

    @api.model
    def _get_watch_employees(self, filters, limit=10):
        """Top nhân viên nghỉ nhiều trong kỳ — tổng hợp từ hr.leave."""
        from collections import defaultdict

        agg = defaultdict(lambda: {"leave_days": 0.0, "employee": None})
        for leave in self._month_validated_leaves(filters):
            employee = leave.employee_id
            bucket = agg[employee.id]
            bucket["employee"] = employee
            bucket["leave_days"] += leave.number_of_days or 0.0

        ranked = sorted(
            agg.values(),
            key=lambda row: (-row["leave_days"], row["employee"].name or ""),
        )
        rows = []
        for row in ranked[:limit]:
            employee = row["employee"]
            store = self._employee_store_info(employee)
            rows.append({
                "employee_name": employee.name or "",
                "store_name": store["store_name"],
                "job_title": self._job_title_label(
                    self._employee_job_title_key(employee), employee=employee
                ) or "—",
                "leave_days": round(row["leave_days"], 2),
                "employee_id": employee.id,
            })
        return rows

    @api.model
    def _get_top_stores(self, filters, limit=10):
        """Top cửa hàng theo tỷ lệ NV nghỉ trong kỳ (NV nghỉ / tổng NV)."""
        from collections import defaultdict

        filters = self._parse_filters(filters)
        active_mien = filters.get("employee_mien")

        employees_on_leave_by_store = defaultdict(set)
        leave_days_by_store = defaultdict(float)
        top_employee_by_store = defaultdict(lambda: {"leave_days": 0.0, "job_title": ""})
        store_meta = {}

        for leave in self._month_validated_leaves(filters):
            employee = leave.employee_id
            store = self._employee_store_info(employee)
            store_key = store["store_key"]
            if not store_key:
                continue
            store_meta[store_key] = store
            employees_on_leave_by_store[store_key].add(employee.id)
            days = leave.number_of_days or 0.0
            leave_days_by_store[store_key] += days
            top_row = top_employee_by_store[store_key]
            if days > top_row["leave_days"]:
                top_row["leave_days"] = days
                top_row["job_title"] = self._employee_job_title_key(employee)

        employee_count_by_store = defaultdict(set)
        Employee = self.env["hr.employee"].sudo().with_context(active_test=False)
        emp_domain = [("active", "=", True), ("company_id", "in", self.env.companies.ids)]
        for employee in Employee.search(emp_domain):
            if not self._employee_matches_filters(employee, filters):
                continue
            store = self._employee_store_info(employee)
            if store["store_key"]:
                employee_count_by_store[store["store_key"]].add(employee.id)
                store_meta.setdefault(store["store_key"], store)

        store_keys = set(store_meta.keys()) | set(employees_on_leave_by_store.keys())
        ranked_keys = sorted(
            store_keys,
            key=lambda key: (
                -(
                    len(employees_on_leave_by_store.get(key, set()))
                    / max(len(employee_count_by_store.get(key, set())), 1)
                ),
                -len(employees_on_leave_by_store.get(key, set())),
                store_meta.get(key, {}).get("store_name", ""),
            ),
        )
        rows = []
        for store_key in ranked_keys[:limit]:
            if not employees_on_leave_by_store.get(store_key):
                continue
            meta = store_meta[store_key]
            emp_count = len(employee_count_by_store.get(store_key, set()))
            on_leave_count = len(employees_on_leave_by_store.get(store_key, set()))
            leave_rate = round((on_leave_count / emp_count) * 100, 1) if emp_count else 0.0
            top_job = top_employee_by_store[store_key]["job_title"]
            rows.append({
                "store_name": meta["store_name"],
                "job_title": self._job_title_label(top_job) or "—",
                "employee_count": emp_count,
                "on_leave_count": on_leave_count,
                "leave_days": round(leave_days_by_store.get(store_key, 0.0), 2),
                "leave_rate": leave_rate,
                "store_id": meta["store_id"],
            })
        return rows

    @api.model
    def _get_store_alerts(self, filters, limit=10):
        """Cảnh báo cửa hàng — chỉ hiện khi hôm nay có >= 2 NV nghỉ cùng cửa hàng."""
        from collections import defaultdict

        filters = self._parse_filters(filters)
        active_mien = filters.get("employee_mien")
        today = fields.Date.context_today(self)
        min_on_leave = self._STORE_ALERT_MIN_ON_LEAVE

        on_leave_by_store = defaultdict(set)
        on_leave_titles_by_store = defaultdict(set)
        Leave = self.env["hr.leave"].sudo().with_context(active_test=False)
        on_leave_domain = [
            ("state", "=", "validate"),
            ("request_date_from", "<=", today),
            ("request_date_to", ">=", today),
        ]
        if active_mien:
            on_leave_domain.append(("employee_leave_mien", "=", active_mien))

        for leave in Leave.search(on_leave_domain):
            employee = leave.employee_id
            if not employee or employee.company_id.id not in self.env.companies.ids:
                continue
            if active_mien and self._resolve_leave_mien(leave) != active_mien:
                continue
            store = self._employee_store_info(employee)
            if not store["store_key"]:
                continue
            on_leave_by_store[store["store_key"]].add(employee.id)
            job_key = self._employee_job_title_key(employee)
            if job_key:
                on_leave_titles_by_store[store["store_key"]].add(job_key)

        employee_count_by_store = defaultdict(set)
        store_meta = {}
        Employee = self.env["hr.employee"].sudo().with_context(active_test=False)
        for employee in Employee.search([
            ("active", "=", True),
            ("company_id", "in", self.env.companies.ids),
        ]):
            if not self._employee_matches_mien(employee, active_mien):
                continue
            store = self._employee_store_info(employee)
            if not store["store_key"]:
                continue
            employee_count_by_store[store["store_key"]].add(employee.id)
            store_meta[store["store_key"]] = store

        alert_store_keys = {
            store_key
            for store_key, employees in on_leave_by_store.items()
            if len(employees) >= min_on_leave
        }
        ranked_keys = sorted(
            alert_store_keys,
            key=lambda key: (
                -(
                    len(on_leave_by_store.get(key, set()))
                    / max(len(employee_count_by_store.get(key, set())), 1)
                ),
                -len(on_leave_by_store.get(key, set())),
                store_meta[key]["store_name"],
            ),
        )
        rows = []
        top_stores_by_id = {
            row["store_id"]: row["job_title"]
            for row in self._get_top_stores(filters, limit=50)
        }
        for store_key in ranked_keys[:limit]:
            meta = store_meta[store_key]
            emp_count = len(employee_count_by_store.get(store_key, set()))
            on_leave = len(on_leave_by_store.get(store_key, set()))
            rate = round((on_leave / emp_count) * 100, 2) if emp_count else 0.0
            titles = on_leave_titles_by_store.get(store_key, set())
            if titles:
                job_label = self._job_titles_label(",".join(sorted(titles)))
            else:
                job_label = top_stores_by_id.get(meta["store_id"], "—")
            rows.append({
                "store_name": meta["store_name"],
                "job_title": job_label or "—",
                "employee_count": emp_count,
                "on_leave_today": on_leave,
                "on_leave_rate": rate,
                "store_id": meta["store_id"],
            })
        return rows

    @api.model
    def _build_status_sections(self, status_info):
        status_info = status_info or self._empty_mien_status_info()
        section_defs = (
            ("waiting_approval", "Chờ duyệt", "waiting_approval_items"),
            ("waiting_handover", "Chờ bàn giao", "waiting_handover_items"),
            ("refused", "Từ chối", "refused_items"),
        )
        sections = []
        for idx, (count_key, label, items_key) in enumerate(section_defs, 1):
            sections.append({
                "no": idx,
                "label": label,
                "count": status_info.get(count_key, 0),
                "items": status_info.get(items_key, []),
            })
        return sections

    @api.model
    def _build_mien_comparison(self, filters):
        """Tổng hợp miền từ hr.leave + hr.employee theo kỳ lọc."""
        filters = self._parse_filters(filters)
        active_mien = filters.get("employee_mien")
        mien_list = (active_mien,) if active_mien in self._MIEN_ORDER else self._MIEN_ORDER
        status_info = self._get_mien_status_info(mien_list, filters)
        labels = dict(
            self.env["hr.leave.analytics.mien.summary"]._fields["employee_mien"]._description_selection(
                self.env
            )
        )
        totals = {mien: {"employee_count": 0, "leave_days": 0.0} for mien in mien_list}

        Employee = self.env["hr.employee"].sudo().with_context(active_test=False)
        for employee in Employee.search([
            ("active", "=", True),
            ("company_id", "in", self.env.companies.ids),
        ]):
            mien = employee.mien or False
            if not mien and employee.ma_bo_phan_id:
                mien = employee.ma_bo_phan_id.mien or False
            if mien not in totals:
                continue
            if self._employee_matches_filters(employee, filters):
                totals[mien]["employee_count"] += 1

        for leave in self._month_validated_leaves(filters):
            mien = self._resolve_leave_mien(leave)
            if mien in totals:
                totals[mien]["leave_days"] += leave.number_of_days or 0.0

        business_days = self._business_days_in_month(filters["date_from"], filters["date_to"])
        result = []
        for mien in mien_list:
            employee_count = totals[mien]["employee_count"]
            leave_days = round(totals[mien]["leave_days"], 2)
            if employee_count and business_days:
                leave_rate = round((leave_days / (employee_count * business_days)) * 100, 2)
            else:
                leave_rate = 0.0
            info = status_info.get(mien, self._empty_mien_status_info())
            result.append({
                "mien": mien,
                "label": labels.get(mien, mien),
                "employee_count": employee_count,
                "leave_days": leave_days,
                "leave_rate": leave_rate,
                "status_sections": self._build_status_sections(info),
            })
        return result

    @api.model
    def _serialize_mien_rows(self, rows, active_mien=False, status_info_by_mien=None, date_from=None, date_to=None):

        labels = dict(self.env["hr.leave.analytics.mien.summary"]._fields["employee_mien"]._description_selection(self.env))

        mien_list = (active_mien,) if active_mien in self._MIEN_ORDER else self._MIEN_ORDER

        totals = {mien: {"employee_count": 0, "leave_days": 0.0} for mien in mien_list}

        for row in rows:

            if row.employee_mien not in totals:

                continue

            totals[row.employee_mien]["employee_count"] += row.employee_count or 0

            totals[row.employee_mien]["leave_days"] += row.leave_days or 0.0



        if date_from and date_to:
            business_days = self._business_days_in_month(date_from, date_to)
        else:
            business_days = self._business_days_in_month(*self._default_period())

        result = []
        for mien in mien_list:

            employee_count = totals[mien]["employee_count"]

            leave_days = round(totals[mien]["leave_days"], 2)

            if employee_count and business_days:

                leave_rate = round((leave_days / (employee_count * business_days)) * 100, 2)

            else:

                leave_rate = 0.0

            status_info = (status_info_by_mien or {}).get(mien, self._empty_mien_status_info())
            result.append(

                {

                    "mien": mien,

                    "label": labels.get(mien, mien),

                    "employee_count": employee_count,

                    "leave_days": leave_days,

                    "leave_rate": leave_rate,

                    "status_sections": self._build_status_sections(status_info),

                }

            )

        return result



    @api.model

    def action_open_for_user(self):

        user = self.env.user

        allowed = user._hr_leave_analytics_allowed_miens_list()

        if allowed is None:

            xmlid = "hr_leave_analytics.action_hr_leave_analytics_dashboard_client"

        else:

            if not allowed:

                raise AccessError("Bạn không có quyền xem báo cáo nghỉ phép.")

            preferred = [m for m in ("VP", "Nam", "ĐTT", "Bắc") if m in allowed]

            xmlid = MIEN_ACTION_XMLIDS[preferred[0]]

        action = self.env.ref(xmlid).sudo().read()[0]

        return action



    @api.model
    def get_filter_options(self, filters=None):
        filters = self._parse_filters(filters)
        active_mien = filters.get("employee_mien")
        today = fields.Date.context_today(self)

        Store = self.env["hr.store"].sudo()
        store_domain = []
        if active_mien:
            store_domain.append(("mien", "=", active_mien))
        stores = Store.search_read(store_domain, ["id", "name"], order="name")

        Department = self.env["hr.department"].sudo()
        departments = Department.search_read([], ["id", "name"], order="name", limit=200)

        years = list(range(today.year, today.year - 4, -1))
        months = [{"value": m, "label": f"Tháng {m}"} for m in range(1, 13)]

        return {
            "years": years,
            "months": months,
            "stores": [{"id": s["id"], "name": s["name"]} for s in stores],
            "departments": [{"id": d["id"], "name": d["name"]} for d in departments],
            "current_year": filters["year"],
            "current_month": filters["month"],
        }

    @api.model

    def get_dashboard_data(self, filters=None):

        filters = self._parse_filters(filters)

        active_mien = filters["employee_mien"]

        user = self.env.user

        if active_mien:

            user._hr_leave_analytics_check_mien_access(active_mien)

        else:

            user._hr_leave_analytics_check_overview_access()

        mien_rows = self._build_mien_comparison(filters)

        watch_employees = self._get_watch_employees(filters)
        top_stores = self._get_top_stores(filters)
        kpi = self._get_kpi_summary(filters)
        request_status = self._get_request_status_summary(filters)
        filter_options = self.get_filter_options(filters)
        on_leave_today_list = self._get_on_leave_today_list(filters)
        leave_workflow_tables = self._get_leave_workflow_tables(filters)
        monthly_trend = self._get_monthly_trend(filters)
        pending_actions = self._get_pending_actions(filters)
        staff_alerts = self._get_staff_alerts(filters)

        Mien = self.env["hr.leave.analytics.mien.summary"]

        mien_label = False

        if active_mien:

            labels = dict(Mien._fields["employee_mien"]._description_selection(self.env))

            mien_label = labels.get(active_mien, active_mien)

        leave_details = self._get_leave_details(filters)

        kpi_drill = {
            drill_type: self._leaves_for_kpi_drill(drill_type, filters)
            for drill_type in (
                "on_leave_today",
                "pending_approval",
                "approved_period",
                "refused_period",
            )
        }

        dashboard_title = f"Dashboard {mien_label}" if mien_label else "Dashboard Tổng quan"

        return {

            "title": mien_label or "Tổng quan toàn hệ thống",

            "dashboard_title": dashboard_title,

            "report_subtitle": "Bảng thống kê Ngày nghỉ phép",

            "period_label": self._period_label(filters),

            "is_regional_dashboard": bool(active_mien),

            "mien_chart_title": (

                f"{mien_label} — Ngày nghỉ đã duyệt & trạng thái đơn"

                if mien_label

                else "So sánh các Miền — Ngày nghỉ đã duyệt & trạng thái đơn"

            ),

            "active_mien": active_mien or False,

            "filters": {

                "date_from": fields.Date.to_string(filters["date_from"]),

                "date_to": fields.Date.to_string(filters["date_to"]),

                "year": filters["year"],

                "month": filters["month"],

                "employee_mien": active_mien or False,

                "store_id": filters.get("store_id") or False,

                "department_id": filters.get("department_id") or False,

            },

            "filter_options": filter_options,

            "kpi": kpi,

            "request_status": request_status,

            "mien_comparison": mien_rows,

            "top_stores": top_stores,

            "watch_employees": watch_employees,

            "on_leave_today_list": on_leave_today_list,

            "leave_workflow_tables": leave_workflow_tables,

            "monthly_trend": monthly_trend,

            "pending_actions": pending_actions,

            "staff_alerts": staff_alerts,

            "kpi_drill": kpi_drill,

            "leave_details": leave_details,

        }



    @api.model

    def action_drill_down(self, drill_type, filters=None, record_id=False):

        filters = self._parse_filters(filters)

        base_domain = self._mien_domain(filters)



        if drill_type == "employee" and record_id:

            action = self.env.ref("hr_leave_analytics.action_hr_leave_analytics_employee_watch").sudo().read()[0]

            action["domain"] = base_domain + [("employee_id", "=", record_id)]

            return action

        if drill_type == "store" and record_id:

            action = self.env.ref("hr_leave_analytics.action_hr_leave_analytics_store_rank").sudo().read()[0]

            action["domain"] = base_domain + [("store_id", "=", record_id)]

            return action

        if drill_type == "mien" and record_id:

            action = self.env.ref("hr_leave_analytics.action_hr_leave_analytics_mien_compare").sudo().read()[0]

            action["domain"] = base_domain + [("employee_mien", "=", record_id)]

            return action

        if drill_type == "pending_handover":
            return self._action_open_hr_leaves(filters, pending_type="handover")

        if drill_type == "pending_approval":
            return self._action_open_hr_leaves(filters, pending_type="approval")

        if drill_type == "on_leave_today":
            return self._action_open_hr_leaves(filters, pending_type="on_leave_today")

        if drill_type == "approved_period":
            return self._action_open_hr_leaves(filters, pending_type="approved_period")

        if drill_type == "refused_period":
            return self._action_open_hr_leaves(filters, pending_type="refused_period")



        action = self.env.ref("hr_leave_analytics.action_hr_leave_analytics_report").sudo().read()[0]

        action["domain"] = base_domain + [("state", "=", "validate")]

        return action

    @api.model
    def _action_open_hr_leaves(self, filters, pending_type="approval"):
        filters = self._parse_filters(filters)
        today = fields.Date.context_today(self)
        Leave = self.env["hr.leave"].sudo().with_context(active_test=False)
        domain = [("state", "!=", "cancel")]
        name = "Đơn nghỉ phép"

        if pending_type == "approval":
            name = "Đơn chờ duyệt"
            base_domain = [("state", "in", ("confirm", "validate1"))]
            if filters.get("employee_mien"):
                base_domain.append(("employee_leave_mien", "=", filters["employee_mien"]))
            if filters.get("store_id"):
                base_domain.append(("employee_id.ma_bo_phan_id.store_id", "=", filters["store_id"]))
            if filters.get("department_id"):
                base_domain.append(("employee_id.department_id", "=", filters["department_id"]))
            leave_ids = [
                leave.id
                for leave in Leave.search(base_domain, order="create_date desc, id desc")
                if self._classify_leave_status_bucket(leave) == "waiting_approval"
                and self._employee_matches_filters(leave.employee_id, filters)
            ]
            domain = [("id", "in", leave_ids)] if leave_ids else [("id", "=", 0)]

        elif pending_type == "handover":
            name = "Đơn chờ bàn giao"
            base_domain = [("state", "in", ("confirm", "validate1"))]
            if filters.get("employee_mien"):
                base_domain.append(("employee_leave_mien", "=", filters["employee_mien"]))
            if filters.get("store_id"):
                base_domain.append(("employee_id.ma_bo_phan_id.store_id", "=", filters["store_id"]))
            if filters.get("department_id"):
                base_domain.append(("employee_id.department_id", "=", filters["department_id"]))
            leave_ids = [
                leave.id
                for leave in Leave.search(base_domain, order="create_date desc, id desc")
                if self._classify_leave_status_bucket(leave) == "waiting_handover"
                and self._employee_matches_filters(leave.employee_id, filters)
            ]
            domain = [("id", "in", leave_ids)] if leave_ids else [("id", "=", 0)]

        elif pending_type == "on_leave_today":
            domain = [
                ("state", "=", "validate"),
                ("request_date_from", "<=", today),
                ("request_date_to", ">=", today),
            ]
            name = "Nhân viên nghỉ hôm nay"
        elif pending_type == "approved_period":
            domain = [
                ("state", "=", "validate"),
                ("request_date_from", "<=", filters["date_to"]),
                ("request_date_to", ">=", filters["date_from"]),
            ]
            name = "Đơn đã duyệt trong kỳ"
        elif pending_type == "refused_period":
            domain = [
                ("state", "=", "refuse"),
                ("request_date_from", "<=", filters["date_to"]),
                ("request_date_to", ">=", filters["date_from"]),
            ]
            name = "Đơn từ chối trong kỳ"

        if pending_type not in ("approval", "handover"):
            if filters.get("employee_mien"):
                domain.append(("employee_leave_mien", "=", filters["employee_mien"]))
            if filters.get("store_id"):
                domain.append(("employee_id.ma_bo_phan_id.store_id", "=", filters["store_id"]))
            if filters.get("department_id"):
                domain.append(("employee_id.department_id", "=", filters["department_id"]))

        action = self.env.ref(
            "hr_holidays.hr_leave_action_action_approve_department"
        ).sudo().read()[0]
        action["name"] = name
        action["domain"] = domain
        ctx = action.get("context") or {}
        if isinstance(ctx, str):
            ctx = safe_eval(ctx, {"uid": self.env.uid})
        ctx = dict(ctx)
        ctx.pop("search_default_waiting_for_me", None)
        ctx.pop("search_default_waiting_for_me_manager", None)
        ctx.pop("search_default_current_year", None)
        ctx["create"] = False
        ctx["hide_employee_name"] = 0
        action["context"] = ctx
        return action



    @api.model

    def action_export_excel(self, export_type, filters=None):

        filters = self._parse_filters(filters)

        if export_type == "mien_compare" and not filters.get("employee_mien"):
            domain = [("company_id", "in", self.env.companies.ids)]
        elif export_type == "leave_details":
            Report = self.env["hr.leave.analytics.report"]
            domain = Report._analytics_base_domain({
                "date_from": fields.Date.to_string(filters["date_from"]),
                "date_to": fields.Date.to_string(filters["date_to"]),
                "employee_mien": filters.get("employee_mien"),
            })
        else:
            domain = self._mien_domain(filters)

        mapping = {

            "watch_employees": "hr_leave_analytics.action_hr_leave_analytics_employee_watch",

            "top_stores": "hr_leave_analytics.action_hr_leave_analytics_store_rank",

            "store_alerts": "hr_leave_analytics.action_hr_leave_analytics_store_alert",

            "leave_details": "hr_leave_analytics.action_hr_leave_analytics_report",

            "mien_compare": "hr_leave_analytics.action_hr_leave_analytics_mien_compare",

        }

        xmlid = mapping.get(export_type, mapping["mien_compare"])

        action = self.env.ref(xmlid).sudo().read()[0]

        action["domain"] = domain

        return action


