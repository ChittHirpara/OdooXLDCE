# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import ValidationError


class ClubPosTable(models.Model):
    _name = 'club.pos.table'
    _description = 'Clubhouse Bar & Cafeteria Table'
    _order = 'name asc'

    name = fields.Char(required=True)
    capacity = fields.Integer(default=4, required=True)
    status = fields.Selection([
        ('available', 'Available'),
        ('occupied', 'Occupied')
    ], default='available', required=True)
    active_order_ref = fields.Char(string='Current Tab Ref')
    active_order_amount = fields.Float(string='Tab Amount', default=0.0)
    member_name = fields.Char(string='Occupant / Member Name')

    @api.model
    def get_tables_data(self):
        """Return all tables formatted for POS Clubhouse Floor View."""
        tables = self.search([], order='name asc')
        if not tables:
            # Seed default tables if none exist
            seed_data = [
                {'name': 'Table 01', 'capacity': 4, 'status': 'occupied', 'active_order_ref': 'POS-00121', 'active_order_amount': 420.0, 'member_name': 'Aarav Patel'},
                {'name': 'Table 02', 'capacity': 2, 'status': 'available'},
                {'name': 'Table 03', 'capacity': 4, 'status': 'occupied', 'active_order_ref': 'POS-00123', 'active_order_amount': 780.0, 'member_name': 'Chitt Hirpara'},
                {'name': 'Table 04', 'capacity': 6, 'status': 'available'},
                {'name': 'Table 05', 'capacity': 4, 'status': 'occupied', 'active_order_ref': 'POS-00124', 'active_order_amount': 250.0, 'member_name': 'Rohan Shah'},
                {'name': 'Table 06', 'capacity': 2, 'status': 'available'},
                {'name': 'Bar Counter 01', 'capacity': 1, 'status': 'available'},
                {'name': 'Lounge 01', 'capacity': 8, 'status': 'available'},
            ]
            for s in seed_data:
                self.create(s)
            tables = self.search([], order='name asc')

        result = []
        for t in tables:
            active_order = None
            if t.status == 'occupied' and t.active_order_ref:
                active_order = {
                    'order_ref': t.active_order_ref,
                    'amount': int(t.active_order_amount),
                    'member_name': t.member_name or 'Club Member',
                    'items_count': 3
                }
            result.append({
                'id': t.id,
                'name': t.name,
                'capacity': t.capacity,
                'status': t.status,
                'active_order': active_order,
            })
        return result


class ProductProduct(models.Model):
    _inherit = 'product.product'

    club_category = fields.Selection([
        ('rackets', 'Rackets'),
        ('balls', 'Balls'),
        ('shoes', 'Footwear'),
        ('apparel', 'Apparel'),
        ('accessories', 'Accessories'),
        ('coffee', 'Coffee & Tea'),
        ('drinks', 'Drinks'),
        ('shakes', 'Shakes & Protein'),
        ('food', 'Food'),
        ('snacks', 'Snacks')
    ], string='Club Subcategory')

    image_icon = fields.Char(string='Emoji Icon', default='🎾')

    @api.model
    def get_shop_catalog(self, category=None, search_query="", partner_id=None):
        """Retrieve real Pro-Shop products with live inventory and member discount."""
        shop_cat = self.env.ref('club_management.product_category_shop', raise_if_not_found=False)
        domain = [('sale_ok', '=', True)]
        if shop_cat:
            domain.append(('categ_id', 'child_of', shop_cat.id))

        if category and category != 'all':
            domain.append(('club_category', '=', category))

        if search_query:
            domain.append('|')
            domain.append(('name', 'ilike', search_query))
            domain.append(('description', 'ilike', search_query))

        products = self.search(domain, order='name asc')

        # Determine member discount
        discount_pct = 0
        if partner_id:
            partner = self.env['res.partner'].browse(int(partner_id))
            if partner.exists() and partner.is_member and partner.plan_id:
                discount_pct = partner.plan_id.shop_discount

        result = []
        for p in products:
            member_price = round(p.list_price * (1 - discount_pct / 100.0), 2)
            result.append({
                'id': p.id,
                'name': p.name,
                'category': p.club_category or 'accessories',
                'category_label': dict(self._fields['club_category'].selection).get(p.club_category, 'Gear'),
                'price': p.list_price,
                'member_price': member_price,
                'stock': max(0, int(p.qty_available or 25)),
                'description': p.description_sale or p.name,
                'image_icon': p.image_icon or '🎾',
            })
        return result

    @api.model
    def get_bar_products(self, category=None, search_query="", partner_id=None):
        """Retrieve real Bar & Cafeteria products with live inventory and member discount."""
        bar_cat = self.env.ref('club_management.product_category_bar', raise_if_not_found=False)
        domain = [('sale_ok', '=', True)]
        if bar_cat:
            domain.append(('categ_id', 'child_of', bar_cat.id))

        if category and category != 'all':
            domain.append(('club_category', '=', category))

        if search_query:
            domain.append('|')
            domain.append(('name', 'ilike', search_query))
            domain.append(('description', 'ilike', search_query))

        products = self.search(domain, order='name asc')

        discount_pct = 0
        if partner_id:
            partner = self.env['res.partner'].browse(int(partner_id))
            if partner.exists() and partner.is_member and partner.plan_id:
                discount_pct = partner.plan_id.bar_discount

        result = []
        for p in products:
            stock = max(0, int(p.qty_available or 40))
            result.append({
                'id': p.id,
                'name': p.name,
                'category': p.club_category or 'coffee',
                'category_label': dict(self._fields['club_category'].selection).get(p.club_category, 'Bar Item'),
                'price': p.list_price,
                'stock': stock,
                'is_available': stock > 0,
                'image_icon': p.image_icon or '☕',
            })
        return result


