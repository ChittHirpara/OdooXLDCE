import json
import re
from datetime import timedelta

from odoo import http
from odoo.addons.club_management.models.booking import WEBSITE_BOOKING_DAYS, club_today
from odoo.tests import tagged

from .test_website import WebsiteCase


class OnlineCase(WebsiteCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        cls.olcourt = env['club.court'].create({
            'name': 'Online Test Court', 'sport': 'tennis', 'list_price': 700.0, 'social_capacity': 4})
        cls.member = env['res.partner'].create({
            'name': 'Online Member', 'email': 'online.member@example.com',
            'plan_id': env.ref('club_management.plan_gold').id})
        cls.member.action_activate_membership()

    def day(self, offset=3):
        day = club_today() + timedelta(days=offset)
        while day.weekday() == 4:
            day += timedelta(days=1)
        return day.isoformat()

    def friday(self):
        day = club_today() + timedelta(days=1)
        while day.weekday() != 4:
            day += timedelta(days=1)
        return day.isoformat()

    def post(self, path, redirects=False, **data):
        if not getattr(self, '_visitor_session', False):
            self.authenticate(None, None)       # one anonymous session per test: the cart lives in it
            self._visitor_session = True
        if 'csrf_token' not in data:
            data['csrf_token'] = http.Request.csrf_token(self)
        return self.url_open(path, data=data, allow_redirects=redirects)

    def book(self, time='10:00', date=None, **data):
        data.setdefault('court_id', self.olcourt.id)
        data.setdefault('name', 'Web Booker')
        data.setdefault('phone', '+91 90000 33333')
        data.setdefault('email', 'web.booker@example.com')
        return self.post('/book/submit', date=date or self.day(), time=time, **data)

    def token_of(self, response):
        return re.search(r'/booking/([0-9a-f]{32})', response.headers['Location']).group(1)


@tagged('post_install', '-at_install', 'club_management', 'club_website')
class TestBookingPages(OnlineCase):

    def test_the_availability_grid_links_straight_to_booking(self):
        html = self.get('/courts')
        self.assertIn('click a free slot to book it', html.lower())
        self.assertIn('t', html)
        bundles = re.findall(r'(?:src)="(/web/assets/[^"]+assets_frontend[^"]*\.js)"', html)
        js = ''.join(self.get(path) for path in bundles)
        self.assertIn('/book?court_id=', js)
        self.assertNotIn('I would like to request', js)

    def test_the_date_picker_stops_at_the_booking_window(self):
        last = (club_today() + timedelta(days=WEBSITE_BOOKING_DAYS)).isoformat()
        self.assertIn('max="%s"' % last, self.get('/courts'))

    def test_the_booking_form_shows_the_court_time_and_guest_price(self):
        html = self.get('/book?court_id=%s&date=%s&time=10:00' % (self.olcourt.id, self.day()))
        self.assertIn('Online Test Court', html)
        self.assertIn('10:00 to 11:00', html)
        self.assertIn('₹700', html)
        for name in ('name', 'phone', 'email', 'website_url', 'csrf_token'):
            self.assertIn('name="%s"' % name, html)
        self.assertNotIn('name="member_ref"', html, "no member ID box: members just sign in")
        self.assertIn('Sign in', html)
        self.assertIn('Confirm booking', html)
        self.assertNotIn('name="players"', html)                 # only on Fridays
        # the hidden fields the form posts back must carry the real values (they once rendered
        # as Odoo's own `time` module, because the template variable shadowed a built-in name)
        self.assertRegex(html, r'name="date"[^>]*value="%s"' % self.day())
        self.assertRegex(html, r'name="time"[^>]*value="10:00"')
        self.assertRegex(html, r'name="court_id"[^>]*value="%s"' % self.olcourt.id)

    def test_a_form_error_keeps_the_booking_form_and_its_hidden_values(self):
        response = self.book(name='', phone='', email='')
        self.assertEqual(response.status_code, 400)
        self.assertIn('Confirm booking', response.text)           # the form is still there
        self.assertRegex(response.text, r'name="time"[^>]*value="10:00"')

    def test_friday_asks_how_many_players(self):
        html = self.get('/book?court_id=%s&date=%s&time=18:00' % (self.olcourt.id, self.friday()))
        self.assertIn('name="players"', html)
        self.assertIn('social play', html)

    def test_an_unknown_court_goes_back_to_the_courts_page(self):
        response = self.url_open('/book?court_id=999999&date=%s&time=10:00' % self.day(), allow_redirects=False)
        self.assertEqual(response.status_code, 303 if response.status_code == 303 else 302)
        self.assertTrue(response.headers['Location'].endswith('/courts'))

    def test_a_past_or_too_distant_slot_shows_a_message_and_no_form(self):
        yesterday = (club_today() - timedelta(days=1)).isoformat()
        html = self.get('/book?court_id=%s&date=%s&time=10:00' % (self.olcourt.id, yesterday))
        self.assertIn('already passed', html)
        self.assertNotIn('Confirm booking', html)
        far = (club_today() + timedelta(days=WEBSITE_BOOKING_DAYS + 3)).isoformat()
        self.assertIn('days ahead', self.get('/book?court_id=%s&date=%s&time=10:00' % (self.olcourt.id, far)))

    def test_junk_parameters_do_not_break_the_page(self):
        for query in ('court_id=abc&date=x&time=y', 'date=2026-10-05', '', 'court_id=%s&date=nope&time=10:00' % self.olcourt.id):
            self.assertIn(self.url_open('/book?' + query).status_code, (200,))

    def test_booking_as_a_guest_confirms_instantly(self):
        response = self.book()
        self.assertEqual(response.status_code, 303)
        token = self.token_of(response)
        booking = self.env['club.booking'].search([('access_token', '=', token)])
        self.assertEqual((booking.state, booking.price, booking.booking_source), ('confirmed', 700.0, 'website'))
        page = self.get('/booking/%s?new=1' % token)
        for expected in ('You are booked!', booking.name, 'Online Test Court', '10:00 to 11:00', '₹700',
                         'guest rate', 'Web Booker', 'Cancel this booking'):
            self.assertIn(expected, page)

    def test_the_booking_shows_up_for_staff_and_in_the_grid(self):
        self.book('11:00')
        data = json.loads(self.get('/club/availability?date=%s&court_id=%s' % (self.day(), self.olcourt.id)))
        slots = {s['start']: s['available'] for s in data['courts'][0]['slots']}
        self.assertFalse(slots['11:00'])
        self.assertTrue(slots['12:00'])

    def test_a_confirmation_email_and_a_follow_up_lead(self):
        self.book(email='confirm.me@example.com')
        mail = self.env['mail.mail'].search([('email_to', '=', 'confirm.me@example.com'),
                                             ('subject', 'like', 'Court booked')])
        self.assertEqual(len(mail), 1)
        self.assertEqual(self.env['crm.lead'].search_count([('email_from', '=', 'confirm.me@example.com')]), 1)

    def test_a_missing_name_shows_the_message_and_keeps_what_was_typed(self):
        before = self.env['club.booking'].search_count([])
        response = self.book(name='', phone='+91 90000 44444', email='')
        self.assertEqual(response.status_code, 400)
        self.assertIn('tell us your name', response.text)
        self.assertIn('91 90000 44444', response.text)
        self.assertEqual(self.env['club.booking'].search_count([]), before)

    def test_a_taken_slot_is_refused_with_the_form_still_filled_in(self):
        self.book('10:00')
        response = self.book('10:00', name='Second Booker', phone='+91 91111 22222', email='second@example.com')
        self.assertEqual(response.status_code, 400)
        self.assertIn('already booked', response.text)
        self.assertIn('Second Booker', response.text)
        self.assertEqual(self.env['club.booking'].search_count([('walkin_name', '=', 'Second Booker')]), 0)

    def test_the_honeypot_books_nothing(self):
        before = self.env['club.booking'].search_count([])
        response = self.book(website_url='http://spam.example')
        self.assertEqual(response.status_code, 303)
        self.assertTrue(response.headers['Location'].endswith('/courts'))
        self.assertEqual(self.env['club.booking'].search_count([]), before)

    def test_a_post_without_a_csrf_token_is_refused(self):
        before = self.env['club.booking'].search_count([])
        response = self.url_open('/book/submit', data={'court_id': self.olcourt.id, 'date': self.day(),
                                                       'time': '10:00', 'name': 'No Token', 'phone': '9000011111'})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.env['club.booking'].search_count([]), before)

    def test_a_guest_cannot_book_more_than_two_a_day(self):
        self.book('08:00')
        self.book('10:00')
        response = self.book('12:00')
        self.assertEqual(response.status_code, 400)
        self.assertIn('maximum per day', response.text)

    def test_friday_players_share_the_court(self):
        friday = self.friday()
        ok = self.book('18:00', date=friday, players='3')
        self.assertEqual(ok.status_code, 303)
        full = self.book('18:00', date=friday, players='2', name='Late', phone='+91 92222 00000', email='late@example.com')
        self.assertEqual(full.status_code, 400)
        self.assertIn('full', full.text)

    # --- members -----------------------------------------------------------
    def test_a_member_books_at_their_tier_price(self):
        response = self.book(name='', member_ref=self.member.member_id, member_email='ONLINE.member@example.com',
                             phone='', email='')
        self.assertEqual(response.status_code, 303)
        page = self.get(response.headers['Location'])
        self.assertIn('Online Member', page)
        self.assertIn('Gold member rate', page)
        self.assertIn('₹0', page)
        booking = self.env['club.booking'].search([('access_token', '=', self.token_of(response))])
        self.assertEqual((booking.partner_id, booking.tier), (self.member, 'gold'))
        self.assertEqual(self.env['crm.lead'].search_count([('email_from', '=', 'online.member@example.com')]), 0)

    def test_a_wrong_member_check_is_refused(self):
        response = self.book(member_ref=self.member.member_id, member_email='someone.else@example.com')
        self.assertEqual(response.status_code, 400)
        self.assertIn('could not verify', response.text)

    # --- the private booking page: view and cancel -------------------------
    def test_an_unknown_booking_link_is_404(self):
        self.get('/booking/' + 'f' * 32, status=404)
        self.get('/booking/short', status=404)

    def test_the_page_shows_only_that_booking(self):
        mine = self.token_of(self.book('10:00', name='Visible Person'))
        self.book('12:00', name='Other Person', phone='+91 93333 11111', email='other.person@example.com')
        page = self.get('/booking/' + mine)
        self.assertIn('Visible Person', page)
        self.assertNotIn('Other Person', page)

    def test_cancelling_frees_the_slot_and_says_so(self):
        token = self.token_of(self.book('10:00'))
        response = self.post('/booking/%s/cancel' % token)
        self.assertEqual(response.status_code, 303)
        page = self.get('/booking/' + token)
        self.assertIn('Booking cancelled', page)
        self.assertIn('has been cancelled', page)
        self.assertNotIn('Cancel this booking', page)
        data = json.loads(self.get('/club/availability?date=%s&court_id=%s' % (self.day(), self.olcourt.id)))
        self.assertTrue({s['start']: s['available'] for s in data['courts'][0]['slots']}['10:00'])
        self.assertEqual(self.book('10:00', name='Next', phone='+91 94444 55555', email='next@example.com').status_code, 303)

    def test_cancelling_twice_is_refused_politely(self):
        token = self.token_of(self.book('10:00'))
        self.post('/booking/%s/cancel' % token)
        self.post('/booking/%s/cancel' % token)
        self.assertIn('no longer', self.get('/booking/' + token))

    def test_cancelling_needs_a_csrf_token(self):
        token = self.token_of(self.book('10:00'))
        response = self.url_open('/booking/%s/cancel' % token, data={'x': '1'})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.env['club.booking'].search([('access_token', '=', token)]).state, 'confirmed')

    def test_a_started_session_has_no_cancel_button(self):
        booking = self.env['club.booking'].create({
            'court_id': self.olcourt.id, 'walkin_name': 'Past', 'state': 'confirmed', 'booking_source': 'website',
            'access_token': 'a' * 32,
            'start_datetime': self.env['club.booking']._club_start_utc((club_today() - timedelta(days=1)).isoformat(), '10:00')})
        self.assertNotIn('Cancel this booking', self.get('/booking/' + booking.access_token))

    def test_names_are_escaped_on_the_booking_page(self):
        token = self.token_of(self.book(name='<b>Bold</b> Booker'))
        self.assertNotIn('<b>Bold</b>', self.get('/booking/' + token))

    def test_the_public_still_cannot_read_bookings_through_the_web_client(self):
        self.book()
        reply = self.url_open('/web/dataset/call_kw/club.booking/search_read', data=json.dumps({
            'jsonrpc': '2.0', 'method': 'call', 'params': {
                'model': 'club.booking', 'method': 'search_read', 'args': [[]], 'kwargs': {'fields': ['name']}}}),
            headers={'Content-Type': 'application/json'}).json()
        self.assertNotIn('result', reply)


