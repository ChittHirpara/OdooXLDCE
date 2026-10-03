from odoo import api, models
from odoo.addons.club_management.models.booking import club_today

LOW_STOCK = 5


class ClubWebsiteData(models.AbstractModel):
    """What the public pages show. Visitors have no access rights, so everything is read as
    superuser, and only the fields a page needs are returned: no costs, no customers."""
    _name = 'club.website.data'
    _description = 'Public website data'

    @api.model
    def plans(self):
        return self.env['club.membership.plan'].sudo().search([])

    @api.model
    def courts(self):
        return self.env['club.court'].sudo().search([('active', '=', True)])

    @api.model
    def open_slots_today(self):
        """Per court: slots still bookable today, and the next free start."""
        result = []
        for data in self.courts().get_availability(club_today()):
            free = [s for s in data['slots'] if s['available']]
            result.append({
                'name': data['court'], 'sport': data['sport'], 'free': len(free),
                'next': free[0]['start'] if free else None,
                'price': data['list_price'], 'is_social': data['is_social'],
            })
        return result

    @api.model
    def shop_products(self, category=None, query=''):
        return self.env['product.product'].sudo().get_shop_catalog(category, query or '')

    @api.model
    def shop_categories(self):
        seen = {}
        for product in self.shop_products():
            seen.setdefault(product['category'], product['category_label'])
        return sorted(seen.items(), key=lambda item: item[1])

    @api.model
    def shop_product(self, product_id):
        """One shop product, or None when it is not publicly for sale."""
        shop = self.env.ref('club_management.product_category_shop')
        product = self.env['product.product'].sudo().search([
            ('id', '=', product_id), ('sale_ok', '=', True), ('categ_id', 'child_of', shop.id)])
        if not product:
            return None
        item = next((p for p in self.shop_products() if p['id'] == product.id), None)
        if item:
            item['tiers'] = [{
                'plan': plan.name, 'discount': plan.shop_discount,
                'price': plan.pricelist_id._get_product_price(product, 1.0),
            } for plan in self.plans() if plan.shop_discount]
        return item

    @api.model
    def stock_label(self, stock):
        if stock <= 0:
            return "Out of stock"
        if stock <= LOW_STOCK:
            return "Only %d left" % stock
        return "In stock"

    @api.model
    def max_shop_discount(self):
        return max(self.plans().mapped('shop_discount') or [0])
