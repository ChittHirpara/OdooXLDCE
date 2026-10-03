from odoo import fields, models


class AccountMove(models.Model):
    _inherit = 'account.move'

    club_source = fields.Selection(
        [('membership', 'Membership'), ('court', 'Court Booking'),
         ('shop', 'Pro-Shop'), ('bar', 'Bar & Cafeteria')],
        string='Club Revenue Source', copy=False, index=True,
        help="Which part of the club this invoice belongs to, for revenue reporting.")
