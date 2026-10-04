import json
import re
from datetime import datetime, time
from urllib.parse import parse_qs, urlparse

import pytz

from odoo import Command, http
from odoo.tests import HttpCase, tagged

IST = pytz.timezone('Asia/Kolkata')


def club_dt(year, month, day, hour):
    local = IST.localize(datetime.combine(datetime(year, month, day).date(), time(hour, 0)))
    return local.astimezone(pytz.utc).replace(tzinfo=None)


class WebsiteCase(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        shop = env.ref('club_management.product_category_shop')
        bar = env.ref('club_management.product_category_bar')
        location = env['stock.warehouse'].search([], limit=1).lot_stock_id
        Product = env['product.product']
        cls.grip = Product.create({
            'name': 'Webtest Grip', 'list_price': 300.0, 'standard_price': 111.37, 'detailed_type': 'product',
            'categ_id': shop.id, 'club_category': 'accessories', 'description_sale': 'Soft tacky grip.'})
        cls.sold_out = Product.create({
            'name': 'Webtest Sold Out Racket', 'list_price': 5000.0, 'detailed_type': 'product',
            'categ_id': shop.id, 'club_category': 'rackets'})
        cls.balls = Product.create({
            'name': 'Webtest Balls', 'list_price': 400.0, 'detailed_type': 'product',
            'categ_id': shop.id, 'club_category': 'balls'})
        cls.latte = Product.create({
            'name': 'Webtest Latte', 'list_price': 200.0, 'detailed_type': 'consu',
            'categ_id': bar.id, 'club_category': 'coffee'})
        cls.hidden = Product.create({
            'name': 'Webtest Hidden', 'list_price': 10.0, 'detailed_type': 'consu',
            'categ_id': shop.id, 'sale_ok': False})
        Quant = env['stock.quant']
        Quant._update_available_quantity(cls.grip, location, 3)       # "Only 3 left"
        Quant._update_available_quantity(cls.balls, location, 40)
        cls.court = env['club.court'].create({
            'name': 'Webtest Court', 'sport': 'padel', 'list_price': 700.0, 'surface': 'Glass'})
        cls.gold = env.ref('club_management.plan_gold')
        cls.silver = env.ref('club_management.plan_silver')
        cls.junior = env.ref('club_management.plan_junior')

    def get(self, path, status=200):
        response = self.url_open(path)
        self.assertEqual(response.status_code, status, '%s -> %s' % (path, response.status_code))
        return response.text

    def submit(self, **data):
        self.authenticate(None, None)
        data['csrf_token'] = http.Request.csrf_token(self)
        return self.url_open('/join/submit', data=data)


@tagged('post_install', '-at_install', 'club_management', 'club_website')
class TestPages(WebsiteCase):

    def test_navigation_matches_the_site_map(self):
        names = ['Home', 'Membership', 'Courts', 'Shop', 'About', 'Contact', 'Join the Club']
        urls = ['/', '/membership', '/courts', '/club-shop', '/about', '/contact', '/join']
        menus = self.env.ref('website.default_website').menu_id.child_id.sorted('sequence')
        self.assertEqual(menus.mapped('name'), names)
        self.assertEqual(menus.mapped('url'), urls)
        # ...and visitors see them, in that order, in the header
        header = self.get('/').split('<main')[0]
        positions = [header.find('href="%s"' % url) for url in urls[1:]]
        self.assertTrue(all(p >= 0 for p in positions), positions)
        self.assertEqual(positions, sorted(positions))

    def test_the_stock_contact_page_redirects_to_the_crm_form(self):
        response = self.url_open('/contactus', allow_redirects=False)
        self.assertEqual(response.status_code, 301)
        self.assertTrue(response.headers['Location'].endswith('/contact'))

    def test_the_site_is_branded_as_the_club(self):
        html = self.get('/')
        self.assertIn('The Champions Club', html)
        self.assertNotIn('YourLogo', html)
        self.assertNotIn('555-555-5556', html)                      # Odoo's sample phone number
        self.assertEqual(self.env.ref('website.default_website').name, 'The Champions Club')
        logo = self.url_open('/web/image/website/%s/logo' % self.env.ref('website.default_website').id)
        self.assertEqual(logo.status_code, 200)
        self.assertIn(b'CHAMPIONS CLUB', logo.content)

    def test_every_public_page_opens_for_an_anonymous_visitor(self):
        for path in ('/', '/membership', '/courts', '/club-shop', '/about', '/contact', '/join'):
            html = self.get(path)
            self.assertIn('club-site', html, path)
            self.assertIn('/join', html, path)         # always one click from the enquiry

    def test_home_is_a_gateway_into_the_modules(self):
        html = self.get('/')
        for expected in ('Where champions train', 'Gold', 'Silver', 'Junior', 'Open courts today',
                         'Webtest Court', 'club-product-name', 'Join the Club', '/membership', '/courts', '/club-shop'):
            self.assertIn(expected, html)
        for sport in ('Tennis', 'Padel', 'Badminton', 'Cricket'):
            self.assertIn(sport, html)
        self.assertIn('Cafeteria', html)

    def test_home_shows_only_four_products_and_no_bar_items(self):
        html = self.get('/')
        self.assertLessEqual(html.count('club-product-name'), 4)
        self.assertNotIn('Webtest Latte', html)

    def test_membership_page_comes_from_the_plans(self):
        html = self.get('/membership')
        self.assertIn('₹5,000', html)
        self.assertIn('₹3,000', html)
        self.assertIn('₹1,500', html)
        self.assertIn('365 days', html)
        self.assertIn('Courts at ₹500 per hour', html)
        self.assertIn('Court bookings included', html)                 # Gold: free courts
        self.assertIn('20% off in the Pro-Shop', html)
        self.assertIn('15% off at the bar and cafeteria', html)
        self.assertIn('Bar and cafeteria at standard prices', html)    # Junior: no bar discount
        self.assertIn('Under 18', html)
        for code in ('gold', 'silver', 'junior'):
            self.assertIn('/join?type=membership&amp;plan=%s' % code, html)
        self.assertIn('Compare the plans', html)

    def test_membership_page_follows_a_plan_change(self):
        self.silver.write({'price': 3500.0, 'shop_discount': 12.0})
        html = self.get('/membership')
        self.assertIn('₹3,500', html)
        self.assertNotIn('₹3,000', html)
        self.assertIn('12% off in the Pro-Shop', html)

    def test_courts_page_has_the_availability_widget_and_the_courts(self):
        html = self.get('/courts')
        self.assertIn('club-availability', html)
        self.assertIn('data-endpoint="/club/availability"', html)
        self.assertIn('js-date', html)
        self.assertIn('js-sport', html)
        self.assertIn('Webtest Court', html)
        self.assertIn('Padel', html)
        self.assertIn('Glass', html)
        self.assertIn('₹700', html)

    def test_the_widget_endpoint_reflects_real_bookings(self):
        self.env['club.booking'].create({
            'court_id': self.court.id, 'start_datetime': club_dt(2026, 10, 5, 10), 'walkin_name': 'Someone'})
        data = json.loads(self.get('/club/availability?date=2026-10-05&court_id=%s' % self.court.id))
        slots = {s['start']: s['available'] for s in data['courts'][0]['slots']}
        self.assertFalse(slots['10:00'])
        self.assertFalse(slots['09:30'])
        self.assertTrue(slots['11:00'])
        padel = json.loads(self.get('/club/availability?date=2026-10-05&sport=padel'))
        self.assertTrue(all(c['sport'] == 'padel' for c in padel['courts']))

    def test_the_site_assets_are_in_the_frontend_bundle(self):
        html = self.get('/courts')
        bundles = re.findall(r'(?:src|href)="(/web/assets/[^"]+assets_frontend[^"]*)"', html)
        self.assertTrue(bundles, "no frontend bundle on the page")
        js = [self.get(path) for path in bundles if path.endswith('.js')]
        css = [self.get(path) for path in bundles if path.endswith('.css')]
        self.assertTrue(any('ClubCourtAvailability' in text for text in js), "availability widget missing")
        self.assertTrue(any('.club-site' in text for text in css), "club styles missing")


@tagged('post_install', '-at_install', 'club_management', 'club_website')
class TestShopPages(WebsiteCase):

    def test_shop_lists_shop_products_with_live_stock(self):
        html = self.get('/club-shop')
        self.assertIn('Webtest Grip', html)
        self.assertIn('Only 3 left', html)
        self.assertIn('In stock', html)
        self.assertIn('Out of stock', html)
        self.assertIn('₹300', html)
        self.assertIn('Members save up to 20%', html)

    def test_shop_hides_bar_items_membership_products_and_unsellable_products(self):
        html = self.get('/club-shop')
        for hidden in ('Webtest Latte', 'Webtest Hidden', 'Membership (365 days)'):
            self.assertNotIn(hidden, html)

    def test_shop_search_and_category_filters(self):
        found = self.get('/club-shop?q=Grip')
        self.assertIn('Webtest Grip', found)
        self.assertNotIn('Webtest Balls', found)
        category = self.get('/club-shop?category=balls')
        self.assertIn('Webtest Balls', category)
        self.assertNotIn('Webtest Grip', category)
        self.assertIn('Nothing matches', self.get('/club-shop?q=zzzzzz-nothing'))
        self.assertIn('Webtest Grip', self.get('/club-shop?category=not-a-category'))   # ignored, not an error

    def test_search_text_is_escaped(self):
        html = self.get('/club-shop?q=%3Cscript%3Ealert(1)%3C/script%3E')
        self.assertNotIn('<script>alert(1)</script>', html)

    def test_shop_never_shows_costs(self):
        html = self.get('/club-shop') + self.get('/club-shop/%s' % self.grip.id)
        self.assertNotIn('111.37', html)
        self.assertNotIn('111,37', html)
        self.assertNotIn('standard_price', html)

    def test_product_page_shows_member_prices_from_the_pricelists(self):
        html = self.get('/club-shop/%s' % self.grip.id)
        self.assertIn('Soft tacky grip.', html)
        self.assertIn('Member prices', html)
        self.assertIn('₹240', html)        # Gold 20% off 300
        self.assertIn('₹270', html)        # Silver 10%
        self.assertIn('₹285', html)        # Junior 5%
        self.assertIn('Only 3 left', html)

    def test_in_stock_products_have_an_add_to_cart_form(self):
        html = self.get('/club-shop/%s' % self.grip.id)
        self.assertIn('action="/club-shop/cart/add"', html)
        self.assertIn('name="product_id"', html)
        self.assertIn('Add to cart', html)
        self.assertNotIn('Reserve for pickup', html)

    def test_sold_out_product_offers_a_notify_enquiry_instead(self):
        html = self.get('/club-shop/%s' % self.sold_out.id)
        self.assertIn('Out of stock', html)
        self.assertNotIn('Add to cart', html)
        self.assertIn('Ask when it is back', html)

    def test_products_not_for_the_public_shop_are_404(self):
        for product in (self.latte, self.hidden, self.gold.product_id):
            self.get('/club-shop/%s' % product.id, status=404)
        self.get('/club-shop/999999999', status=404)


@tagged('post_install', '-at_install', 'club_management', 'club_website')
class TestJoinForm(WebsiteCase):

    def test_form_has_the_fields_a_visitor_needs_and_a_honeypot(self):
        html = self.get('/join')
        for name in ('name', 'email', 'phone', 'type', 'plan', 'sport', 'message', 'website_url', 'csrf_token'):
            self.assertIn('name="%s"' % name, html)
        for label in ('Membership', 'Court Booking', 'Pro-Shop', 'Gold', 'Silver', 'Junior', 'Tennis', 'Padel'):
            self.assertIn(label, html)

    def test_links_preselect_the_plan_and_type(self):
        html = self.get('/join?type=membership&plan=gold&sport=tennis')
        self.assertRegex(html, r'<option value="gold"[^>]*selected')
        self.assertRegex(html, r'<option value="tennis"[^>]*selected')
        self.assertRegex(self.get('/join?type=court'), r'<option value="court"[^>]*selected')

    def test_unknown_type_falls_back_to_membership(self):
        self.assertRegex(self.get('/join?type=whatever'), r'<option value="membership"[^>]*selected')

    def test_prefilled_text_is_escaped(self):
        html = self.get('/join?message=%3Cscript%3Ealert(1)%3C/script%3E')
        self.assertNotIn('<script>alert(1)</script>', html)

    def test_contact_page_posts_a_general_enquiry(self):
        self.assertRegex(self.get('/contact'), r'<option value="general"[^>]*selected')

    def test_submit_creates_the_crm_lead_and_shows_the_reference(self):
        response = self.submit(name='Rahul Patel', email='rahul.web@example.com', phone='+91 90000 12345',
                               type='membership', plan='gold', sport='tennis', message='Interested in coaching.')
        self.assertEqual(response.status_code, 200)
        ref = re.search(r'ENQ-\d{5}', response.text).group(0)
        lead = self.env['crm.lead'].search([('enquiry_ref', '=', ref)])
        self.assertEqual((lead.contact_name, lead.email_from, lead.interested_plan_id, lead.enquiry_source),
                         ('Rahul Patel', 'rahul.web@example.com', self.gold, 'website'))
        self.assertEqual((lead.stage_id.name, lead.sport_interest, lead.enquiry_type), ('New', 'tennis', 'membership'))
        self.assertTrue(lead.user_id)
        self.assertEqual(len(lead.activity_ids), 1)                     # the follow-up call
        self.assertIn('Interested in coaching.', lead.description)
        self.assertIn('Thank you, Rahul Patel', response.text)
        self.assertIn('/club/enquiry/status/%s' % lead.enquiry_token, response.text)

    def test_the_acknowledgment_email_is_queued(self):
        self.submit(name='Mail Person', email='mail.person@example.com', plan='silver')
        mail = self.env['mail.mail'].search([('email_to', '=', 'mail.person@example.com')])
        self.assertEqual(len(mail), 1)

    def test_contact_form_creates_a_general_enquiry_without_a_plan(self):
        response = self.submit(name='Gen Eral', email='gen.eral@example.com', type='general', message='Opening hours?')
        ref = re.search(r'ENQ-\d{5}', response.text).group(0)
        lead = self.env['crm.lead'].search([('enquiry_ref', '=', ref)])
        self.assertEqual((lead.enquiry_type, bool(lead.interested_plan_id)), ('general', False))

    def test_court_request_from_the_availability_grid_becomes_a_court_enquiry(self):
        response = self.submit(name='Court Seeker', phone='+91 90000 55555', type='court', sport='padel',
                               message='I would like to request Webtest Court on 2026-10-05 at 18:00.')
        lead = self.env['crm.lead'].search([('enquiry_ref', '=', re.search(r'ENQ-\d{5}', response.text).group(0))])
        self.assertEqual((lead.enquiry_type, lead.sport_interest), ('court', 'padel'))
        self.assertIn('Webtest Court on 2026-10-05 at 18:00', lead.description)

    def test_invalid_input_re_shows_the_form_with_the_message_and_keeps_the_values(self):
        before = self.env['crm.lead'].search_count([])
        response = self.submit(name='Typo Person', email='not-an-email', plan='gold', message='keep me')
        self.assertEqual(response.status_code, 400)
        self.assertIn('The email address is not valid.', response.text)
        self.assertIn('Typo Person', response.text)
        self.assertIn('keep me', response.text)
        self.assertEqual(self.env['crm.lead'].search_count([]), before)

    def test_missing_name_and_missing_contact_details_are_refused(self):
        self.assertIn('tell us your name', self.submit(name='', email='a@example.com').text)
        self.assertIn('email address or a phone number', self.submit(name='No Contact').text)

    def test_honeypot_looks_like_success_but_creates_nothing(self):
        before = self.env['crm.lead'].search_count([])
        response = self.submit(name='Bot', email='bot@example.com', plan='gold', website_url='http://spam.example')
        self.assertEqual(response.status_code, 200)
        self.assertIn('Thank you', response.text)
        self.assertNotIn('ENQ-', response.text)
        self.assertEqual(self.env['crm.lead'].search_count([]), before)

    def test_the_same_visitor_twice_gets_the_same_reference(self):
        first = re.search(r'ENQ-\d{5}', self.submit(name='Twice', email='twice@example.com', plan='gold').text).group(0)
        second = re.search(r'ENQ-\d{5}', self.submit(name='Twice', email='twice@example.com', plan='gold',
                                                      message='again').text).group(0)
        self.assertEqual(first, second)

    def test_post_without_a_csrf_token_is_rejected(self):
        before = self.env['crm.lead'].search_count([])
        response = self.url_open('/join/submit', data={'name': 'No Token', 'email': 'no.token@example.com'})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.env['crm.lead'].search_count([]), before)

    def test_names_with_markup_are_escaped_on_the_thank_you_page(self):
        response = self.submit(name='<b>Bold</b>', email='bold@example.com')
        self.assertNotIn('<b>Bold</b>', response.text)