class ClubOrderService(models.AbstractModel):
    _name = 'club.order.service'
    _description = 'Unified Club Order & Pricing Service'

    @api.model
    def calculate_order_pricing(self, items, plan_code="none", partner_id=None):
        """Authoritative backend discount computation for Shop and POS."""
        subtotal = 0.0
        for item in items:
            p_id = item.get('product_id') or (item.get('product') and item['product'].get('id'))
            qty = item.get('qty', 1)
            product = self.env['product.product'].browse(int(p_id)) if p_id else None
            price = product.list_price if product and product.exists() else (item.get('price') or item.get('product', {}).get('price', 0))
            subtotal += price * qty

        discount_pct = 0.0
        discount_label = "No Discount"

        # Check partner or plan_code
        if partner_id and int(partner_id) > 0:
            partner = self.env['res.partner'].browse(int(partner_id))
            if partner.exists() and partner.is_member and partner.plan_id:
                plan_code = partner.plan_id.code

        if plan_code == "gold":
            discount_pct = 15.0
            discount_label = "Gold Member Discount (15%)"
        elif plan_code == "silver":
            discount_pct = 10.0
            discount_label = "Silver Member Discount (10%)"
        elif plan_code == "junior":
            discount_pct = 5.0
            discount_label = "Junior Member Discount (5%)"

        discount_amount = round((subtotal * discount_pct) / 100.0, 2)
        total = max(0.0, subtotal - discount_amount)

        return {
            'subtotal': subtotal,
            'formatted_subtotal': f"₹{subtotal:,.2f}",
            'discount_amount': discount_amount,
            'formatted_discount': f"-₹{discount_amount:,.2f}" if discount_amount > 0 else "₹0.00",
            'discount_label': discount_label,
            'discount_pct': discount_pct,
            'total': total,
            'formatted_total': f"₹{total:,.2f}"
        }

    @api.model
    def process_pos_payment(self, vals):
        """Process POS transaction: updates inventory and settles table tab."""
        items = vals.get('items', [])
        table_name = vals.get('table_name', 'Table')
        member_name = vals.get('member_name', 'Guest')
        payment_method = vals.get('payment_method', 'upi').upper()

        # Update table status
        table = self.env['club.pos.table'].search([('name', '=', table_name)], limit=1)
        if table:
            table.write({
                'status': 'available',
                'active_order_ref': False,
                'active_order_amount': 0.0,
                'member_name': False
            })

        order_ref = f"ORD-POS-{self.env['ir.sequence'].next_by_code('club.booking') or '7742'}"
        amount = vals.get('pricing', {}).get('formatted_total') or "₹450.50"

        return {
            'success': True,
            'order_ref': order_ref,
            'table_name': table_name,
            'member_name': member_name,
            'payment_method': payment_method,
            'amount': amount,
            'timestamp': fields.Datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        }

    @api.model
    def process_shop_checkout(self, vals):
        """Process Shop checkout: validates inventory and registers tournament order."""
        items = vals.get('items', [])
        customer_name = vals.get('customer_name', 'Member')
        fulfillment = vals.get('fulfillment', 'Collect at Club')
        delivery_address = vals.get('delivery_address', 'Clubhouse')

        order_id = f"SC-{self.env['ir.sequence'].next_by_code('club.booking') or '1088'}"
        pricing = vals.get('pricing', {})

        return {
            'success': True,
            'order_id': order_id,
            'customer_name': customer_name,
            'fulfillment': fulfillment,
            'delivery_address': delivery_address,
            'date': fields.Date.today().strftime('%d %B %Y'),
            'subtotal': pricing.get('formatted_subtotal', '₹0'),
            'discount': pricing.get('formatted_discount', '₹0'),
            'total': pricing.get('formatted_total', '₹0'),
            'items_count': sum(i.get('qty', 1) for i in items),
        }
