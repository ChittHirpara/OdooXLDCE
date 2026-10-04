"""More demo data so the site and the screens look like a club in daily use: members who joined
over the last months, shop and bar orders, member feedback (some shown on the website),
support tickets and a few more products. About 50 records, safe to run again."""
import base64
from datetime import timedelta

from odoo import api, models
from odoo.tools import file_path

from .booking import club_today

PARAM_EXTRAS = 'club_management.demo_extras_loaded'

# name, plan, months since joining, date of birth (Junior only: years old)
NEW_MEMBERS = [
    ('Kavya Rao', 'gold', 7, None), ('Aditya Verma', 'gold', 5, None), ('Nisha Bose', 'silver', 6, None),
    ('Rahul Joshi', 'silver', 4, None), ('Tanvi Shah', 'silver', 3, None), ('Manish Gupta', 'silver', 2, None),
    ('Pooja Menon', 'gold', 1, None), ('Siddharth Jain', 'silver', 1, None),
    ('Aisha Khan', 'junior', 3, 12), ('Veer Chopra', 'junior', 0, 11),
]

# name, category, list price, cost, picture, stock (0 = not stock-tracked), club subcategory, shop or bar
NEW_PRODUCTS = [
    ('Padel Overgrip (Pack of 3)', 'shop', 'accessories', 399, 210, 'grip_tape', 30),
    ('Sports Water Bottle (750 ml)', 'shop', 'accessories', 650, 320, 'water_bottle', 40),
    ('Junior Tennis Racket (23 inch)', 'shop', 'rackets', 2900, 1700, 'tennis_racket', 9),
    ('Gym Towel Set (2 pcs)', 'shop', 'apparel', 549, 260, 'towel', 22),
    ('Masala Chai', 'bar', 'coffee', 60, 18, 'espresso', 0),
    ('Fresh Lime Mint Cooler', 'bar', 'drinks', 90, 28, 'lime_soda', 0),
]

# area, rating, comment, name, days ago, shown on the website
FEEDBACK = [
    ('court', 5, "Spotless courts and the online booking took under a minute. The evening floodlights are great.", 'Kavya Rao', 3, True),
    ('court', 5, "Booked two courts for the family on Saturday without any fuss. We will be back.", 'Aditya Verma', 6, True),
    ('court', 4, "Good surface and friendly staff. Friday social play is a lovely idea.", 'Nisha Bose', 9, True),
    ('bar', 5, "The cold coffee and the club sandwich after a match are exactly what I needed.", 'Rahul Joshi', 12, True),
    ('bar', 4, "Great shakes, quick service at the counter.", 'Tanvi Shah', 15, True),
    ('shop', 5, "Found the racket I wanted, and my member discount was applied automatically at checkout.", 'Manish Gupta', 18, True),
    ('shop', 4, "Good range of grips and balls. Delivery was quick.", 'Pooja Menon', 21, True),
    ('club', 5, "One membership for the courts, the shop and the bar. It just works. Best club in the area.", 'Siddharth Jain', 24, True),
    ('club', 5, "My daughter loves the Junior programme and the coaches are patient.", 'Aisha Khan', 28, True),
    ('club', 4, "Clean, well run and easy to book. Would love more weekend slots.", 'Veer Chopra', 33, True),
    ('court', 3, "Courts are fine but the changing room could be cleaner on busy evenings.", 'Imran Khan', 38, False),
    ('bar', 3, "Food was good but we waited a while at peak time.", 'Divya Menon', 41, False),
    ('shop', 2, "The racket I wanted was out of stock for over a week.", 'Suresh Rao', 4, False),
    ('court', 1, "Floodlights on Court 3 were flickering during our whole session.", 'Neha Gupta', 2, False),
]

