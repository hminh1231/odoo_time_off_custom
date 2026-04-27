import base64
import logging

from markupsafe import Markup

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class HrEmployeeGateTicket(models.Model):
    _name = 'hr.employee.gate.ticket'
    _description = 'HR Employee Gate Ticket'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'check_in desc'

    name = fields.Char(
        string='Reference',
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: _('New'),
    )
    employee_id = fields.Many2one(
        'hr.employee',
        string='Employee',
        required=True,
        default=lambda self: self.env.user.employee_id,
        tracking=True,
    )
    check_in = fields.Datetime(
        string='Check In',
        required=True,
        default=fields.Datetime.now,
        tracking=True,
    )
    gate_ticket = fields.Char(string='Reason', tracking=True)
    gate_items = fields.Text(string='Items', tracking=True)
    checkout_time = fields.Datetime(string='Checkout Time', tracking=True)

    approver_id = fields.Many2one(
        'res.users',
        string='First Approver',
        domain=[('share', '=', False)],
        tracking=True,
        help='User who can do the first approval',
    )
    second_approver_id = fields.Many2one(
        'res.users',
        string='Second Approver',
        domain=lambda self: [
            ('share', '=', False),
            ('group_ids', 'in', [self.env.ref('base.group_user').id]),
        ],
        tracking=True,
        help='User who will do the second approval',
    )
    third_approver_id = fields.Many2one(
        'res.users',
        string='Third Approver',
        domain=lambda self: [
            ('share', '=', False),
            ('group_ids', 'in', [self.env.ref('base.group_user').id]),
        ],
        tracking=True,
        help='User who will do the third approval',
    )
    state = fields.Selection(
        [
            ('draft', 'To Submit'),
            ('confirm', 'First Approval'),
            ('second_approve', 'Second Approval'),
            ('third_approve', 'Third Approval'),
            ('validate', 'Approved'),
            ('refuse', 'Refused'),
        ],
        string='Status',
        default='draft',
        tracking=True,
        copy=False,
    )
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        default=lambda self: self.env.company,
    )

    def _notify_approver(self, approver, message_body):
        self.ensure_one()
        if not approver or approver.share or not approver.partner_id:
            return
        try:
            bot_user = (
                self.env.ref("business_discuss_bots.user_bot_gate_ticket", raise_if_not_found=False)
                or self.env.ref("base.user_root")
            )
            chat = (
                self.env["discuss.channel"]
                .with_user(bot_user)
                .sudo()
                ._get_or_create_chat([approver.partner_id.id], pin=True)
            )
            chat.with_user(bot_user).sudo().message_post(
                body=Markup(message_body) if not isinstance(message_body, Markup) else message_body,
                message_type="comment",
                subtype_xmlid="mail.mt_comment",
            )
        except Exception:
            try:
                bot_partner = bot_user.partner_id if bot_user else False
                if not bot_partner:
                    raise ValueError("gate ticket bot partner not found")
                chat = (
                    self.env["discuss.channel"]
                    .sudo()
                    .with_user(approver)
                    ._get_or_create_chat([bot_partner.id], pin=True)
                )
                chat.with_user(bot_user).sudo().message_post(
                    body=Markup(message_body) if not isinstance(message_body, Markup) else message_body,
                    message_type="comment",
                    subtype_xmlid="mail.mt_comment",
                )
            except Exception:
                _logger.exception(
                    "hr_employee_gate_ticket: failed to send gate-ticket bot chat ticket_id=%s user_id=%s",
                    self.id,
                    approver.id,
                )

    def action_submit(self):
        for ticket in self:
            if ticket.state != 'draft':
                raise UserError(_('Only draft tickets can be submitted.'))
            ticket.state = 'confirm'
            if ticket.approver_id:
                ticket._notify_approver(
                    ticket.approver_id,
                    _(
                        'Nhân viên <b>%(employee)s</b> đang yêu cầu ra cổng.<br/>'
                        'Mã phiếu: <b>%(ticket)s</b>',
                        employee=ticket.employee_id.name,
                        ticket=ticket.name,
                    ),
                )

    def action_first_approve(self):
        for ticket in self:
            if ticket.state not in ['confirm', 'refuse']:
                raise UserError(_('Only tickets in first approval or refused state can be approved.'))
            if ticket.approver_id and ticket.approver_id != self.env.user and not self.env.user.has_group('base.group_system'):
                raise UserError(_('Only the assigned first approver or administrators can do first approval.'))
            ticket.state = 'second_approve'
            if ticket.second_approver_id:
                ticket._notify_approver(
                    ticket.second_approver_id,
                    _(
                        'Nhân viên <b>%(employee)s</b> đang yêu cầu ra cổng.<br/>'
                        'Mã phiếu: <b>%(ticket)s</b>',
                        employee=ticket.employee_id.name,
                        ticket=ticket.name,
                    ),
                )
            if ticket.employee_id.user_id:
                ticket._notify_approver(
                    ticket.employee_id.user_id,
                    _(
                        'Your gateway ticket has been approved by <b>%(approver)s</b>. '
                        'Waiting for second approval.',
                        approver=self.env.user.name,
                    ),
                )

    def action_second_approve(self):
        for ticket in self:
            if ticket.state != 'second_approve':
                raise UserError(_('Only tickets in second approval state can be approved.'))
            if ticket.second_approver_id and ticket.second_approver_id != self.env.user and not self.env.user.has_group('base.group_system'):
                raise UserError(_('Only the assigned second approver or administrators can do second approval.'))
            if ticket.third_approver_id:
                ticket.state = 'third_approve'
                ticket._notify_approver(
                    ticket.third_approver_id,
                    _(
                        'Nhân viên <b>%(employee)s</b> đang yêu cầu ra cổng.<br/>'
                        'Mã phiếu: <b>%(ticket)s</b>',
                        employee=ticket.employee_id.name,
                        ticket=ticket.name,
                    ),
                )
                if ticket.employee_id.user_id:
                    ticket._notify_approver(
                        ticket.employee_id.user_id,
                        _('Đơn ra cổng của bạn đã được chấp nhận.'),
                    )
            else:
                ticket.state = 'validate'
                if ticket.employee_id.user_id:
                    ticket._notify_approver(
                        ticket.employee_id.user_id,
                        _('Đơn ra cổng của bạn đã được chấp nhận.'),
                    )
                ticket.message_post(
                    body=_('Gateway ticket fully approved.'),
                    subtype_xmlid='mail.mt_comment',
                )

    def action_third_approve(self):
        for ticket in self:
            if ticket.state != 'third_approve':
                raise UserError(_('Only tickets in third approval state can be finally approved.'))
            if ticket.third_approver_id and ticket.third_approver_id != self.env.user and not self.env.user.has_group('base.group_system'):
                raise UserError(_('Only the assigned third approver or administrators can do third approval.'))
            ticket.state = 'validate'
            if ticket.employee_id.user_id:
                ticket._notify_approver(
                    ticket.employee_id.user_id,
                    _(
                        'Your gateway ticket has been <b>fully approved</b> by <b>%(approver)s</b>.',
                        approver=self.env.user.name,
                    ),
                )
            ticket.message_post(
                body=_('Gateway ticket fully approved.'),
                subtype_xmlid='mail.mt_comment',
            )

    def action_refuse(self):
        for ticket in self:
            if ticket.state not in ['confirm', 'second_approve', 'third_approve', 'validate']:
                raise UserError(_('Only confirmed, second approval, third approval, or approved tickets can be refused.'))
            ticket.state = 'refuse'
            if ticket.employee_id.user_id:
                ticket._notify_approver(
                    ticket.employee_id.user_id,
                    _(
                        'Your gateway ticket has been <b>refused</b> by <b>%(approver)s</b>.',
                        approver=self.env.user.name,
                    ),
                )
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
                    _(
                        'Gateway ticket for <b>%(employee)s</b> has been refused by <b>%(refuser)s</b>.',
                        employee=ticket.employee_id.name,
                        refuser=self.env.user.name,
                    ),
                )

    def action_draft(self):
        for ticket in self:
            ticket.state = 'draft'

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('hr.employee.gate.ticket') or _('New')
        tickets = super().create(vals_list)
        for ticket in tickets:
            _logger.info('Created gate ticket ID %s', ticket.id)
            ticket._generate_gate_ticket_pdf()
        return tickets

    def write(self, vals):
        result = super().write(vals)
        if any(
            field in vals
            for field in ['gate_ticket', 'gate_items', 'checkout_time', 'approver_id', 'second_approver_id', 'third_approver_id']
        ):
            for ticket in self:
                ticket._generate_gate_ticket_pdf()
        return result

    def _generate_gate_ticket_pdf(self):
        self.ensure_one()
        _logger.info('Attempting to generate PDF for gate ticket %s', self.id)
        try:
            pdf_content, _ = self.env['ir.actions.report']._render_qweb_pdf(
                'hr_employee_gate_ticket.action_report_gate_ticket',
                res_ids=[self.id],
            )
            attachment_vals = {
                'name': f'Gate_Ticket_{self.employee_id.name}_{self.id}.pdf',
                'type': 'binary',
                'datas': base64.b64encode(pdf_content),
                'res_model': self._name,
                'res_id': self.id,
                'mimetype': 'application/pdf',
            }
            old_attachments = self.env['ir.attachment'].search(
                [
                    ('res_model', '=', self._name),
                    ('res_id', '=', self.id),
                    ('name', 'like', 'Gate_Ticket_%'),
                ]
            )
            if old_attachments:
                old_attachments.unlink()
            self.env['ir.attachment'].create(attachment_vals)
        except Exception:
            _logger.exception('Error generating gate ticket PDF for %s', self.id)