@tagged('post_install', '-at_install', 'club_management', 'club_website')
class TestStatusPage(WebsiteCase):

    def enquire(self, email='status.web@example.com'):
        return self.env['crm.lead'].create_club_enquiry('Status Web', email=email, plan='gold')

    def test_timeline_marks_done_and_current_steps(self):
        lead = self.enquire()
        html = self.get('/club/enquiry/status/%s' % lead.enquiry_token)
        self.assertIn(lead.enquiry_ref, html)
        self.assertIn('club-timeline', html)
        self.assertEqual(html.count('club-step '), 6)
        self.assertEqual(len(re.findall(r'club-step\s+done', html)), 0)
        lead.stage_id = self.env.ref('crm.stage_lead3')                          # Interested
        html = self.get('/club/enquiry/status/%s' % lead.enquiry_token)
        self.assertEqual(len(re.findall(r'club-step\s+done', html)), 2)         # New, Contacted
        self.assertRegex(html, re.compile(r'club-step\s+current[^>]*>.*?Interested', re.S))

    def test_unknown_token_is_404(self):
        self.get('/club/enquiry/status/' + 'q' * 40, status=404)

    def test_closed_enquiry_has_no_timeline(self):
        lead = self.enquire('closed.web@example.com')
        lead.action_set_lost()
        html = self.get('/club/enquiry/status/%s' % lead.enquiry_token)
        self.assertIn('Closed', html)
        self.assertNotIn('club-timeline', html)

    def test_page_shows_no_internal_details(self):
        lead = self.enquire('private.web@example.com')
        lead.message_post(body='INTERNAL NOTE do not show')
        html = self.get('/club/enquiry/status/%s' % lead.enquiry_token)
        for secret in ('INTERNAL NOTE', 'private.web@example.com', lead.user_id.name):
            self.assertNotIn(secret, html)