# category, subject, description, name, email, state, days ago, resolution
TICKETS = [
    ('complaint', 'Floodlights flickering on Court 3', 'The lights kept flickering during our 8 pm session.',
     'Neha Gupta', 'neha.gupta@example.com', 'progress', 2, None),
    ('booking', 'Charged for a booking I cancelled', 'I cancelled BK well before the session but was still invoiced.',
     'Rahul Joshi', 'rahul.joshi@example.com', 'resolved', 9, 'The invoice was cancelled and a credit note issued.'),
    ('order', 'Wrong grip delivered', 'I ordered the padel overgrip but received a tennis one.',
     'Pooja Menon', 'pooja.menon@example.com', 'resolved', 14, 'We swapped it for the correct grip at the front desk.'),
    ('refund', 'Refund for the cancelled Friday social session', 'The Friday session was cancelled by the club. Please refund.',
     'Tanvi Shah', 'tanvi.shah@example.com', 'new', 1, None),
    ('other', 'Need a receipt for my membership fee', 'Please send a receipt for my annual membership.',
     'Manish Gupta', 'manish.gupta@example.com', 'closed', 20, 'Receipt emailed.'),
    ('complaint', 'Cafe wifi is not working', 'The wifi in the cafeteria has been down all week.',
     'Suresh Rao', 'suresh.rao@example.com', 'new', 3, None),
]

# channel, days ago, member (name, or None for a guest), guest name, items, payment
ORDERS = [
    ('shop', 2, 'Kavya Rao', None, [('Tennis Racket Pro', 1)], None),
    ('shop', 5, 'Aditya Verma', None, [('Padel Overgrip (Pack of 3)', 2), ('Sports Water Bottle (750 ml)', 1)], None),
    ('shop', 8, None, 'Imran Khan', [('Club Towel', 1)], None),
    ('shop', 12, 'Nisha Bose', None, [('Yonex Astrox 88D Pro Badminton Racket', 1)], None),
    ('shop', 19, 'Rahul Joshi', None, [('Gym Towel Set (2 pcs)', 1), ('Sports Water Bottle (750 ml)', 2)], None),
    ('shop', 27, None, 'Divya Menon', [('Junior Tennis Racket (23 inch)', 1)], None),
    ('bar', 1, 'Tanvi Shah', None, [('Cold Coffee', 2), ('Masala Chai', 1)], 'upi'),
    ('bar', 3, 'Manish Gupta', None, [('Champions Classic Smash Burger', 1), ('Fresh Lime Mint Cooler', 1)], 'card'),
    ('bar', 6, None, 'Suresh Rao', [('Whey Gold Recovery Shake', 1)], 'cash'),
    ('bar', 10, 'Pooja Menon', None, [('Clubhouse Grilled Chicken Wrap', 1), ('Bottled Water', 2)], 'upi'),
    ('bar', 16, 'Siddharth Jain', None, [('Artisanal Cappuccino', 2), ('Espresso Single Origin', 1)], 'card'),
    ('bar', 23, None, 'Pooja Bhatt', [('Fresh Lime Soda', 2), ('Masala Chai', 2)], 'cash'),
]


