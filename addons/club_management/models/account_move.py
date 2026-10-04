from odoo import fields, models


class AccountMove(models.Model):
    _inherit = 'account.move'

    club_source = fields.Selection(
        [('membership', 'Membership'), ('court', 'Court Booking'),
         ('shop', 'Pro-Shop'), ('bar', 'Bar & Cafeteria')],
        string='Club Revenue Source', copy=False, index=True,
        help="Which part of the club this invoice belongs to, for revenue reporting.")

    def _invoice_paid_hook(self):
        """E-mail the customer when a membership or court invoice is paid. Shop and bar orders
        are paid at the till and already get their order confirmation, so they are not repeated."""
        res = super()._invoice_paid_hook()
        template = self.env.ref('club_management.mail_template_payment_received', raise_if_not_found=False)
        if template:
            for move in self.filtered(lambda m: m.move_type == 'out_invoice'
                                      and m.club_source in ('membership', 'court') and m.partner_id.email):
                template.sudo().send_mail(move.id)
        return res
