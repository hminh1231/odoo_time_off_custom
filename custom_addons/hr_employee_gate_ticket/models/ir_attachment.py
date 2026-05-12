from odoo import _, models
from odoo.exceptions import UserError


class IrAttachment(models.Model):
    _inherit = 'ir.attachment'

    def unlink(self):
        # Allow internal PDF regeneration to bypass this guard
        if self.env.context.get('gate_ticket_regenerating'):
            return super().unlink()

        gate_ticket_attachments = self.filtered(
            lambda a: a.res_model == 'hr.employee.gate.ticket' and a.res_id
        )
        if gate_ticket_attachments:
            raise UserError(
                _('Attachments on gate tickets cannot be deleted.')
            )
        return super().unlink()
