from odoo import api, fields, models


class HrEmployeeTimeoff(models.Model):
    _inherit = 'hr.employee'

    phep_chuan = fields.Float(string='Phép chuẩn')
    tong_so_phep = fields.Float(string='Tổng số phép')
    da_su_dung = fields.Float(
        string='Đã sử dụng',
        compute='_compute_time_off_summary',
        store=True,
    )
    con_lai = fields.Float(
        string='Còn lại',
        compute='_compute_time_off_summary',
        store=True,
    )
    ngay_het_han = fields.Date(string='Ngày hết hạn')

    @api.depends('tong_so_phep')
    def _compute_time_off_summary(self):
        if 'hr.leave.type' not in self.env:
            for employee in self:
                employee.da_su_dung = 0.0
                employee.con_lai = employee.tong_so_phep
            return
        leave_types = self.env['hr.leave.type'].sudo().search([
            ('requires_allocation', '=', 'yes'),
        ])
        for employee in self:
            if not leave_types:
                employee.da_su_dung = 0.0
                employee.con_lai = employee.tong_so_phep
                continue
            data = leave_types.get_allocation_data(employee)
            emp_data = data.get(employee, [])
            total_taken = sum(
                item[1].get('virtual_leaves_taken', 0.0) for item in emp_data
            )
            employee.da_su_dung = total_taken
            employee.con_lai = employee.tong_so_phep - total_taken


class HrLeaveTimeOffSummary(models.Model):
    _inherit = 'hr.leave'

    def _recompute_employee_time_off_summary(self):
        employees = self.mapped('employee_id').filtered(lambda e: e.id)
        if employees:
            employees._compute_time_off_summary()

    def action_confirm(self):
        res = super().action_confirm()
        self._recompute_employee_time_off_summary()
        return res

    def action_validate(self):
        res = super().action_validate()
        self._recompute_employee_time_off_summary()
        return res

    def action_refuse(self):
        res = super().action_refuse()
        self._recompute_employee_time_off_summary()
        return res

    def action_draft(self):
        res = super().action_draft()
        self._recompute_employee_time_off_summary()
        return res