@tagged('post_install', '-at_install', 'club_management', 'club_website')
class TestShopCart(OnlineCase):

    def add(self, product, qty=1, **kw):
        return self.post('/club-shop/cart/add', product_id=product.id, qty=qty, **kw)

    def cart_html(self):
        return self.get('/club-shop/cart')

    def test_adding_to_the_cart_redirects_to_it_and_lists_the_product(self):
        response = self.add(self.grip, 2)
        self.assertEqual(response.status_code, 303)
        self.assertTrue(response.headers['Location'].endswith('/club-shop/cart'))
        html = self.cart_html()
        for expected in ('Webtest Grip', '₹300', '₹600', 'Checkout', 'Update cart'):
            self.assertIn(expected, html)

    def test_adding_twice_adds_up_and_is_held_to_the_stock(self):
        self.add(self.grip, 2)
        self.add(self.grip, 2)
        self.assertIn('value="3"', self.cart_html())                   # stock is 3
        self.assertIn('Only 3', self.get('/club-shop/cart'))

    def test_a_sold_out_product_cannot_be_added(self):
        self.add(self.sold_out, 1)
        self.assertIn('out of stock', self.get('/club-shop/%s' % self.sold_out.id).lower())
        self.assertNotIn('Webtest Sold Out Racket', self.cart_html())

    def test_products_not_sold_in_the_shop_cannot_be_added(self):
        for product in (self.latte, self.hidden, self.gold.product_id):
            self.add(product, 1)
        self.assertNotIn('Webtest Latte', self.cart_html())
        self.assertIn('Your cart is empty', self.cart_html())

    def test_bad_quantities_and_ids_are_handled(self):
        self.post('/club-shop/cart/add', product_id='abc', qty='1')
        self.post('/club-shop/cart/add', product_id=self.balls.id, qty='lots')
        self.post('/club-shop/cart/add', product_id=self.balls.id, qty='-4')
        self.assertIn('Webtest Balls', self.cart_html())

    def test_updating_and_removing_lines(self):
        self.add(self.balls, 2)
        self.add(self.grip, 1)
        self.post('/club-shop/cart/update', **{'qty_%s' % self.balls.id: '5', 'qty_%s' % self.grip.id: '0'})
        html = self.cart_html()
        self.assertIn('Webtest Balls', html)
        self.assertNotIn('Webtest Grip', html)
        self.assertIn('₹2,000', html)

    def test_the_shop_shows_the_cart_count(self):
        self.add(self.balls, 3)
        self.assertIn('Cart (3)', self.get('/club-shop'))

    def test_every_visitor_has_their_own_cart(self):
        self.add(self.balls, 1)
        self.opener.cookies.clear()
        self.assertIn('Your cart is empty', self.cart_html())

    def test_cart_posts_need_a_csrf_token(self):
        response = self.url_open('/club-shop/cart/add', data={'product_id': self.balls.id, 'qty': 1})
        self.assertEqual(response.status_code, 400)

    def test_checkout_with_an_empty_cart_goes_back_to_the_cart(self):
        response = self.url_open('/club-shop/checkout', allow_redirects=False)
        self.assertIn(response.status_code, (302, 303))
        self.assertTrue(response.headers['Location'].endswith('/club-shop/cart'))

    def test_the_checkout_page_summarises_the_cart(self):
        self.add(self.balls, 2)
        html = self.get('/club-shop/checkout')
        for expected in ('Webtest Balls', '₹800', 'Place order', 'Collect at the club', 'Home delivery',
                         'Sign in', 'name="website_url"', 'pay at the club'):
            self.assertIn(expected, html)

    def checkout(self, **data):
        data.setdefault('name', 'Shop Buyer')
        data.setdefault('phone', '+91 90000 66666')
        data.setdefault('email', 'shop.buyer@example.com')
        data.setdefault('fulfillment', 'collect')
        return self.post('/club-shop/checkout/submit', **data)

    def test_placing_an_order_as_a_guest(self):
        self.add(self.balls, 2)
        stock_before = int(self.balls.qty_available)
        response = self.checkout()
        self.assertEqual(response.status_code, 303)
        token = re.search(r'/club-shop/order/([0-9a-f]{32})', response.headers['Location']).group(1)
        order = self.env['club.order'].search([('access_token', '=', token)])
        self.assertEqual((order.channel, order.source, order.total, order.fulfillment),
                         ('shop', 'website', 800.0, 'Collect at Club'))
        self.balls.invalidate_recordset(['qty_available'])
        self.assertEqual(int(self.balls.qty_available), stock_before - 2)
        page = self.get('/club-shop/order/' + token)
        for expected in ('Thank you, Shop Buyer', order.name, 'Webtest Balls', '₹800', 'Collect at Club', 'Pay at the club'):
            self.assertIn(expected, page)
        self.assertIn('Your cart is empty', self.cart_html())              # the cart was cleared

    def test_the_confirmation_email_is_queued(self):
        self.add(self.balls, 1)
        self.checkout(email='order.confirm@example.com')
        self.assertEqual(self.env['mail.mail'].search_count([
            ('email_to', '=', 'order.confirm@example.com'), ('subject', 'like', 'Your Champions Club order')]), 1)

    def test_a_member_gets_the_tier_discount_at_checkout(self):
        self.add(self.grip, 1)
        response = self.checkout(member_ref=self.member.member_id, member_email=self.member.email)
        token = re.search(r'/club-shop/order/([0-9a-f]{32})', response.headers['Location']).group(1)
        page = self.get('/club-shop/order/' + token)
        self.assertIn('Member discount (Gold)', page)
        self.assertIn('-₹60', page)
        self.assertIn('₹240', page)

    def test_a_wrong_member_check_keeps_the_cart_and_shows_one_message(self):
        self.add(self.balls, 1)
        response = self.checkout(member_ref=self.member.member_id, member_email='nobody@example.com')
        self.assertEqual(response.status_code, 400)
        self.assertIn('could not verify', response.text)
        self.assertIn('Webtest Balls', self.cart_html())

    def test_delivery_needs_an_address(self):
        self.add(self.balls, 1)
        refused = self.checkout(fulfillment='delivery', address='12')
        self.assertEqual(refused.status_code, 400)
        self.assertIn('delivery address', refused.text)
        ok = self.checkout(fulfillment='delivery', address='12 MG Road, Pune 411001')
        token = re.search(r'/club-shop/order/([0-9a-f]{32})', ok.headers['Location']).group(1)
        page = self.get('/club-shop/order/' + token)
        self.assertIn('Home Delivery', page)
        self.assertIn('12 MG Road, Pune 411001', page)

    def test_a_missing_name_or_contact_is_refused_and_values_are_kept(self):
        self.add(self.balls, 1)
        response = self.checkout(name='', phone='', email='')
        self.assertEqual(response.status_code, 400)
        self.assertIn('tell us your name', response.text)

    def test_stock_that_ran_out_after_adding_is_refused_cleanly(self):
        self.add(self.grip, 3)
        self.env['stock.quant']._update_available_quantity(
            self.grip, self.env['stock.warehouse'].search([], limit=1).lot_stock_id, -2)      # someone else bought them
        before = self.env['club.order'].search_count([])
        response = self.checkout()
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.env['club.order'].search_count([]), before)

    def test_prices_sent_by_the_browser_are_ignored(self):
        self.add(self.grip, 1)
        response = self.checkout(price='1', total='1', unit_price='1')
        token = re.search(r'/club-shop/order/([0-9a-f]{32})', response.headers['Location']).group(1)
        self.assertEqual(self.env['club.order'].search([('access_token', '=', token)]).total, 300.0)

    def test_the_honeypot_places_no_order(self):
        self.add(self.balls, 1)
        before = self.env['club.order'].search_count([])
        response = self.checkout(website_url='http://spam.example')
        self.assertEqual(response.status_code, 303)
        self.assertEqual(self.env['club.order'].search_count([]), before)

    def test_checkout_needs_a_csrf_token(self):
        self.add(self.balls, 1)
        response = self.url_open('/club-shop/checkout/submit', data={'name': 'x', 'phone': '9000011111'})
        self.assertEqual(response.status_code, 400)

    def test_an_order_link_only_shows_that_order(self):
        self.add(self.balls, 1)
        first = re.search(r'([0-9a-f]{32})', self.checkout(name='First Buyer').headers['Location']).group(1)
        self.add(self.balls, 1)
        self.checkout(name='Second Buyer', phone='+91 95555 00000', email='second.buyer@example.com')
        page = self.get('/club-shop/order/' + first)
        self.assertIn('First Buyer', page)
        self.assertNotIn('Second Buyer', page)
        self.get('/club-shop/order/' + 'e' * 32, status=404)

    def test_the_order_shows_up_for_staff(self):
        self.add(self.balls, 1)
        self.checkout(name='Staff Visible')
        order = self.env['club.order'].search([('customer_name', '=', 'Staff Visible')])
        self.assertEqual((order.source, order.customer_email), ('website', 'shop.buyer@example.com'))

    def test_the_public_cannot_read_orders_through_the_web_client(self):
        reply = self.url_open('/web/dataset/call_kw/club.order/search_read', data=json.dumps({
            'jsonrpc': '2.0', 'method': 'call', 'params': {
                'model': 'club.order', 'method': 'search_read', 'args': [[]], 'kwargs': {'fields': ['name']}}}),
            headers={'Content-Type': 'application/json'}).json()
        self.assertNotIn('result', reply)