class ClubDemoExtras(models.AbstractModel):
    _inherit = 'club.demo'

    @api.model
    def load_extras(self):
        """Add the extra demo data once per database."""
        params = self.env['ir.config_parameter'].sudo()
        if params.get_param(PARAM_EXTRAS):
            return False
        today = club_today()
        self._extra_products()
        members = self._extra_members(today)
        self._extra_orders(today, members)
        self._extra_feedback(today)
        self._extra_tickets(today, members)
        params.set_param(PARAM_EXTRAS, '1')
        return True

    # ------------------------------------------------------------------
    def _back_date(self, record, days):
        """Pretend the record was created ``days`` ago (the reports and lists group on it)."""
        self.env.cr.execute(
            "UPDATE %s SET create_date = now() - make_interval(days => %%s) WHERE id = %%s" % record._table,
            (days, record.id))
        record.invalidate_recordset(['create_date'])

    def _extra_products(self):
        Product = self.env['product.product']
        warehouse = self.env['stock.warehouse'].search([], limit=1)
        for name, channel, subcategory, price, cost, picture, stock in NEW_PRODUCTS:
            if Product.search_count([('name', '=', name)]):
                continue
            product = Product.create({
                'name': name, 'list_price': float(price), 'standard_price': float(cost),
                'categ_id': self.env.ref('club_management.product_category_%s' % channel).id,
                'club_category': subcategory, 'sale_ok': True, 'available_in_pos': True,
                'detailed_type': 'product' if stock else 'consu'})
            with open(file_path('club_management/static/img/products/%s.svg' % picture), 'rb') as handle:
                product.image_1920 = base64.b64encode(handle.read())
            if stock and warehouse:
                self.env['stock.quant']._update_available_quantity(product, warehouse.lot_stock_id, stock)

    def _extra_members(self, today):
        Partner = self.env['res.partner']
        Plan = self.env['club.membership.plan']
        members = {}
        for name, code, months, age in NEW_MEMBERS:
            email = '%s@example.com' % name.lower().replace(' ', '.')
            partner = Partner.search([('email', '=', email)], limit=1)
            if not partner:
                plan = Plan.search([('code', '=', code)], limit=1)
                partner = Partner.create({
                    'name': name, 'email': email, 'plan_id': plan.id,
                    'phone': '+91 98%08d' % (sum(map(ord, name)) * 7919 % 10 ** 8),
                    'date_of_birth': (today - timedelta(days=age * 365 + 90)) if age else False})
                partner.action_activate_membership()
                joined = today - timedelta(days=months * 30 + 2)
                partner.write({'join_date': joined, 'expiry_date': joined + timedelta(days=plan.validity_days)})
            members[name] = partner
        return members

    def _extra_orders(self, today, members):
        svc = self.env['club.order.service']
        Product = self.env['product.product']
        for channel, days, member_name, guest, items, payment in ORDERS:
            products = [(Product.search([('name', '=', n)], limit=1), qty) for n, qty in items]
            if not all(product for product, _qty in products):
                continue
            partner = members.get(member_name) or self.env['res.partner']
            if self.env['club.order'].search_count([
                    ('customer_name', '=', partner.name or guest), ('channel', '=', channel),
                    ('line_ids.product_id', '=', products[0][0].id)]):
                continue        # already there: running the loader again adds nothing
            plan = partner._get_active_plan() if partner else self.env['club.membership.plan']
            try:
                with self.env.cr.savepoint():
                    lines = svc._price_items([{'product_id': p.id, 'qty': q} for p, q in products], plan)
                    values = {'customer_name': partner.name or guest, 'source': 'website' if channel == 'shop' else 'staff'}
                    if channel == 'shop':
                        values['fulfillment'] = 'Collect at Club'
                    else:
                        values['payment_method'] = payment
                    order = svc._create_order(channel, lines, plan, partner, **values)
                    self._back_date(order, days)
            except Exception:   # noqa: BLE001 - a missing product or no stock must not stop the demo load
                continue

    def _extra_feedback(self, today):
        Feedback = self.env['club.feedback']
        for area, rating, comment, name, days, public in FEEDBACK:
            if Feedback.search_count([('comment', '=', comment)]):
                continue
            feedback = Feedback.create_public(
                area, rating, comment=comment, name=name, email='%s@example.com' % name.lower().replace(' ', '.'))
            feedback.write({'public': public, 'reviewed': days > 7})
            self._back_date(feedback, days)

    def _extra_tickets(self, today, members):
        Ticket = self.env['club.ticket']
        for category, subject, description, name, email, state, days, resolution in TICKETS:
            if Ticket.search_count([('subject', '=', subject)]):
                continue
            partner = members.get(name)
            ticket = Ticket.create_public(name, category, subject, description=description, email=email,
                                          partner_id=partner.id if partner else None)
            if state in ('progress', 'resolved', 'closed'):
                ticket.action_start()
            if resolution:
                ticket.resolution = resolution
            if state == 'resolved':
                ticket.action_resolve()
            elif state == 'closed':
                ticket.action_resolve()
                ticket.action_close()
            self._back_date(ticket, days)
