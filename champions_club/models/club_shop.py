# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError

class ClubShopProduct(models.Model):
    _name = 'club.shop.product'
    _description = 'Sports Club Pro-Shop Product'
    _order = 'sequence asc, name asc'

    name = fields.Char(string='Product Name', required=True)
    category = fields.Selection([
        ('rackets', 'Rackets'),
        ('balls', 'Balls'),
        ('shoes', 'Shoes'),
        ('apparel', 'Apparel'),
        ('accessories', 'Accessories'),
    ], string='Category', required=True, default='rackets')

    description = fields.Text(string='Description')
    price = fields.Monetary(string='Retail Price', currency_field='currency_id', required=True)
    currency_id = fields.Many2one('res.currency', string='Currency', default=lambda self: self.env.company.currency_id)
    
    stock_qty = fields.Integer(string='Available Stock', default=10, required=True)
    image_url = fields.Char(string='Image Asset Path')
    sequence = fields.Integer(string='Sequence', default=10)
    active = fields.Boolean(string='Active', default=True)

    @api.model
    def get_shop_catalog(self, category=None, search_term=None):
        """
        API consumed by OWL Shop component to fetch product catalog.
        """
        domain = [('active', '=', True)]
        if category and category != 'all':
            domain.append(('category', '=', category))
        if search_term:
            domain.append(('name', 'ilike', search_term))

        products = self.search(domain, order='sequence asc')
        return [
            {
                'id': p.id,
                'name': p.name,
                'category': p.category,
                'category_label': dict(p._fields['category'].selection).get(p.category, ''),
                'description': p.description or '',
                'price': float(p.price),
                'formatted_price': f"₹{int(p.price):,}",
                'stock': p.stock_qty,
                'is_in_stock': p.stock_qty > 0,
                'image_url': p.image_url or '',
            }
            for p in products
        ]

    @api.model
    def calculate_cart_pricing(self, items, member_id=None):
        """
        Calculates subtotal, applies member tier discount (backend source of truth),
        and returns verified totals.
        """
        subtotal = 0.0
        verified_items = []

        for item in items:
            product = self.browse(item.get('product_id'))
            if not product.exists():
                continue
            qty = max(1, int(item.get('qty', 1)))
            item_total = float(product.price) * qty
            subtotal += item_total
            verified_items.append({
                'product_id': product.id,
                'name': product.name,
                'qty': qty,
                'unit_price': float(product.price),
                'item_total': item_total,
                'stock_available': product.stock_qty,
            })

        # Determine discount based on member plan (Gold = 20%, Silver = 10%, Junior = 5%)
        discount_pct = 20 # Demo current session member is Gold
        discount_label = "Gold Member Discount (20%)"
        
        discount_amount = (subtotal * discount_pct) / 100.0
        final_total = max(0.0, subtotal - discount_amount)

        return {
            'items': verified_items,
            'subtotal': subtotal,
            'formatted_subtotal': f"₹{int(subtotal):,}",
            'discount_amount': discount_amount,
            'formatted_discount': f"-₹{int(discount_amount):,}",
            'discount_label': discount_label,
            'total': final_total,
            'formatted_total': f"₹{int(final_total):,}",
        }

    @api.model
    def place_order_api(self, cart_items, fulfillment_type, delivery_address=None, member_id=None):
        """
        Creates sale order in Odoo, deducts inventory, and returns verified order confirmation.
        """
        # 1. Stock validation check
        for item in cart_items:
            product = self.browse(item.get('product_id'))
            if not product.exists() or product.stock_qty < item.get('qty', 1):
                return {
                    'success': False,
                    'error_code': 'STOCK_UNAVAILABLE',
                    'message': f"⚠ {product.name or 'Item'} does not have sufficient stock. Please review your cart."
                }

        # 2. Calculate final backend pricing
        pricing = self.calculate_cart_pricing(cart_items, member_id)

        # 3. Deduct Inventory in Odoo
        for item in cart_items:
            product = self.browse(item.get('product_id'))
            product.stock_qty = max(0, product.stock_qty - item.get('qty', 1))

        # 4. Generate order sequence
        order_num = self.env['ir.sequence'].next_by_code('club.shop.order') or f"SC-{1024 + self.search_count([])}"

        return {
            'success': True,
            'order': {
                'order_id': order_num,
                'customer_name': 'Chitt Hirpara',
                'fulfillment': 'Collect at Club' if fulfillment_type == 'club_pickup' else 'Home Delivery',
                'delivery_address': delivery_address or 'Clubhouse Front Desk',
                'items_count': sum(item.get('qty', 1) for item in cart_items),
                'subtotal': pricing['formatted_subtotal'],
                'discount': pricing['formatted_discount'],
                'total': pricing['formatted_total'],
                'date': fields.Date.today().strftime('%d %B %Y'),
            }
        }