@tagged('post_install', '-at_install', 'club_management', 'club_website')
class TestPublicSecurity(WebsiteCase):

    def rpc(self, route, **params):
        response = self.url_open(route, data=json.dumps({'jsonrpc': '2.0', 'method': 'call', 'params': params}),
                                 headers={'Content-Type': 'application/json'})
        return response.json()

    def test_the_public_cannot_read_leads_or_members_through_the_web_client_api(self):
        self.env['crm.lead'].create_club_enquiry('Secret', email='secret.lead@example.com', plan='gold')
        for model, fields in (('crm.lead', ['name', 'email_from']), ('res.partner', ['name', 'member_id']),
                              ('club.booking', ['name']), ('club.order', ['name'])):
            reply = self.rpc('/web/dataset/call_kw/%s/search_read' % model,
                             model=model, method='search_read', args=[[]], kwargs={'fields': fields})
            self.assertNotIn('result', reply, model)
            self.assertIn('error', reply, model)

    def test_the_public_cannot_book_order_or_open_the_pos_catalog(self):
        before = self.env['club.booking'].search_count([])
        reply = self.rpc('/club/api/booking/create', court_id=self.court.id, date='2026-10-05',
                         time='10:00', partner_id=1)
        self.assertIn('error', reply)
        self.assertEqual(self.env['club.booking'].search_count([]), before)
        self.assertIn(self.url_open('/club/api/pos/catalog', allow_redirects=False).status_code, (302, 303, 401, 403))


