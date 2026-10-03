# -*- coding: utf-8 -*-
import re
import uuid
from datetime import datetime, time, timedelta

import pytz

from odoo import Command, api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools import email_normalize

from .booking import CLUB_TZ, club_today, to_club_time

# Stock shown for products that are not stock-tracked (services, consumables).
UNTRACKED_STOCK = 99
MAX_ONLINE_QTY = 20     # most of one product in an online order


def money(amount, sign=''):
    return "%s₹%s" % (sign, format(amount, ',.2f'))


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
        result = []
        for table in self.search([], order='name asc'):
            active_order = None
            if table.status == 'occupied' and table.active_order_ref:
                active_order = {
                    'order_ref': table.active_order_ref,
                    'amount': int(table.active_order_amount),
                    'member_name': table.member_name or 'Club Member',
                }
            result.append({
                'id': table.id,
                'name': table.name,
                'capacity': table.capacity,
                'status': table.status,
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

    def _club_image_url(self):
        """The product picture for staff screens, with the write date so a new picture shows at once."""
        self.ensure_one()
        if not self.image_128:
            return ''
        return '/web/image/product.product/%d/image_512?unique=%s' % (
            self.id, fields.Datetime.to_string(self.write_date) if self.write_date else '')

    def _club_stock(self):
        """Real units on hand for stock-tracked products; a fixed 'available' number otherwise."""
        self.ensure_one()
        if self.detailed_type == 'product':
            return max(0, int(self.qty_available))
        return UNTRACKED_STOCK

    def _club_catalog(self, categ_xmlid, category, search_query):
        base = self.env.ref(categ_xmlid, raise_if_not_found=False)
        domain = [('sale_ok', '=', True)]
        if base:
            domain.append(('categ_id', 'child_of', base.id))
        if category and category != 'all':
            domain.append(('club_category', '=', category))
        if search_query:
            domain += ['|', ('name', 'ilike', search_query), ('description', 'ilike', search_query)]
        return self.search(domain, order='name asc')

    @api.model
    def get_shop_catalog(self, category=None, search_query="", partner_id=None):
        """Pro-Shop products with real stock and the member's price from their tier pricelist."""
        plan = self.env['club.order.service']._plan_for(partner_id)
        selection = dict(self._fields['club_category'].selection)
        result = []
        for p in self._club_catalog('club_management.product_category_shop', category, search_query):
            member_price = (plan.pricelist_id._get_product_price(p, 1.0)
                            if plan.pricelist_id else p.list_price)
            result.append({
                'id': p.id,
                'name': p.name,
                'category': p.club_category or 'accessories',
                'category_label': selection.get(p.club_category, 'Gear'),
                'price': p.list_price,
                'member_price': round(member_price, 2),
                'stock': p._club_stock(),
                'description': p.description_sale or p.name,
                'has_image': bool(p.image_128),
                'image_url': p._club_image_url(),
            })
        return result

    @api.model
    def get_bar_products(self, category=None, search_query="", partner_id=None):
        """Bar & Cafeteria products with real stock."""
        selection = dict(self._fields['club_category'].selection)
        result = []
        for p in self._club_catalog('club_management.product_category_bar', category, search_query):
            stock = p._club_stock()
            result.append({
                'id': p.id,
                'name': p.name,
                'category': p.club_category or 'coffee',
                'category_label': selection.get(p.club_category, 'Bar Item'),
                'price': p.list_price,
                'stock': stock,
                'is_available': stock > 0,
                'has_image': bool(p.image_128),
                'image_url': p._club_image_url(),
            })
        return result


class ClubOrderService(models.AbstractModel):
    _name = 'club.order.service'
    _description = 'Unified Club Order & Pricing Service'

    # ------------------------------------------------------------------
    # pricing: one rule for Shop and POS, driven by the member's tier pricelist
    # ------------------------------------------------------------------
    @api.model
    def _partner(self, partner_id):
        """The partner for a frontend id; 0, None or an unknown id means a walk-in guest."""
        pid = int(partner_id or 0)
        return self.env['res.partner'].browse(pid).exists() if pid > 0 else self.env['res.partner']

    @api.model
    def _plan_for(self, partner_id=None, plan_code=None):
        """Plan whose discounts apply. A partner id wins; a bare plan code is the fallback."""
        Plan = self.env['club.membership.plan']
        if partner_id is not None:
            partner = self._partner(partner_id)
            return partner._get_active_plan() if partner else Plan
        if plan_code in ('gold', 'silver', 'junior'):
            return Plan.search([('code', '=', plan_code)], limit=1)
        return Plan

    @api.model
    def _price_items(self, items, plan):
        Product = self.env['product.product']
        lines = []
        for item in items or []:
            product_id = item.get('product_id') or (item.get('product') or {}).get('id')
            qty = int(item.get('qty') or 1)
            product = Product.browse(int(product_id)).exists() if product_id else Product
            if not product or qty < 1:
                raise ValidationError("The order contains an unknown product or an invalid quantity.")
            unit = plan.pricelist_id._get_product_price(product, qty) if plan.pricelist_id else product.list_price
            lines.append({'product': product, 'qty': qty, 'list_price': product.list_price,
                          'unit_price': unit})
        return lines

    @api.model
    def _totals(self, lines, plan):
        subtotal = round(sum(l['list_price'] * l['qty'] for l in lines), 2)
        total = round(sum(l['unit_price'] * l['qty'] for l in lines), 2)
        discount = round(subtotal - total, 2)
        pct = round(discount * 100.0 / subtotal, 2) if subtotal else 0.0
        label = "%s Member Discount (%g%%)" % (plan.name, pct) if plan and discount else "No Discount"
        return {
            'subtotal': subtotal,
            'formatted_subtotal': money(subtotal),
            'discount_amount': discount,
            'formatted_discount': money(discount, '-') if discount else "₹0.00",
            'discount_label': label,
            'discount_pct': pct,
            'total': total,
            'formatted_total': money(total),
        }

    @api.model
    def calculate_order_pricing(self, items, plan_code="none", partner_id=None):
        """Authoritative price of a basket, using the member's tier pricelist."""
        plan = self._plan_for(partner_id, plan_code)
        return self._totals(self._price_items(items, plan), plan)

    # ------------------------------------------------------------------
    # orders
    # ------------------------------------------------------------------
    @api.model
    def _check_and_deduct_stock(self, lines):
        for line in lines:
            product = line['product']
            if product.detailed_type == 'product' and product.qty_available < line['qty']:
                raise ValidationError("Only %d x %s left in stock." % (
                    max(0, int(product.qty_available)), product.name))
        warehouse = self.env['stock.warehouse'].sudo().search([], limit=1)
        if not warehouse:
            return
        quants = self.env['stock.quant'].sudo()
        for line in lines:
            if line['product'].detailed_type == 'product':
                quants._update_available_quantity(
                    line['product'], warehouse.lot_stock_id, -line['qty'])

    @api.model
    def _create_order(self, channel, lines, plan, partner, **vals):
        self._check_and_deduct_stock(lines)
        return self.env['club.order'].create(dict(
            vals,
            channel=channel,
            partner_id=partner.id,
            plan_id=plan.id,
            line_ids=[Command.create({
                'product_id': l['product'].id, 'qty': l['qty'],
                'list_price': l['list_price'], 'unit_price': l['unit_price'],
            }) for l in lines],
        ))

    @api.model
    def process_pos_payment(self, vals):
        """Settle a bar tab: recompute prices on the server, deduct stock, free the table."""
        partner = self._partner(vals.get('member_id'))
        plan = partner._get_active_plan() if partner else self.env['club.membership.plan']
        lines = self._price_items(vals.get('items'), plan)
        if not lines:
            raise ValidationError("The order is empty.")
        method = (vals.get('payment_method') or '').lower()
        if method not in ('cash', 'card', 'upi'):
            raise ValidationError("Choose a payment method: cash, card or UPI.")
        table = self.env['club.pos.table'].search([('name', '=', vals.get('table_name'))], limit=1)
        customer = partner.name if partner else (vals.get('member_name') or 'Walk-in Guest')

        order = self._create_order('bar', lines, plan, partner, customer_name=customer,
                                   table_id=table.id, payment_method=method)
        if table:
            table.write({'status': 'available', 'active_order_ref': False,
                         'active_order_amount': 0.0, 'member_name': False})
        return {
            'success': True,
            'order_id': order.id,
            'order_ref': order.name,
            'table_name': table.name or vals.get('table_name'),
            'member_name': customer,
            'payment_method': method.upper(),
            'amount': money(order.total),
            'subtotal': money(order.subtotal),
            'discount': money(order.discount, '-') if order.discount else "₹0.00",
            'date': to_club_time(fields.Datetime.now()).strftime('%H:%M'),
        }

    @api.model
    def place_public_order(self, items, name, phone=None, email=None, fulfillment='collect',
                           address=None, member_ref=None, member_email=None):
        """A website visitor's pro-shop order: priced on the server, stock deducted, paid at the
        club (collect) or on delivery. A member who gives their member ID and the e-mail on file
        gets their tier price. Only products sold in the public shop can be ordered this way.
        Raises ValidationError with a message the visitor can act on."""
        svc = self.sudo()
        name = (name or '').strip()
        phone = re.sub(r'[^\d+]', '', phone or '')
        email = email_normalize((email or '').strip()) or False
        partner = self.env['res.partner']
        if member_ref:
            partner = self.env['res.partner']._club_verify_member(member_ref, member_email)
            name = partner.name
        else:
            if not name:
                raise ValidationError("Please tell us your name.")
            if not phone and not email:
                raise ValidationError("Please give a phone number or an e-mail address, so we can reach you.")
        if fulfillment not in ('collect', 'delivery'):
            raise ValidationError("Choose collect at the club or home delivery.")
        address = (address or '').strip()
        if fulfillment == 'delivery' and len(address) < 8:
            raise ValidationError("Please enter the full delivery address.")

        shop = self.env.ref('club_management.product_category_shop')
        clean = []
        for item in items or []:
            product = svc.env['product.product'].browse(int(item.get('product_id') or 0)).exists()
            qty = int(item.get('qty') or 0)
            if not (product and product.sale_ok and product.categ_id.parent_path.startswith(
                    shop.parent_path)):
                raise ValidationError("One of the products in your cart is not available online.")
            if not 1 <= qty <= MAX_ONLINE_QTY:
                raise ValidationError("Choose between 1 and %d of each product." % MAX_ONLINE_QTY)
            clean.append({'product_id': product.id, 'qty': qty})
        if not clean:
            raise ValidationError("Your cart is empty.")

        plan = partner._get_active_plan() if partner else self.env['club.membership.plan']
        lines = svc._price_items(clean, plan)
        with self.env.cr.savepoint():       # a refused order (for example no stock) leaves nothing behind
            order = svc._create_order(
                'shop', lines, plan, partner, customer_name=name[:100],
                customer_phone=phone[:30] or False, customer_email=email,
                fulfillment='Home Delivery' if fulfillment == 'delivery' else 'Collect at Club',
                delivery_address=address if fulfillment == 'delivery' else False,
                source='website', access_token=uuid.uuid4().hex)
        order._send_confirmation()
        return order

    @api.model
    def process_shop_checkout(self, vals):
        """Place a Pro-Shop order: recompute prices on the server and deduct stock."""
        partner = self._partner(vals.get('partner_id'))
        plan = partner._get_active_plan() if partner else self.env['club.membership.plan']
        lines = self._price_items(vals.get('items'), plan)
        if not lines:
            raise ValidationError("Your cart is empty.")
        customer = partner.name if partner else (vals.get('customer_name') or 'Guest')
        fulfillment = vals.get('fulfillment') or 'Collect at Club'
        address = vals.get('delivery_address') or 'Clubhouse Front Desk'

        order = self._create_order('shop', lines, plan, partner, customer_name=customer,
                                   fulfillment=fulfillment, delivery_address=address)
        return {
            'success': True,
            'order_id': order.name,
            'customer_name': customer,
            'fulfillment': fulfillment,
            'delivery_address': address,
            'date': to_club_time(fields.Datetime.now()).strftime('%d %B %Y'),
            'subtotal': money(order.subtotal),
            'discount': money(order.discount, '-') if order.discount else "₹0",
            'total': money(order.total),
            'items_count': sum(l['qty'] for l in lines),
        }

    @api.model
    def current_shift(self):
        """Today's bar sales, taken from real orders, for the shift / Z-report panel."""
        today = club_today()
        day_start = CLUB_TZ.localize(datetime.combine(today, time.min))
        to_utc = lambda dt: dt.astimezone(pytz.utc).replace(tzinfo=None)  # noqa: E731
        orders = self.env['club.order'].search([
            ('channel', '=', 'bar'),
            ('create_date', '>=', to_utc(day_start)),
            ('create_date', '<', to_utc(day_start + timedelta(days=1))),
        ], order='id')
        by_method = {m: sum(orders.filtered(lambda o: o.payment_method == m).mapped('total'))
                     for m in ('cash', 'card', 'upi')}
        total = sum(by_method.values())
        first = to_club_time(orders[0].create_date).strftime('Today, %I:%M %p') if orders else 'No sales yet'
        fmt = lambda amount: "₹%s" % format(amount, ',.0f')  # noqa: E731
        return {
            'session_id': 'SHIFT-%s' % today.strftime('%Y%m%d'),
            'staff_name': self.env.user.name,
            'start_time': first,
            'orders_count': len(orders),
            'cash_sales': by_method['cash'], 'card_sales': by_method['card'],
            'upi_sales': by_method['upi'], 'total_sales': total,
            'formatted_cash': fmt(by_method['cash']), 'formatted_card': fmt(by_method['card']),
            'formatted_upi': fmt(by_method['upi']), 'formatted_total': fmt(total),
        }
