from odoo import api, fields, models, _
from odoo.exceptions import UserError
import base64
import logging

_logger = logging.getLogger(__name__)


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

    def _notify_approver(self, approver, message_body):
        """Send notification to a specific approver."""
        if not approver or self.attendance_type != 'gateway':
            return

        self.message_post(
            body=message_body,
            partner_ids=[approver.partner_id.id],
            subtype_xmlid='mail.mt_comment'
        )

    def action_submit(self):
        for attendance in self:
            if attendance.state != 'draft':
                raise UserError(_('Only draft attendances can be submitted.'))
            if attendance.attendance_type == 'gateway':
                attendance.state = 'confirm'
                # Notify first approver
                if attendance.approver_id:
                    attendance._notify_approver(
                        attendance.approver_id,
                        _('Gateway ticket submitted by <b>%(employee)s</b> is waiting for your approval.<br/>'
                          'Reason: %(reason)s',
                          employee=attendance.employee_id.name,
                          reason=attendance.gate_ticket or 'N/A')
                    )
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
                # Notify second approver
                if attendance.second_approver_id:
                    attendance._notify_approver(
                        attendance.second_approver_id,
                        _('Gateway ticket for <b>%(employee)s</b> has been approved by <b>%(approver)s</b> '
                          'and is waiting for your second approval.<br/>'
                          'Reason: %(reason)s',
                          employee=attendance.employee_id.name,
                          approver=self.env.user.name,
                          reason=attendance.gate_ticket or 'N/A')
                    )
                # Notify employee about first approval
                if attendance.employee_id.user_id:
                    attendance._notify_approver(
                        attendance.employee_id.user_id,
                        _('Your gateway ticket has been approved by <b>%(approver)s</b>. '
                          'Waiting for second approval.',
                          approver=self.env.user.name)
                    )
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
                # Notify third approver
                attendance._notify_approver(
                    attendance.third_approver_id,
                    _('Gateway ticket for <b>%(employee)s</b> has passed second approval by <b>%(approver)s</b> '
                      'and is waiting for your final approval.<br/>'
                      'Reason: %(reason)s',
                      employee=attendance.employee_id.name,
                      approver=self.env.user.name,
                      reason=attendance.gate_ticket or 'N/A')
                )
                # Notify employee about second approval
                if attendance.employee_id.user_id:
                    attendance._notify_approver(
                        attendance.employee_id.user_id,
                        _('Your gateway ticket has passed second approval by <b>%(approver)s</b>. '
                          'Waiting for final approval.',
                          approver=self.env.user.name)
                    )
            else:
                attendance.state = 'validate'
                # Notify employee about final approval
                if attendance.employee_id.user_id:
                    attendance._notify_approver(
                        attendance.employee_id.user_id,
                        _('Your gateway ticket has been <b>fully approved</b> by <b>%(approver)s</b>.',
                          approver=self.env.user.name)
                    )
                # Post general message about approval
                attendance.message_post(
                    body=_('Gateway ticket fully approved.'),
                    subtype_xmlid='mail.mt_comment'
                )

    def action_third_approve(self):
        for attendance in self:
            if attendance.state != 'third_approve':
                raise UserError(_('Only attendances in third approval state can be finally approved.'))
            if attendance.third_approver_id and attendance.third_approver_id != self.env.user:
                if not self.env.user.has_group('hr_attendance.group_hr_attendance_user'):
                    raise UserError(_('Only the assigned third approver or attendance administrators can do third approval.'))
            attendance.state = 'validate'
            # Notify employee about final approval
            if attendance.employee_id.user_id:
                attendance._notify_approver(
                    attendance.employee_id.user_id,
                    _('Your gateway ticket has been <b>fully approved</b> by <b>%(approver)s</b>.',
                      approver=self.env.user.name)
                )
            # Post general message about approval
            attendance.message_post(
                body=_('Gateway ticket fully approved.'),
                subtype_xmlid='mail.mt_comment'
            )

    def action_refuse(self):
        for attendance in self:
            if attendance.state not in ['confirm', 'second_approve', 'third_approve', 'validate']:
                raise UserError(_('Only confirmed, second approval, third approval, or approved attendances can be refused.'))
            old_state = attendance.state
            attendance.state = 'refuse'
            # Notify employee about refusal
            if attendance.employee_id.user_id:
                attendance._notify_approver(
                    attendance.employee_id.user_id,
                    _('Your gateway ticket has been <b>refused</b> by <b>%(approver)s</b>.',
                      approver=self.env.user.name)
                )
            # Notify all approvers about refusal
            approvers_to_notify = []
            if attendance.approver_id and attendance.approver_id != self.env.user:
                approvers_to_notify.append(attendance.approver_id)
            if attendance.second_approver_id and attendance.second_approver_id != self.env.user:
                approvers_to_notify.append(attendance.second_approver_id)
            if attendance.third_approver_id and attendance.third_approver_id != self.env.user:
                approvers_to_notify.append(attendance.third_approver_id)

            for approver in approvers_to_notify:
                attendance._notify_approver(
                    approver,
                    _('Gateway ticket for <b>%(employee)s</b> has been refused by <b>%(refuser)s</b>.',
                      employee=attendance.employee_id.name,
                      refuser=self.env.user.name)
                )

    def action_draft(self):
        for attendance in self:
            attendance.state = 'draft'

    @api.model_create_multi
    def create(self, vals_list):
        _logger.info(f'Creating attendance records: {vals_list}')
        attendances = super(HrAttendance, self).create(vals_list)
        for attendance in attendances:
            _logger.info(f'Created attendance ID {attendance.id}, type: {attendance.attendance_type}')
            if attendance.attendance_type == 'gateway':
                _logger.info(f'Calling _generate_gate_ticket_pdf for attendance {attendance.id}')
                attendance._generate_gate_ticket_pdf()
        return attendances

    def write(self, vals):
        result = super(HrAttendance, self).write(vals)
        if any(field in vals for field in ['gate_ticket', 'gate_items', 'checkout_time', 'approver_id', 'second_approver_id']):
            for attendance in self:
                if attendance.attendance_type == 'gateway':
                    attendance._generate_gate_ticket_pdf()
        return result

    def _generate_gate_ticket_pdf(self):
        self.ensure_one()
        _logger.info(f'Attempting to generate PDF for attendance {self.id}, type: {self.attendance_type}')

        if self.attendance_type != 'gateway':
            _logger.info(f'Skipping PDF generation - not a gateway ticket')
            return

        try:
            pdf_content, _ = self.env['ir.actions.report']._render_qweb_pdf('hr_attendance_gate_ticket.action_report_gate_ticket', res_ids=[self.id])
            _logger.info(f'PDF generated, size: {len(pdf_content)} bytes')

            attachment_vals = {
                'name': f'Gate_Ticket_{self.employee_id.name}_{self.id}.pdf',
                'type': 'binary',
                'datas': base64.b64encode(pdf_content),
                'res_model': 'hr.attendance',
                'res_id': self.id,
                'mimetype': 'application/pdf',
            }

            old_attachments = self.env['ir.attachment'].search([
                ('res_model', '=', 'hr.attendance'),
                ('res_id', '=', self.id),
                ('name', 'like', 'Gate_Ticket_%'),
            ])
            if old_attachments:
                _logger.info(f'Removing {len(old_attachments)} old attachments')
                old_attachments.unlink()

            attachment = self.env['ir.attachment'].create(attachment_vals)
            _logger.info(f'Created attachment: {attachment.name} (ID: {attachment.id})')
        except Exception as e:
            _logger.error(f'Error generating gate ticket PDF: {str(e)}', exc_info=True)
