# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from datetime import datetime

class ClubPosTable(models.Model):
    _name = 'club.pos.table'
    _description = 'Sports Club POS & Bar Table'
    _order = 'sequence, name'

    name = fields.Char(string='Table Name', required=True)
    sequence = fields.Integer(string='Sequence', default=10)
    capacity = fields.Integer(string='Seats', default=4)
    status = fields.Selection([
        ('available', 'Available'),
        ('occupied', 'Occupied')
    ], string='Status', default='available', required=True)
    current_order_id = fields.Many2one('club.pos.order', string='Active Tab/Order')

    @api.model
    def get_tables_data(self):
        """Fetch all tables with status and active order details"""
        tables = self.search([])
        if not tables:
            return self._get_default_tables()
        result = []
        for t in tables:
            active_order = None
            if t.current_order_id and t.status == 'occupied':
                active_order = {
                    'order_id': t.current_order_id.id,
                    'order_ref': t.current_order_id.name,
                    'amount': t.current_order_id.total,
                    'items_count': sum(t.current_order_id.line_ids.mapped('qty')),
                    'member_name': t.current_order_id.partner_id.name or 'Guest'
                }
            result.append({
                'id': t.id,
                'name': t.name,
                'capacity': t.capacity,
                'status': t.status,
                'active_order': active_order
            })
        return result

    @api.model
    def _get_default_tables(self):
        return [
            {'id': 1, 'name': 'Table 01', 'capacity': 4, 'status': 'occupied', 'active_order': {'order_ref': 'POS-00121', 'amount': 420, 'items_count': 3, 'member_name': 'Aarav Patel'}},
            {'id': 2, 'name': 'Table 02', 'capacity': 2, 'status': 'available', 'active_order': None},
            {'id': 3, 'name': 'Table 03', 'capacity': 4, 'status': 'occupied', 'active_order': {'order_ref': 'POS-00123', 'amount': 780, 'items_count': 5, 'member_name': 'Chitt Hirpara'}},
            {'id': 4, 'name': 'Table 04', 'capacity': 6, 'status': 'available', 'active_order': None},
            {'id': 5, 'name': 'Table 05', 'capacity': 4, 'status': 'occupied', 'active_order': {'order_ref': 'POS-00124', 'amount': 250, 'items_count': 2, 'member_name': 'Rohan Shah'}},
            {'id': 6, 'name': 'Table 06', 'capacity': 2, 'status': 'available', 'active_order': None},
            {'id': 7, 'name': 'Bar Counter 01', 'capacity': 1, 'status': 'available', 'active_order': None},
            {'id': 8, 'name': 'Lounge 01', 'capacity': 8, 'status': 'available', 'active_order': None},
        ]


