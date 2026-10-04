from odoo import Command, api, fields, models

PRICELIST_SYNC_FIELDS = {'name', 'shop_discount', 'bar_discount'}
PRODUCT_SYNC_FIELDS = {'name', 'price', 'validity_days', 'active'}


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
    price = fields.Float(string='Annual Fee', default=5000.0)
    description = fields.Text(string='Description')
    active = fields.Boolean(default=True)
    pricelist_id = fields.Many2one(
        'product.pricelist', string='Pricelist', readonly=True, copy=False, ondelete='set null',
        help="Generated automatically from the discounts. Active members get it, so POS and the "
             "website shop apply the tier discount.")
    product_id = fields.Many2one(
        'product.product', string='Membership Product', readonly=True, copy=False,
        ondelete='set null',
        help="Service product sold on a membership quotation. Generated from the annual fee.")

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
        plans._sync_product()
        return plans

    def write(self, vals):
        res = super().write(vals)
        if PRICELIST_SYNC_FIELDS & vals.keys():
            self._sync_pricelist()
        if PRODUCT_SYNC_FIELDS & vals.keys():
            self._sync_product()
        return res

    def _sync_product(self):
        """One service product per plan, priced at the annual fee, for membership quotations.
        It sits outside the Club Shop / Bar categories, so it never shows in the shop or POS."""
        for plan in self.sudo():
            vals = {
                'name': "%s Membership (%s days)" % (plan.name, plan.validity_days),
                'detailed_type': 'service',
                'list_price': plan.price,
                'sale_ok': True,
                'purchase_ok': False,
                'available_in_pos': False,
                'active': plan.active,
            }
            if plan.product_id:
                plan.product_id.write(vals)
            else:
                plan.product_id = self.env['product.product'].create(vals)
            self.env['club.finance'].apply_tax(plan.product_id)

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

    @api.model
    def get_frontend_plans(self):
        """Format membership plans for frontend OWL client actions and APIs."""
        plans = self.search([('active', '=', True)], order='sequence, id')
        result = []
        for p in plans:
            badge = "MOST POPULAR" if p.code == "gold" else ("UNDER 18" if p.code == "junior" else None)
            features = {
                'club_access': "Full club access (All facilities & lounges)" if p.code == "gold" else (
                    "Standard club access (Courts & locker room)" if p.code == "silver" else "Junior access (Academy & off-peak hours)"),
                'court_benefits': "Priority prime-time booking & 7 days advance (Rate: ₹0/hr)" if p.code == "gold" else (
                    f"Standard booking window (Rate: ₹{int(p.court_rate)}/hr)" if p.code == "silver" else f"Discounted court rates (Rate: ₹{int(p.court_rate)}/hr)"),
                'shop_benefits': f"{int(p.shop_discount)}% member discount on gear",
                'bar_benefits': f"{int(p.bar_discount)}% discount at cafeteria & sports bar" if p.bar_discount > 0 else "Standard member rates (No discount)",
                'membership_type': "Premium / Full Access VIP" if p.code == "gold" else (
                    "Standard Adult Membership" if p.code == "silver" else "Youth & Academy (< 18 yrs)"),
            }
            benefits = [
                features['club_access'],
                features['court_benefits'],
                features['shop_benefits'],
                features['bar_benefits'],
            ]
            result.append({
                'id': p.code,
                'db_id': p.id,
                'name': p.name.upper(),
                'code': p.code,
                'badge': badge,
                'description': p.description or (
                    "Premium access for members who want the complete club experience." if p.code == "gold" else (
                        "Standard membership for regular club users." if p.code == "silver" else "Discounted membership for members under 18.")),
                'price': p.price or (5000 if p.code == "gold" else (3000 if p.code == "silver" else 1500)),
                'currency': "₹",
                'billing_period': "year",
                'is_featured': p.code == "gold",
                'court_rate': p.court_rate,
                'shop_discount': p.shop_discount,
                'bar_discount': p.bar_discount,
                'benefits': benefits,
                'features': features,
                'active': p.active,
            })
        return result
