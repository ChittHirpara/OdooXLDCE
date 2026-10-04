from odoo import api, models
from odoo.addons.club_management.models.booking import club_today
from odoo.addons.club_management.models.club_pos_and_shop import MAX_ONLINE_QTY

LOW_STOCK = 5


def env_labels(model):
    """(area, label) pairs of the feedback areas, for display."""
    return model.env['club.feedback']._fields['area'].selection


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
    def cart_lines(self, cart):
        """The visitor's cart ({product id: quantity}) as display lines at today's list prices.

        Products that are no longer for sale or are sold out drop out; quantities are held to
        the stock and to the online maximum. The real price (member discount, stock check) is
        decided again by the server when the order is placed.
        """
        products = {p['id']: p for p in self.shop_products()}
        lines = []
        for product_id, qty in (cart or {}).items():
            product = products.get(int(product_id))
            if not product or product['stock'] <= 0:
                continue
            qty = max(1, min(int(qty), product['stock'], MAX_ONLINE_QTY))
            lines.append({'product': product, 'qty': qty, 'total': product['price'] * qty})
        return lines

    @api.model
    def social_proof(self):
        """Honest numbers for the home page: active members, sessions booked and the average rating."""
        env = self.sudo().env
        rating = env['club.feedback'].rating_summary()
        return {
            'members': env['res.partner'].search_count([('is_member', '=', True), ('member_state', '=', 'active')]),
            'sessions': env['club.booking'].search_count([('state', 'in', ('confirmed', 'done'))]),
            'courts': env['club.court'].search_count([('active', '=', True)]),
            'rating': rating['average'], 'ratings': rating['count'],
        }

    @api.model
    def testimonials(self, limit=6):
        """Feedback the club chose to show: 4-5 stars with a comment. Only first name and initial."""
        labels = dict(env_labels(self))
        rows = self.env['club.feedback'].sudo().search([
            ('public', '=', True), ('rating', '>=', 4), ('comment', '!=', False)], order='id desc', limit=limit)
        result = []
        for row in rows:
            parts = (row.name or 'Club member').split()
            author = parts[0] + (' %s.' % parts[-1][0] if len(parts) > 1 else '')
            result.append({'comment': row.comment, 'rating': row.rating, 'author': author,
                           'about': labels.get(row.area, '')})
        return result

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