@tagged('post_install', '-at_install', 'club_management', 'club_website')
class TestInstantJourney(OnlineCase):
    """What a visitor can now do without sending an enquiry."""

    def test_a_visitor_books_and_orders_without_contacting_anyone(self):
        env = self.env
        leads_before = env['crm.lead'].search_count([('enquiry_source', '=', 'website'), ('enquiry_type', '!=', 'court')])
        booking_response = self.book('15:00', name='Instant Visitor', email='instant@example.com')
        self.assertEqual(booking_response.status_code, 303)
        booking = env['club.booking'].search([('access_token', '=', self.token_of(booking_response))])
        self.assertEqual(booking.state, 'confirmed')                  # no staff step
        self.post('/club-shop/cart/add', product_id=self.balls.id, qty=1)
        order_response = self.post('/club-shop/checkout/submit', name='Instant Visitor', email='instant@example.com',
                                   phone='+91 90000 88888', fulfillment='collect')
        self.assertEqual(order_response.status_code, 303)
        order = env['club.order'].search([('customer_email', '=', 'instant@example.com')])
        self.assertEqual((order.channel, order.state), ('shop', 'paid'))
        # nothing in the CRM needed anyone's action beyond a prospect to offer a membership to
        self.assertEqual(env['crm.lead'].search_count(
            [('enquiry_source', '=', 'website'), ('enquiry_type', '!=', 'court')]), leads_before)
