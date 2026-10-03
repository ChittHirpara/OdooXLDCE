from odoo import Command, api, fields, models

PRICELIST_SYNC_FIELDS = {'name', 'shop_discount', 'bar_discount'}


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
    pricelist_id = fields.Many2one(
        'product.pricelist', string='Pricelist', readonly=True, copy=False, ondelete='set null',
        help="Generated automatically from the discounts. Active members get it, so POS and the "
             "website shop apply the tier discount.")

    _sql_constraints = [
        ('code_unique', 'unique(code)', 'Only one plan per tier is allowed.'),
        ('rate_positive', 'CHECK(court_rate >= 0)', 'Court rate cannot be negative.'),
        ('shop_discount_range', 'CHECK(shop_discount >= 0 AND shop_discount <= 100)',
         'Shop discount must be between 0 and 100.'),
        ('bar_discount_range', 'CHECK(bar_discount >= 0 AND bar_discount <= 100)',
         'Bar discount must be between 0 and 100.'),
        ('validity_positive', 'CHECK(validity_days > 0)', 'Validity must be at least 1 day.'),
    ]

    @api.model_create_multi
    def create(self, vals_list):
        plans = super().create(vals_list)
        plans._sync_pricelist()
        return plans

    def write(self, vals):
        res = super().write(vals)
        if PRICELIST_SYNC_FIELDS & vals.keys():
            self._sync_pricelist()
        return res

    def _sync_pricelist(self):
        """Keep one pricelist per plan: shop % on the Club Shop category and
        bar % on the Bar & Cafeteria category. Runs as superuser because club
        managers do not necessarily have Sales rights."""
        shop_categ = self.env.ref('club_management.product_category_shop', raise_if_not_found=False)
        bar_categ = self.env.ref('club_management.product_category_bar', raise_if_not_found=False)
        for plan in self.sudo():
            name = "Club %s" % plan.name
            # High sequence: tier pricelists must never win Odoo's "first pricelist" fallback.
            # No company: the tier discounts apply wherever the member shops.
            vals = {'name': name, 'sequence': 100 + plan.sequence, 'company_id': False}
            if plan.pricelist_id:
                plan.pricelist_id.write(vals)
            else:
                plan.pricelist_id = self.env['product.pricelist'].create(vals)
            items = [
                Command.create({
                    'applied_on': '2_product_category',
                    'categ_id': categ.id,
                    'compute_price': 'percentage',
                    'percent_price': percent,
                })
                for categ, percent in ((shop_categ, plan.shop_discount), (bar_categ, plan.bar_discount))
                if categ and percent
            ]
            plan.pricelist_id.item_ids = [Command.clear()] + items
        self.env['pos.config'].sudo().search([])._enable_club_pricelists()
