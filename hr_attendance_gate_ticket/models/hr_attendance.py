from odoo import api, fields, models, _
from odoo.exceptions import UserError


class HrAttendance(models.Model):
    _inherit = 'hr.attendance'

    attendance_type = fields.Selection([
        ('attendance', 'Attendance'),
        ('gateway', 'Gateway'),
    ], string='Type', default='attendance', required=True)

    gate_ticket = fields.Char(string='Reason')
    gate_items = fields.Text(string='Items')
    checkout_time = fields.Datetime(string='Checkout Time')

    approver_id = fields.Many2one('res.users', string='First Approver',
                                   domain=[('share', '=', False)],
                                   tracking=True,
                                   help='User who can do the first approval')

    second_approver_id = fields.Many2one('res.users', string='Second Approver',
                                          domain=lambda self: [('share', '=', False), ('group_ids', 'in', [self.env.ref('hr_attendance.group_hr_attendance_officer').id])],
                                          tracking=True,
                                          help='HR Officer who will do the second approval')

    third_approver_id = fields.Many2one('res.users', string='Third Approver',
                                         domain=lambda self: [('share', '=', False), ('group_ids', 'in', [self.env.ref('hr_attendance.group_hr_attendance_officer').id])],
                                         tracking=True,
                                         help='HR Officer who will do the third approval')

    state = fields.Selection([
        ('draft', 'To Submit'),
        ('confirm', 'First Approval'),
        ('second_approve', 'Second Approval'),
        ('third_approve', 'Third Approval'),
        ('validate', 'Approved'),
        ('refuse', 'Refused'),
    ], string='Status', default='draft', tracking=True, copy=False)

    def action_submit(self):
        for attendance in self:
            if attendance.state != 'draft':
                raise UserError(_('Only draft attendances can be submitted.'))
            if attendance.attendance_type == 'gateway':
                attendance.state = 'confirm'
            else:
                attendance.state = 'validate'

    def action_first_approve(self):
        for attendance in self:
            if attendance.state not in ['confirm', 'refuse']:
                raise UserError(_('Only attendances in first approval or refused state can be approved.'))
            if attendance.approver_id and attendance.approver_id != self.env.user:
                if not self.env.user.has_group('hr_attendance.group_hr_attendance_user'):
                    raise UserError(_('Only the assigned first approver or attendance administrators can do first approval.'))
            if attendance.attendance_type == 'gateway':
                attendance.state = 'second_approve'
            else:
                attendance.state = 'validate'

    def action_second_approve(self):
        for attendance in self:
            if attendance.state != 'second_approve':
                raise UserError(_('Only attendances in second approval state can be approved.'))
            if attendance.second_approver_id and attendance.second_approver_id != self.env.user:
                if not self.env.user.has_group('hr_attendance.group_hr_attendance_user'):
                    raise UserError(_('Only the assigned second approver or attendance administrators can do second approval.'))
            if attendance.third_approver_id:
                attendance.state = 'third_approve'
            else:
                attendance.state = 'validate'

    def action_third_approve(self):
        for attendance in self:
            if attendance.state != 'third_approve':
                raise UserError(_('Only attendances in third approval state can be finally approved.'))
            if attendance.third_approver_id and attendance.third_approver_id != self.env.user:
                if not self.env.user.has_group('hr_attendance.group_hr_attendance_user'):
                    raise UserError(_('Only the assigned third approver or attendance administrators can do third approval.'))
            attendance.state = 'validate'

    def action_refuse(self):
        for attendance in self:
            if attendance.state not in ['confirm', 'second_approve', 'third_approve', 'validate']:
                raise UserError(_('Only confirmed, second approval, third approval, or approved attendances can be refused.'))
            attendance.state = 'refuse'

    def action_draft(self):
        for attendance in self:
            attendance.state = 'draft'