@tagged('post_install', '-at_install', 'club_management', 'club_website')
class TestVisitorToMemberJourney(WebsiteCase):
    """The flow from the specification, end to end."""

    def test_website_to_crm_to_member_to_the_whole_platform(self):
        env = self.env
        # 1-4. a visitor views Gold, checks availability and submits the enquiry
        self.assertIn('Gold', self.get('/membership'))
        self.assertIn('club-availability', self.get('/courts'))
        response = self.submit(name='Journey Visitor', email='journey@example.com', phone='+91 90000 99999',
                               type='membership', plan='gold', sport='tennis', message='Join please')
        ref = re.search(r'ENQ-\d{5}', response.text).group(0)
        # 5. the CRM lead exists, with a follow-up, assigned to a manager
        lead = env['crm.lead'].search([('enquiry_ref', '=', ref)])
        self.assertEqual((lead.stage_id.name, lead.interested_plan_id), ('New', self.gold))
        self.assertTrue(lead.activity_ids and lead.user_id)
        status_url = '/club/enquiry/status/%s' % lead.enquiry_token
        self.assertIn('Received', self.get(status_url))
        # 6-8. staff contact the visitor and mark them interested
        lead.activity_ids.action_feedback()
        lead.stage_id = env.ref('crm.stage_lead2')
        self.assertIn('We have been in touch', self.get(status_url))
        lead.stage_id = env.ref('crm.stage_lead3')
        # 9. quote
        lead.action_create_membership_quote()
        self.assertEqual(lead.stage_id.name, 'Quote Sent')
        self.assertIn('membership quote', self.get(status_url))
        quote = lead.order_ids
        self.assertEqual(quote.amount_total, 5000.0)
        # 10-11. the customer accepts: the lead is won
        quote.action_confirm()
        self.assertTrue(lead.stage_id.is_won)
        self.assertIn('Welcome to the club', self.get(status_url))
        # 12-13. the member exists and the membership is active
        member = lead.partner_id
        self.assertEqual((member.is_member, member.member_state, member.plan_id), (True, 'active', self.gold))
        self.assertTrue(member.member_id)
        # 14. the member books a court: Gold courts are free
        booking = env['club.booking'].create({
            'court_id': self.court.id, 'partner_id': member.id, 'start_datetime': club_dt(2026, 10, 6, 10)})
        self.assertEqual((booking.tier, booking.price), ('gold', 0.0))
        # 15. buys a product: Gold gets 20% off in the shop
        shop = env['club.shop.order'].place_order({
            'partner_id': member.id, 'items': [{'product_id': self.grip.id, 'qty': 1}]})
        self.assertEqual((shop['success'], shop['total']), (True, '₹240.00'))
        # 16. orders at the bar: Gold gets 15% off there
        bar = env['club.pos.order'].process_payment_api({
            'member_id': member.id, 'payment_method': 'upi', 'items': [{'product_id': self.latte.id, 'qty': 1}]})
        self.assertEqual((bar['success'], bar['amount']), (True, '₹170.00'))
        # 17. everything flowed into Odoo for this one person
        orders = env['club.order'].search([('partner_id', '=', member.id)])
        self.assertEqual(sorted(orders.mapped('channel')), ['bar', 'shop'])
        self.assertEqual(env['club.booking'].search_count([('partner_id', '=', member.id)]), 1)
        self.assertEqual(member.property_product_pricelist, self.gold.pricelist_id)
