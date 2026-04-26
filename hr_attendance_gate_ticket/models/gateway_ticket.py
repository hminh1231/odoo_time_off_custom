from odoo import api, fields, models, _
from odoo.exceptions import UserError
import base64
import logging

_logger = logging.getLogger(__name__)


class GatewayTicket(models.Model):
    _name = 'gateway.ticket'
    _description = 'Gateway Ticket'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'check_in desc'

    name = fields.Char(string='Reference', required=True, copy=False, readonly=True,
                       default=lambda self: _('New'))

    employee_id = fields.Many2one('hr.employee', string='Employee', required=True,
                                   default=lambda self: self.env.user.employee_id,
                                   tracking=True)

    check_in = fields.Datetime(string='Check In', required=True,
                                default=fields.Datetime.now,
                                tracking=True)

    gate_ticket = fields.Char(string='Reason', tracking=True)
    gate_items = fields.Text(string='Items', tracking=True)
    checkout_time = fields.Datetime(string='Checkout Time', tracking=True)

    approver_id = fields.Many2one('res.users', string='First Approver',
                                   domain=[('share', '=', False)],
                                   tracking=True,
                                   help='User who can do the first approval')

    second_approver_id = fields.Many2one('res.users', string='Second Approver',
                                          domain=lambda self: [('share', '=', False), ('groups_id', 'in', [self.env.ref('base.group_user').id])],
                                          tracking=True,
                                          help='User who will do the second approval')

    third_approver_id = fields.Many2one('res.users', string='Third Approver',
                                         domain=lambda self: [('share', '=', False), ('groups_id', 'in', [self.env.ref('base.group_user').id])],
                                         tracking=True,
                                         help='User who will do the third approval')

    state = fields.Selection([
        ('draft', 'To Submit'),
        ('confirm', 'First Approval'),
        ('second_approve', 'Second Approval'),
        ('third_approve', 'Third Approval'),
        ('validate', 'Approved'),
        ('refuse', 'Refused'),
    ], string='Status', default='draft', tracking=True, copy=False)

    company_id = fields.Many2one('res.company', string='Company',
                                  default=lambda self: self.env.company)

    def _notify_approver(self, approver, message_body):
        """Send notification to a specific approver."""
        if not approver:
            return

        self.message_post(
            body=message_body,
            partner_ids=[approver.partner_id.id],
            subtype_xmlid='mail.mt_comment'
        )

    def action_submit(self):
        for ticket in self:
            if ticket.state != 'draft':
                raise UserError(_('Only draft tickets can be submitted.'))
            ticket.state = 'confirm'
            # Notify first approver
            if ticket.approver_id:
                ticket._notify_approver(
                    ticket.approver_id,
                    _('Gateway ticket submitted by <b>%(employee)s</b> is waiting for your approval.<br/>'
                      'Reason: %(reason)s',
                      employee=ticket.employee_id.name,
                      reason=ticket.gate_ticket or 'N/A')
                )

    def action_first_approve(self):
        for ticket in self:
            if ticket.state not in ['confirm', 'refuse']:
                raise UserError(_('Only tickets in first approval or refused state can be approved.'))
            if ticket.approver_id and ticket.approver_id != self.env.user:
                if not self.env.user.has_group('base.group_system'):
                    raise UserError(_('Only the assigned first approver or administrators can do first approval.'))
            ticket.state = 'second_approve'
            # Notify second approver
            if ticket.second_approver_id:
                ticket._notify_approver(
                    ticket.second_approver_id,
                    _('Gateway ticket for <b>%(employee)s</b> has been approved by <b>%(approver)s</b> '
                      'and is waiting for your second approval.<br/>'
                      'Reason: %(reason)s',
                      employee=ticket.employee_id.name,
                      approver=self.env.user.name,
                      reason=ticket.gate_ticket or 'N/A')
                )
            # Notify employee about first approval
            if ticket.employee_id.user_id:
                ticket._notify_approver(
                    ticket.employee_id.user_id,
                    _('Your gateway ticket has been approved by <b>%(approver)s</b>. '
                      'Waiting for second approval.',
                      approver=self.env.user.name)
                )

    def action_second_approve(self):
        for ticket in self:
            if ticket.state != 'second_approve':
                raise UserError(_('Only tickets in second approval state can be approved.'))
            if ticket.second_approver_id and ticket.second_approver_id != self.env.user:
                if not self.env.user.has_group('base.group_system'):
                    raise UserError(_('Only the assigned second approver or administrators can do second approval.'))
            if ticket.third_approver_id:
                ticket.state = 'third_approve'
                # Notify third approver
                ticket._notify_approver(
                    ticket.third_approver_id,
                    _('Gateway ticket for <b>%(employee)s</b> has passed second approval by <b>%(approver)s</b> '
                      'and is waiting for your final approval.<br/>'
                      'Reason: %(reason)s',
                      employee=ticket.employee_id.name,
                      approver=self.env.user.name,
                      reason=ticket.gate_ticket or 'N/A')
                )
                # Notify employee about second approval
                if ticket.employee_id.user_id:
                    ticket._notify_approver(
                        ticket.employee_id.user_id,
                        _('Your gateway ticket has passed second approval by <b>%(approver)s</b>. '
                          'Waiting for final approval.',
                          approver=self.env.user.name)
                    )
            else:
                ticket.state = 'validate'
                # Notify employee about final approval
                if ticket.employee_id.user_id:
                    ticket._notify_approver(
                        ticket.employee_id.user_id,
                        _('Your gateway ticket has been <b>fully approved</b> by <b>%(approver)s</b>.',
                          approver=self.env.user.name)
                    )
                # Post general message about approval
                ticket.message_post(
                    body=_('Gateway ticket fully approved.'),
                    subtype_xmlid='mail.mt_comment'
                )

    def action_third_approve(self):
        for ticket in self:
            if ticket.state != 'third_approve':
                raise UserError(_('Only tickets in third approval state can be finally approved.'))
            if ticket.third_approver_id and ticket.third_approver_id != self.env.user:
                if not self.env.user.has_group('base.group_system'):
                    raise UserError(_('Only the assigned third approver or administrators can do third approval.'))
            ticket.state = 'validate'
            # Notify employee about final approval
            if ticket.employee_id.user_id:
                ticket._notify_approver(
                    ticket.employee_id.user_id,
                    _('Your gateway ticket has been <b>fully approved</b> by <b>%(approver)s</b>.',
                      approver=self.env.user.name)
                )
            # Post general message about approval
            ticket.message_post(
                body=_('Gateway ticket fully approved.'),
                subtype_xmlid='mail.mt_comment'
            )

    def action_refuse(self):
        for ticket in self:
            if ticket.state not in ['confirm', 'second_approve', 'third_approve', 'validate']:
                raise UserError(_('Only confirmed, second approval, third approval, or approved tickets can be refused.'))
            old_state = ticket.state
            ticket.state = 'refuse'
            # Notify employee about refusal
            if ticket.employee_id.user_id:
                ticket._notify_approver(
                    ticket.employee_id.user_id,
                    _('Your gateway ticket has been <b>refused</b> by <b>%(approver)s</b>.',
                      approver=self.env.user.name)
                )
            # Notify all approvers about refusal
            approvers_to_notify = []
            if ticket.approver_id and ticket.approver_id != self.env.user:
                approvers_to_notify.append(ticket.approver_id)
            if ticket.second_approver_id and ticket.second_approver_id != self.env.user:
                approvers_to_notify.append(ticket.second_approver_id)
            if ticket.third_approver_id and ticket.third_approver_id != self.env.user:
                approvers_to_notify.append(ticket.third_approver_id)

            for approver in approvers_to_notify:
                ticket._notify_approver(
                    approver,
                    _('Gateway ticket for <b>%(employee)s</b> has been refused by <b>%(refuser)s</b>.',
                      employee=ticket.employee_id.name,
                      refuser=self.env.user.name)
                )

    def action_draft(self):
        for ticket in self:
            ticket.state = 'draft'

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('gateway.ticket') or _('New')

        tickets = super(GatewayTicket, self).create(vals_list)
        for ticket in tickets:
            _logger.info(f'Created gateway ticket ID {ticket.id}')
            ticket._generate_gate_ticket_pdf()
        return tickets

    def write(self, vals):
        result = super(GatewayTicket, self).write(vals)
        if any(field in vals for field in ['gate_ticket', 'gate_items', 'checkout_time', 'approver_id', 'second_approver_id']):
            for ticket in self:
                ticket._generate_gate_ticket_pdf()
        return result

    def _generate_gate_ticket_pdf(self):
        self.ensure_one()
        _logger.info(f'Attempting to generate PDF for gateway ticket {self.id}')

        try:
            pdf_content, _ = self.env['ir.actions.report']._render_qweb_pdf('hr_attendance_gate_ticket.action_report_gate_ticket_new', res_ids=[self.id])
            _logger.info(f'PDF generated, size: {len(pdf_content)} bytes')

            attachment_vals = {
                'name': f'Gate_Ticket_{self.employee_id.name}_{self.id}.pdf',
                'type': 'binary',
                'datas': base64.b64encode(pdf_content),
                'res_model': 'gateway.ticket',
                'res_id': self.id,
                'mimetype': 'application/pdf',
            }

            old_attachments = self.env['ir.attachment'].search([
                ('res_model', '=', 'gateway.ticket'),
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
