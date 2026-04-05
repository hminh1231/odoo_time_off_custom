# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class PaymentRequest(models.Model):
    _name = 'payment.request'
    _description = 'Payment Request'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'id desc'

    name = fields.Char(
        string='Reference',
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: _('New'),
        tracking=True,
    )
    partner_id = fields.Many2one(
        'res.partner',
        string='Payee',
        tracking=True,
        help='Vendor or person to pay (optional).',
    )
    request_date = fields.Date(
        string='Request Date',
        required=True,
        default=fields.Date.context_today,
        tracking=True,
    )
    amount = fields.Monetary(
        string='Amount',
        required=True,
        tracking=True,
    )
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        required=True,
        default=lambda self: self.env.company.currency_id,
    )
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )
    user_id = fields.Many2one(
        'res.users',
        string='Requester',
        required=True,
        default=lambda self: self.env.user,
        tracking=True,
    )
    description = fields.Html(string='Description')
    state = fields.Selection(
        [
            ('draft', 'Draft'),
            ('submitted', 'Submitted'),
            ('approved', 'Approved'),
            ('paid', 'Paid'),
            ('rejected', 'Rejected'),
        ],
        string='Status',
        default='draft',
        required=True,
        tracking=True,
    )
    payment_date = fields.Date(string='Payment Date', readonly=True, copy=False)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('payment.request') or _('New')
        return super().create(vals_list)

    def write(self, vals):
        for rec in self:
            if rec.state not in ('draft', 'rejected') and any(
                k in vals for k in ('amount', 'partner_id', 'currency_id', 'request_date')
            ):
                raise UserError(_('You can only edit amount, payee, currency or date in Draft or Rejected state.'))
        return super().write(vals)

    def unlink(self):
        for rec in self:
            if rec.state != 'draft':
                raise UserError(_('Only draft requests can be deleted.'))
        return super().unlink()

    def action_submit(self):
        self.write({'state': 'submitted'})

    def action_approve(self):
        self.write({'state': 'approved'})

    def action_reject(self):
        self.write({'state': 'rejected', 'payment_date': False})

    def action_paid(self):
        self.write({
            'state': 'paid',
            'payment_date': fields.Date.context_today(self),
        })

    def action_reset_draft(self):
        self.write({'state': 'draft', 'payment_date': False})
