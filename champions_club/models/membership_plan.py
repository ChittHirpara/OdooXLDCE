# -*- coding: utf-8 -*-
from odoo import models, fields, api

class ChampionsMembershipPlan(models.Model):
    _name = 'champions.membership.plan'
    _description = 'Champions Club Membership Plan'
    _order = 'sequence asc, price asc'

    name = fields.Char(string='Plan Name', required=True)
    code = fields.Selection([
        ('gold', 'Gold'),
        ('silver', 'Silver'),
        ('junior', 'Junior'),
    ], string='Plan Code', required=True, default='gold')

    sequence = fields.Integer(string='Sequence', default=10)
    active = fields.Boolean(string='Active', default=True)
    badge_text = fields.Char(string='Badge Tag', help="e.g. 'MOST POPULAR', 'UNDER 18'")
    description = fields.Text(string='Short Description')

    # Pricing & Currency
    currency_id = fields.Many2one('res.currency', string='Currency', default=lambda self: self.env.company.currency_id)
    price = fields.Monetary(string='Price', currency_field='currency_id', required=True, default=5000.0)
    billing_period = fields.Selection([
        ('year', 'Per Year'),
        ('month', 'Per Month'),
    ], string='Billing Period', default='year', required=True)

    # Specific Benefit Attributes
    club_access = fields.Char(string='Club Access', default='Standard club access')
    court_benefits = fields.Char(string='Court Benefits', default='Standard court benefits')
    shop_benefits = fields.Char(string='Shop Benefits', default='Standard shop benefits')
    bar_benefits = fields.Char(string='Bar Benefits', default='Standard bar rates')
    membership_type = fields.Char(string='Membership Type', default='Standard')

    # Active subscribers link
    subscriber_ids = fields.One2many('champions.membership.contract', 'plan_id', string='Subscribers')

    @api.model
    def get_frontend_plans(self):
        """
        API endpoint consumed by the OWL frontend component.
        Returns a clean serialized dictionary with all membership tier properties.
        """
        plans = self.search([('active', '=', True)], order='sequence asc')
        return [
            {
                'id': p.code,
                'odoo_id': p.id,
                'name': p.name,
                'code': p.code,
                'badge': p.badge_text or '',
                'description': p.description or '',
                'price': float(p.price),
                'currency': p.currency_id.symbol or '₹',
                'billing_period': p.billing_period,
                'is_featured': p.code == 'gold',
                'benefits': self._get_plan_benefits_list(p.code),
                'features': {
                    'club_access': p.club_access,
                    'court_benefits': p.court_benefits,
                    'shop_benefits': p.shop_benefits,
                    'bar_benefits': p.bar_benefits,
                    'membership_type': p.membership_type,
                },
                'active': p.active,
            }
            for p in plans
        ]

    def _get_plan_benefits_list(self, code):
        """Returns standard benefits rows based on tier"""
        if code == 'gold':
            return [
                "Full club access",
                "Premium court benefits",
                "Shop benefits",
                "Bar benefits"
            ]
        elif code == 'silver':
            return [
                "Standard club access",
                "Court benefits",
                "Shop benefits"
            ]
        elif code == 'junior':
            return [
                "Junior access",
                "Discounted court rates",
                "Junior benefits"
            ]
        return []
