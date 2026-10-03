from odoo import fields, models


class MembershipPlan(models.Model):
    _name = 'club.membership.plan'
    _description = 'Club Membership Plan'
    _order = 'sequence, id'

    name = fields.Char(required=True)
    code = fields.Selection(
        [('gold', 'Gold'), ('silver', 'Silver'), ('junior', 'Junior')],
        required=True)
    sequence = fields.Integer(default=10)
    court_rate = fields.Float(string='Court Rate / Hour', required=True)
    shop_discount = fields.Float(string='Shop Discount %')
    bar_discount = fields.Float(string='Bar Discount %')
    validity_days = fields.Integer(default=365, required=True)
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ('code_unique', 'unique(code)', 'Only one plan per tier is allowed.'),
        ('rate_positive', 'CHECK(court_rate >= 0)', 'Court rate cannot be negative.'),
        ('shop_discount_range', 'CHECK(shop_discount >= 0 AND shop_discount <= 100)',
         'Shop discount must be between 0 and 100.'),
        ('bar_discount_range', 'CHECK(bar_discount >= 0 AND bar_discount <= 100)',
         'Bar discount must be between 0 and 100.'),
        ('validity_positive', 'CHECK(validity_days > 0)', 'Validity must be at least 1 day.'),
    ]