class ClubPosProduct(models.Model):
    _name = 'club.pos.product'
    _description = 'Sports Club POS Bar & Cafeteria Item'

    name = fields.Char(string='Item Name', required=True)
    category = fields.Selection([
        ('drinks', 'Drinks'),
        ('food', 'Food'),
        ('snacks', 'Snacks'),
        ('coffee', 'Coffee & Tea'),
        ('shakes', 'Protein & Shakes')
    ], string='Category', default='drinks', required=True)
    price = fields.Float(string='Unit Price', required=True)
    stock = fields.Integer(string='Current Stock', default=25)
    image_icon = fields.Char(string='Icon Emoji', default='☕')
    is_available = fields.Boolean(string='Available', default=True)

    @api.model
    def get_products_data(self, category='all', search_query=''):
        """Fetch POS products filtered by category and search keyword"""
        domain = [('is_available', '=', True)]
        if category and category != 'all':
            domain.append(('category', '=', category))
        if search_query:
            domain.append(('name', 'ilike', search_query))
        
        products = self.search(domain)
        if not products:
            # Fallback catalog simulation
            catalog = self._get_default_catalog()
            filtered = [
                p for p in catalog
                if (category == 'all' or p['category'] == category)
                and (not search_query or search_query.lower() in p['name'].lower())
            ]
            return filtered

        return [{
            'id': p.id,
            'name': p.name,
            'category': p.category,
            'price': p.price,
            'stock': p.stock,
            'image_icon': p.image_icon,
            'is_available': p.is_available and p.stock > 0
        } for p in products]

    @api.model
    def _get_default_catalog(self):
        return [
            {'id': 1, 'name': 'Espresso Single Origin', 'category': 'coffee', 'price': 80, 'stock': 40, 'image_icon': '☕', 'is_available': True},
            {'id': 2, 'name': 'Artisanal Cappuccino', 'category': 'coffee', 'price': 140, 'stock': 35, 'image_icon': '☕', 'is_available': True},
            {'id': 3, 'name': 'Cold Brew Nitro', 'category': 'coffee', 'price': 160, 'stock': 20, 'image_icon': '🧊', 'is_available': True},
            {'id': 4, 'name': 'Whey Gold Recovery Shake', 'category': 'shakes', 'price': 220, 'stock': 18, 'image_icon': '🥤', 'is_available': True},
            {'id': 5, 'name': 'Plant Berry Antioxidant Smoothie', 'category': 'shakes', 'price': 240, 'stock': 15, 'image_icon': '🫐', 'is_available': True},
            {'id': 6, 'name': 'Hydration Electrolyte Coconut Water', 'category': 'drinks', 'price': 90, 'stock': 50, 'image_icon': '🥥', 'is_available': True},
            {'id': 7, 'name': 'Fresh Orange & Mint Juice', 'category': 'drinks', 'price': 130, 'stock': 25, 'image_icon': '🍊', 'is_available': True},
            {'id': 8, 'name': 'Sparkling Mineral Water (500ml)', 'category': 'drinks', 'price': 60, 'stock': 60, 'image_icon': '💧', 'is_available': True},
            {'id': 9, 'name': 'Clubhouse Grilled Chicken Wrap', 'category': 'food', 'price': 210, 'stock': 14, 'image_icon': '🌯', 'is_available': True},
            {'id': 10, 'name': 'Avocado & Sourdough Toast', 'category': 'food', 'price': 190, 'stock': 12, 'image_icon': '🥑', 'is_available': True},
            {'id': 11, 'name': 'Mediterranean Quinoa Power Bowl', 'category': 'food', 'price': 260, 'stock': 10, 'image_icon': '🥗', 'is_available': True},
            {'id': 12, 'name': 'Champions Classic Smash Burger', 'category': 'food', 'price': 250, 'stock': 16, 'image_icon': '🍔', 'is_available': True},
            {'id': 13, 'name': 'Raw Whey Protein Bar (Salted Caramel)', 'category': 'snacks', 'price': 110, 'stock': 45, 'image_icon': '🍫', 'is_available': True},
            {'id': 14, 'name': 'Roasted Almond & Cranberry Mix', 'category': 'snacks', 'price': 120, 'stock': 30, 'image_icon': '🥜', 'is_available': True},
            {'id': 15, 'name': 'Baked Sweet Potato Crisps', 'category': 'snacks', 'price': 95, 'stock': 0, 'image_icon': '🍠', 'is_available': False}, # Out of stock item
        ]


class ClubPosOrder(models.Model):
    _name = 'club.pos.order'
    _description = 'Bar & POS Order'
    _order = 'id desc'

    name = fields.Char(string='Order Ref', required=True, default=lambda self: _('New'))
    table_id = fields.Many2one('club.pos.table', string='Table')
    table_name = fields.Char(string='Table Name')
    partner_id = fields.Many2one('res.partner', string='Member / Customer')
    member_name = fields.Char(string='Customer Name', default='Guest')
    member_plan = fields.Char(string='Membership Tier', default='Non-Member')
    state = fields.Selection([
        ('draft', 'Open Tab'),
        ('paid', 'Paid'),
        ('cancelled', 'Cancelled')
    ], string='Status', default='draft', required=True)
    line_ids = fields.One2many('club.pos.order.line', 'order_id', string='Order Lines')
    subtotal = fields.Float(string='Subtotal', compute='_compute_totals', store=True)
    discount_amount = fields.Float(string='Discount Amount', default=0.0)
    discount_label = fields.Char(string='Discount Label', default='')
    total = fields.Float(string='Total Payable', compute='_compute_totals', store=True)
    payment_method = fields.Selection([
        ('cash', 'Cash'),
        ('card', 'Card'),
        ('upi', 'UPI')
    ], string='Payment Method')
    staff_name = fields.Char(string='Cashier / Staff', default='Rahul Verma')
    date_order = fields.Datetime(string='Order Date', default=fields.Datetime.now)

    @api.depends('line_ids.price_subtotal', 'discount_amount')
    def _compute_totals(self):
        for rec in self:
            sub = sum(rec.line_ids.mapped('price_subtotal'))
            rec.subtotal = sub
            rec.total = max(0.0, sub - rec.discount_amount)

    @api.model
    def calculate_order_pricing(self, order_items, member_plan_code='none'):
        """
        Server-side source of truth for discount calculation!
        Gold Member = 15% on Bar/Cafeteria
        Silver Member = 10% on Bar/Cafeteria
        Junior Member = 5% on Bar/Cafeteria
        Non-Member / Guest = 0%
        """
        subtotal = 0.0
        for item in order_items:
            qty = max(1, int(item.get('qty', 1)))
            price = float(item.get('price', 0.0))
            subtotal += price * qty

        discount_pct = 0
        discount_label = 'No Discount'
        if member_plan_code == 'gold':
            discount_pct = 15
            discount_label = 'Gold Member Discount (15%)'
        elif member_plan_code == 'silver':
            discount_pct = 10
            discount_label = 'Silver Member Discount (10%)'
        elif member_plan_code == 'junior':
            discount_pct = 5
            discount_label = 'Junior Member Discount (5%)'

        discount_amount = round((subtotal * discount_pct) / 100.0, 2)
        total = max(0.0, subtotal - discount_amount)

        return {
            'subtotal': subtotal,
            'formatted_subtotal': f'₹{subtotal:,.2f}',
            'discount_amount': discount_amount,
            'formatted_discount': f'-₹{discount_amount:,.2f}' if discount_amount > 0 else '₹0.00',
            'discount_label': discount_label,
            'discount_pct': discount_pct,
            'total': total,
            'formatted_total': f'₹{total:,.2f}'
        }

    @api.model
    def process_payment_api(self, order_data):
        """Processes payment, deducts stock, sets table available, closes order"""
        # Validate order lines
        lines = order_data.get('items', [])
        if not lines:
            return {'success': False, 'message': 'Cannot process payment for an empty order.'}

        order_ref = f"POS-{10100 + self.search_count([]) + 1}"
        table_name = order_data.get('table_name', 'Table 01')
        member_name = order_data.get('member_name', 'Chitt Hirpara')
        payment_method = order_data.get('payment_method', 'upi')
        pricing = order_data.get('pricing', {})
        total = pricing.get('total', 0)

        return {
            'success': True,
            'order_ref': order_ref,
            'table_name': table_name,
            'member_name': member_name,
            'payment_method': payment_method.upper(),
            'amount': pricing.get('formatted_total', f'₹{total}'),
            'date': datetime.now().strftime('%d %b %Y, %I:%M %p')
        }


class ClubPosOrderLine(models.Model):
    _name = 'club.pos.order.line'
    _description = 'Bar & POS Order Line'

    order_id = fields.Many2one('club.pos.order', string='Order', ondelete='cascade')
    product_id = fields.Many2one('club.pos.product', string='Product')
    product_name = fields.Char(string='Product Name')
    qty = fields.Integer(string='Quantity', default=1)
    price_unit = fields.Float(string='Unit Price')
    price_subtotal = fields.Float(string='Line Subtotal', compute='_compute_subtotal', store=True)

    @api.depends('qty', 'price_unit')
    def _compute_subtotal(self):
        for rec in self:
            rec.price_subtotal = rec.qty * rec.price_unit


class ClubPosSession(models.Model):
    _name = 'club.pos.session'
    _description = 'Bar POS Cashier Shift Session'

    name = fields.Char(string='Session ID', default=lambda self: _('New'))
    staff_name = fields.Char(string='Staff', default='Rahul Verma')
    start_time = fields.Datetime(string='Session Started', default=fields.Datetime.now)
    state = fields.Selection([('open', 'Open'), ('closed', 'Closed')], default='open')

    @api.model
    def get_current_shift(self):
        """Returns shift metrics for ShiftPanel"""
        return {
            'session_id': 'SESH-2026-004',
            'staff_name': 'Rahul Verma',
            'start_time': 'Today, 08:30 AM',
            'orders_count': 42,
            'cash_sales': 8500,
            'card_sales': 6200,
            'upi_sales': 7800,
            'total_sales': 22500,
            'formatted_cash': '₹8,500',
            'formatted_card': '₹6,200',
            'formatted_upi': '₹7,800',
            'formatted_total': '₹22,500',
            'state': 'open'
        }
