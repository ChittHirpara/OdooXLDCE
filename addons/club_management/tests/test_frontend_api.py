import json
import re
from pathlib import Path

from odoo import Command
from odoo.addons.club_management.models.booking import club_today
from odoo.exceptions import ValidationError
from odoo.tests import HttpCase, TransactionCase, tagged

from .common import FRI, MON, club_dt

MODULE = Path(__file__).resolve().parents[1]
ORM_CALL = re.compile(r'orm\.call\(\s*"([\w.]+)"\s*,\s*"(\w+)"', re.S)


@tagged('post_install', '-at_install', 'club_management')
class TestFrontendContract(TransactionCase):
    """The OWL screens call the server by model and method name. A rename or a typo on
    either side silently switches a screen to mock data, so check every call exists."""

    def test_every_orm_call_in_the_screens_has_a_backend_method(self):
        calls = set()
        for js in (MODULE / 'static/src/components').rglob('*.js'):
            calls |= set(ORM_CALL.findall(js.read_text(encoding='utf-8')))
        self.assertGreater(len(calls), 10, "expected the screens to make many server calls")
        missing = [(model, method) for model, method in sorted(calls)
                   if model not in self.env or not callable(getattr(self.env[model], method, None))]
        self.assertFalse(missing, "the screens call server methods that do not exist: %s" % missing)

    def test_report_filters_use_only_client_side_safe_domains(self):
        """Search-view filter domains are evaluated in the browser, whose evaluator does not
        support date.replace(...) (it crashed the revenue report). Use relativedelta."""
        for xml in (MODULE / 'views').glob('*.xml'):
            for domain in re.findall(r'domain="([^"]*)"', xml.read_text(encoding='utf-8')):
                self.assertNotIn('.replace(', domain, "%s: %s" % (xml.name, domain))


class FrontendCommon(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        cls.bar_categ = env.ref('club_management.product_category_bar')
        cls.shop_categ = env.ref('club_management.product_category_shop')
        cls.location = env['stock.warehouse'].search([], limit=1).lot_stock_id
        Product = env['product.product']
        cls.latte = Product.create({
            'name': 'Test Latte', 'list_price': 200.0, 'detailed_type': 'product',
            'categ_id': cls.bar_categ.id, 'club_category': 'coffee'})
        cls.grip = Product.create({
            'name': 'Test Grip', 'list_price': 300.0, 'detailed_type': 'product',
            'categ_id': cls.shop_categ.id, 'club_category': 'accessories'})
        cls.water = Product.create({           # not stock-tracked
            'name': 'Test Water', 'list_price': 50.0, 'detailed_type': 'consu',
            'categ_id': cls.bar_categ.id, 'club_category': 'drinks'})
        cls.empty = Product.create({
            'name': 'Test Empty', 'list_price': 100.0, 'detailed_type': 'product',
            'categ_id': cls.bar_categ.id, 'club_category': 'snacks'})
        Quant = env['stock.quant']
        Quant._update_available_quantity(cls.latte, cls.location, 10)
        Quant._update_available_quantity(cls.grip, cls.location, 5)

        today = club_today()
        Partner = env['res.partner']

        def member(name, plan, **extra):
            partner = Partner.create(dict(name=name, plan_id=env.ref('club_management.plan_' + plan).id, **extra))
            partner.action_activate_membership()
            return partner

        cls.gold = member('Fe Gold', 'gold')
        cls.silver = member('Fe Silver', 'silver')
        cls.junior = member('Fe Junior', 'junior', date_of_birth=today.replace(year=today.year - 12))
        cls.lapsed = Partner.create({
            'name': 'Fe Lapsed', 'is_member': True, 'plan_id': env.ref('club_management.plan_gold').id,
            'expiry_date': today.replace(year=today.year - 1)})
        cls.table = env['club.pos.table'].create({
            'name': 'Test Table', 'status': 'occupied', 'active_order_ref': 'POS-1',
            'active_order_amount': 99.0, 'member_name': 'Someone'})
        cls.service = env['club.order.service']

    def stock(self, product):
        product.invalidate_recordset(['qty_available'])    # computed from quants, not cached
        return int(product.qty_available)

    def cart(self, *pairs):
        """Basket exactly as the bar screen sends it: [{product: {...}, qty}]."""
        return [{'product': {'id': product.id, 'name': product.name}, 'qty': qty} for product, qty in pairs]


@tagged('post_install', '-at_install', 'club_management')
class TestOrderPricing(FrontendCommon):

    def price(self, partner, *pairs, **kw):
        return self.service.calculate_order_pricing(
            [{'product_id': p.id, 'qty': q} for p, q in pairs], partner_id=partner.id if partner else 0, **kw)

    def test_gold_bar_discount_comes_from_the_plan(self):
        result = self.price(self.gold, (self.latte, 2))
        self.assertEqual((result['subtotal'], result['discount_amount'], result['total']), (400.0, 60.0, 340.0))
        self.assertEqual(result['discount_label'], 'Gold Member Discount (15%)')
        self.assertEqual(result['formatted_total'], '₹340.00')

    def test_gold_shop_discount_differs_from_bar(self):
        self.assertEqual(self.price(self.gold, (self.grip, 1))['total'], 240.0)    # 20% shop

    def test_junior_has_shop_discount_but_no_bar_discount(self):
        self.assertEqual(self.price(self.junior, (self.latte, 1))['total'], 200.0)
        self.assertEqual(self.price(self.junior, (self.grip, 1))['total'], 285.0)   # 5%

    def test_mixed_basket_applies_each_category_rate(self):
        self.assertEqual(self.price(self.gold, (self.latte, 1), (self.grip, 1))['total'], 170.0 + 240.0)

    def test_lapsed_member_and_walkin_pay_full_price(self):
        self.assertEqual(self.price(self.lapsed, (self.latte, 1))['total'], 200.0)
        self.assertEqual(self.price(None, (self.latte, 1))['total'], 200.0)
        self.assertEqual(self.price(None, (self.latte, 1))['discount_label'], 'No Discount')

    def test_partner_id_wins_over_a_claimed_plan_code(self):
        result = self.service.calculate_order_pricing(
            [{'product_id': self.latte.id, 'qty': 1}], 'gold', self.junior.id)
        self.assertEqual(result['total'], 200.0)       # junior has no bar discount

    def test_plan_code_alone_is_a_fallback(self):
        result = self.service.calculate_order_pricing([{'product_id': self.latte.id, 'qty': 1}], 'silver')
        self.assertEqual(result['total'], 180.0)

    def test_price_matches_the_real_pos_pricelist(self):
        """Single source of truth: the same number Odoo's POS would charge."""
        plan = self.env.ref('club_management.plan_gold')
        expected = plan.pricelist_id._get_product_price(self.latte, 1.0)
        self.assertEqual(self.price(self.gold, (self.latte, 1))['total'], expected)

    def test_changing_the_plan_discount_changes_the_screen_price(self):
        self.env.ref('club_management.plan_gold').bar_discount = 25.0
        self.assertEqual(self.price(self.gold, (self.latte, 1))['total'], 150.0)

    def test_unknown_product_and_bad_quantity_rejected(self):
        with self.assertRaises(ValidationError):
            self.service.calculate_order_pricing([{'product_id': 999999999, 'qty': 1}], partner_id=0)
        with self.assertRaises(ValidationError):
            self.service.calculate_order_pricing([{'product_id': self.latte.id, 'qty': -2}], partner_id=0)

    def test_empty_basket_prices_to_zero(self):
        self.assertEqual(self.service.calculate_order_pricing([], partner_id=0)['total'], 0.0)


@tagged('post_install', '-at_install', 'club_management')
class TestBarPayment(FrontendCommon):

    def pay(self, member, *pairs, **extra):
        vals = {'table_name': 'Test Table', 'member_id': member.id if member else 0,
                'member_name': member.name if member else 'Walk-in Guest', 'payment_method': 'upi',
                'items': self.cart(*pairs)}
        vals.update(extra)
        return self.env['club.pos.order'].process_payment_api(vals)

    def test_payment_creates_a_real_order_and_deducts_stock(self):
        result = self.pay(self.gold, (self.latte, 2))
        self.assertTrue(result['success'])
        self.assertEqual(result['amount'], '₹340.00')
        order = self.env['club.order'].browse(result['order_id'])
        self.assertEqual(result['order_ref'], order.name)
        self.assertTrue(order.name.startswith('ORD/'))
        self.assertEqual((order.channel, order.partner_id, order.total, order.discount),
                         ('bar', self.gold, 340.0, 60.0))
        self.assertEqual(order.plan_id, self.env.ref('club_management.plan_gold'))
        self.assertEqual(order.payment_method, 'upi')
        self.assertEqual(self.stock(self.latte), 8)

    def test_payment_frees_the_table(self):
        self.pay(self.gold, (self.latte, 1))
        self.assertEqual(self.table.status, 'available')
        self.assertFalse(self.table.active_order_ref)
        self.assertFalse(self.table.member_name)

    def test_client_supplied_prices_are_ignored(self):
        result = self.pay(self.gold, (self.latte, 1), pricing={'total': 1, 'formatted_total': '₹1.00'})
        self.assertEqual(result['amount'], '₹170.00')

    def test_walkin_and_lapsed_member_pay_full_price(self):
        walkin = self.pay(None, (self.latte, 1))
        lapsed = self.pay(self.lapsed, (self.latte, 1))
        for result in (walkin, lapsed):
            self.assertEqual(result['amount'], '₹200.00')
        order = self.env['club.order'].browse(walkin['order_id'])
        self.assertFalse(order.partner_id)
        self.assertEqual(order.customer_name, 'Walk-in Guest')
        self.assertFalse(self.env['club.order'].browse(lapsed['order_id']).plan_id)

    def test_not_enough_stock_is_refused_and_nothing_changes(self):
        before = self.env['club.order'].search_count([])
        result = self.pay(self.gold, (self.latte, 11))
        self.assertFalse(result['success'])
        self.assertIn('Only 10 x Test Latte left', result['message'])
        self.assertEqual(self.env['club.order'].search_count([]), before)
        self.assertEqual(self.stock(self.latte), 10)
        self.assertEqual(self.table.status, 'occupied')

    def test_a_failed_second_line_does_not_deduct_the_first(self):
        result = self.pay(self.gold, (self.latte, 2), (self.empty, 1))
        self.assertFalse(result['success'])
        self.assertEqual(self.stock(self.latte), 10)

    def test_untracked_products_never_run_out(self):
        self.assertTrue(self.pay(None, (self.water, 500))['success'])

    def test_invalid_requests_return_a_message(self):
        self.assertIn('payment method', self.pay(self.gold, (self.latte, 1), payment_method='bitcoin')['message'])
        self.assertIn('empty', self.pay(self.gold)['message'])

    def test_orders_get_distinct_sequential_references(self):
        first, second = self.pay(None, (self.water, 1)), self.pay(None, (self.water, 1))
        self.assertNotEqual(first['order_ref'], second['order_ref'])

    def test_shift_totals_come_from_todays_orders(self):
        self.pay(self.gold, (self.latte, 2))                                  # 340 upi
        self.pay(None, (self.latte, 1), payment_method='cash')                # 200 cash
        shift = self.service.current_shift()
        self.assertGreaterEqual(shift['orders_count'], 2)
        self.assertEqual(shift['total_sales'], shift['cash_sales'] + shift['card_sales'] + shift['upi_sales'])
        self.assertGreaterEqual(shift['upi_sales'], 340.0)
        self.assertGreaterEqual(shift['cash_sales'], 200.0)
        self.assertTrue(shift['formatted_total'].startswith('₹'))

    def test_recent_orders_feed(self):
        result = self.pay(self.gold, (self.latte, 1))
        recent = self.env['club.pos.order'].get_recent_orders()
        self.assertEqual(recent[0]['order_ref'], result['order_ref'])
        self.assertEqual((recent[0]['table'], recent[0]['member'], recent[0]['method']),
                         ('Test Table', 'Fe Gold', 'UPI'))


@tagged('post_install', '-at_install', 'club_management')
class TestShopCheckout(FrontendCommon):

    def place(self, member, *pairs, **extra):
        vals = {'partner_id': member.id if member else 0, 'items': [
            {'product_id': p.id, 'qty': q} for p, q in pairs]}
        vals.update(extra)
        return self.env['club.shop.order'].place_order(vals)

    def test_checkout_creates_an_order_with_the_member_discount(self):
        result = self.place(self.gold, (self.grip, 1), fulfillment='Home Delivery', delivery_address='12 MG Road')
        self.assertTrue(result['success'])
        self.assertEqual((result['subtotal'], result['discount'], result['total']),
                         ('₹300.00', '-₹60.00', '₹240.00'))
        order = self.env['club.order'].search([('name', '=', result['order_id'])])
        self.assertEqual((order.channel, order.partner_id, order.fulfillment, order.delivery_address),
                         ('shop', self.gold, 'Home Delivery', '12 MG Road'))
        self.assertEqual(self.stock(self.grip), 4)

    def test_checkout_refuses_more_than_the_stock(self):
        result = self.place(self.gold, (self.grip, 6))
        self.assertFalse(result['success'])
        self.assertIn('Only 5 x Test Grip', result['message'])
        self.assertEqual(self.stock(self.grip), 5)

    def test_guest_checkout_pays_list_price(self):
        self.assertEqual(self.place(None, (self.grip, 2), customer_name='Visitor')['total'], '₹600.00')


@tagged('post_install', '-at_install', 'club_management')
class TestCatalogFeeds(FrontendCommon):

    def test_bar_feed_reports_real_stock(self):
        products = {p['name']: p for p in self.env['club.pos.product'].get_products_data('all', '')}
        self.assertEqual(products['Test Latte']['stock'], 10)
        self.assertTrue(products['Test Latte']['is_available'])
        self.assertEqual(products['Test Empty']['stock'], 0)
        self.assertFalse(products['Test Empty']['is_available'])
        self.assertEqual(products['Test Water']['stock'], 99)          # untracked

    def test_bar_feed_excludes_shop_products_and_filters_by_category(self):
        names = [p['name'] for p in self.env['club.pos.product'].get_products_data('all', '')]
        self.assertNotIn('Test Grip', names)
        coffee = self.env['club.pos.product'].get_products_data('coffee', '')
        self.assertTrue(coffee and all(p['category'] == 'coffee' for p in coffee))
        self.assertEqual([p['name'] for p in self.env['club.pos.product'].get_products_data('all', 'Latte')],
                         ['Test Latte'])

    def test_shop_feed_shows_the_member_price_from_the_pricelist(self):
        by_name = lambda partner: {p['name']: p for p in self.env['club.shop.product'].get_shop_catalog(  # noqa: E731
            'all', '', partner)}
        self.assertEqual(by_name(self.gold.id)['Test Grip']['member_price'], 240.0)
        self.assertEqual(by_name(self.silver.id)['Test Grip']['member_price'], 270.0)
        self.assertEqual(by_name(0)['Test Grip']['member_price'], 300.0)
        self.assertEqual(by_name(self.lapsed.id)['Test Grip']['member_price'], 300.0)
        self.assertEqual(by_name(self.gold.id)['Test Grip']['stock'], 5)
        self.assertNotIn('Test Latte', by_name(self.gold.id))

    def test_reading_the_tables_never_writes(self):
        self.env['club.pos.table'].search([]).unlink()
        self.assertEqual(self.env['club.pos.table'].get_tables_data(), [])
        self.assertEqual(self.env['club.pos.table'].search_count([]), 0)

    def test_members_list_and_current_member_hide_lapsed_benefits(self):
        members = {m['name']: m for m in self.env['res.partner'].get_members_list()}
        self.assertEqual((members['Fe Gold']['planCode'], members['Fe Gold']['discountPct']), ('gold', 15.0))
        self.assertEqual(members['Fe Lapsed']['planCode'], 'none')
        self.assertEqual(members['Fe Lapsed']['discountPct'], 0.0)
        self.assertEqual(members['Fe Lapsed']['status'], 'expired')
        self.assertEqual(members['Walk-in Guest']['id'], 0)

    def test_plans_have_distinct_annual_fees(self):
        fees = {p['code']: p['price'] for p in self.env['club.membership.plan'].get_frontend_plans()}
        self.assertEqual(fees, {'gold': 5000.0, 'silver': 3000.0, 'junior': 1500.0})


@tagged('post_install', '-at_install', 'club_management')
class TestBookingScreenApi(FrontendCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.court = cls.env['club.court'].create({
            'name': 'Api Court', 'sport': 'tennis', 'list_price': 800.0, 'social_capacity': 4})
        cls.Booking = cls.env['club.booking']

    def book(self, hour, partner, day='2026-10-05', minute=0, **kw):
        return self.Booking.create_booking_api(
            self.court.id, day, '%02d:%02d' % (hour, minute), partner.id if partner else 0, **kw)

    def test_availability_lists_booked_start_times_per_court(self):
        self.assertEqual(self.Booking.get_availability('2026-10-05')[self.court.id], [])
        self.book(10, self.gold)
        self.assertEqual(self.Booking.get_availability('2026-10-05')[self.court.id], ['09:30', '10:00', '10:30'])

    def test_successful_booking_has_the_shape_the_screen_needs(self):
        result = self.book(10, self.gold)
        self.assertTrue(result['success'])
        booking = result['booking']
        record = self.Booking.browse(booking['odoo_id'])
        self.assertEqual(booking['id'], record.name)           # reference to show
        self.assertEqual((booking['court_name'], booking['date'], booking['start_time'], booking['end_time']),
                         ('Api Court', '2026-10-05', '10:00', '11:00'))
        self.assertEqual((booking['price'], booking['state'], booking['member_name']),
                         ('₹0', 'confirmed', 'Fe Gold'))
        self.assertEqual((record.partner_id, record.state, record.tier), (self.gold, 'confirmed', 'gold'))

    def test_rule_violations_come_back_as_messages_and_leave_nothing_behind(self):
        self.book(10, self.gold)
        count = self.Booking.search_count([])
        overlap = self.book(10, self.silver, minute=30)
        self.assertFalse(overlap['success'])
        self.assertIn('already booked', overlap['message'])
        self.book(12, self.gold)
        third = self.book(14, self.gold)
        self.assertFalse(third['success'])
        self.assertIn('maximum per day', third['message'])
        self.assertEqual(self.Booking.search_count([]), count + 1)       # only the 12:00 one

    def test_bad_input_is_reported(self):
        self.assertIn('Member not found', self.book(10, self.gold.browse(987654321))['message'])
        bad = self.Booking.create_booking_api(self.court.id, '2026-10-05', 'ten o clock', self.gold.id)
        self.assertFalse(bad['success'])
        self.assertIn('Invalid date/time', bad['message'])
        off_grid = self.book(10, self.gold, minute=15)
        self.assertIn('hour or half hour', off_grid['message'])

    def test_walkin_guest_id_zero_books_as_a_walkin(self):
        result = self.book(10, None)
        self.assertTrue(result['success'])
        record = self.Booking.browse(result['booking']['odoo_id'])
        self.assertFalse(record.partner_id)
        self.assertEqual((record.walkin_name, record.price, record.tier), ('Walk-in Guest', 800.0, 'guest'))

    def test_screen_price_equals_the_charged_price(self):
        for partner in (self.gold, self.silver, self.junior, self.lapsed, None):
            quoted = self.Booking.calculate_booking_price(
                self.court.id, '2026-10-06', '10:00', partner.id if partner else 0)
            booked = self.book(10, partner, day='2026-10-06')['booking']
            self.assertEqual(quoted['formatted_price'], booked['price'], partner and partner.name)
            self.Booking.browse(booked['odoo_id']).action_cancel()

    def test_my_bookings_and_cancel(self):
        booking = self.book(10, self.silver)['booking']
        mine = self.Booking.get_partner_bookings(self.silver.id)
        self.assertEqual([b['odoo_id'] for b in mine], [booking['odoo_id']])
        self.assertEqual(mine[0]['id'], booking['id'])
        self.Booking.action_cancel([booking['odoo_id']]) if False else self.Booking.browse(booking['odoo_id']).action_cancel()
        self.assertEqual(self.Booking.get_partner_bookings(self.silver.id)[0]['state'], 'cancelled')
        self.assertEqual(self.Booking.get_availability('2026-10-05')[self.court.id], [])

    def test_friday_social_availability_tracks_capacity(self):
        self.book(18, None, day='2026-10-09', players=3)
        self.assertEqual(self.Booking.get_availability('2026-10-09')[self.court.id], [])   # 1 place left
        self.book(18, None, day='2026-10-09', players=1)
        self.assertEqual(self.Booking.get_availability('2026-10-09')[self.court.id],
                         ['17:30', '18:00', '18:30'])


@tagged('post_install', '-at_install', 'club_management')
class TestControllerSecurity(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        cls.court = env['club.court'].create({'name': 'Http Court', 'sport': 'tennis', 'list_price': 800.0})
        cls.victim = env['res.partner'].create({'name': 'Victim Member'})
        Users = env['res.users'].with_context(no_reset_password=True)
        base_user = env.ref('base.group_user')
        cls.plain = Users.create({'name': 'Plain User', 'login': 'club_plain', 'password': 'club_plain_pw',
                                  'groups_id': [Command.set([base_user.id])]})
        cls.staff = Users.create({'name': 'Staff User', 'login': 'club_staff', 'password': 'club_staff_pw',
                                  'groups_id': [Command.set([base_user.id,
                                                             env.ref('club_management.group_club_staff').id])]})

    def rpc(self, route, **params):
        response = self.url_open(route, data=json.dumps({'jsonrpc': '2.0', 'method': 'call', 'params': params}),
                                 headers={'Content-Type': 'application/json'})
        return response.json()

    def booking_params(self, partner):
        return {'court_id': self.court.id, 'date': '2026-10-05', 'time': '10:00', 'partner_id': partner.id}

    def test_anonymous_cannot_create_bookings(self):
        before = self.env['club.booking'].search_count([])
        reply = self.rpc('/club/api/booking/create', **self.booking_params(self.victim))
        self.assertIn('error', reply)
        self.assertEqual(self.env['club.booking'].search_count([]), before)

    def test_a_plain_user_can_only_book_for_themselves(self):
        self.authenticate('club_plain', 'club_plain_pw')
        reply = self.rpc('/club/api/booking/create', **self.booking_params(self.victim))
        self.assertTrue(reply['result']['success'], reply)
        booking = self.env['club.booking'].browse(reply['result']['booking']['odoo_id'])
        self.assertEqual(booking.partner_id, self.plain.partner_id)
        self.assertNotEqual(booking.partner_id, self.victim)

    def test_staff_can_book_for_a_member(self):
        self.authenticate('club_staff', 'club_staff_pw')
        reply = self.rpc('/club/api/booking/create', **self.booking_params(self.victim))
        self.assertTrue(reply['result']['success'], reply)
        booking = self.env['club.booking'].browse(reply['result']['booking']['odoo_id'])
        self.assertEqual(booking.partner_id, self.victim)

    def test_booking_rule_errors_are_returned_not_raised(self):
        self.authenticate('club_staff', 'club_staff_pw')
        self.rpc('/club/api/booking/create', **self.booking_params(self.victim))
        again = self.rpc('/club/api/booking/create', **self.booking_params(self.victim))
        self.assertFalse(again['result']['success'])
        self.assertIn('already booked', again['result']['error'])

    def test_pos_catalog_is_staff_only(self):
        anonymous = self.url_open('/club/api/pos/catalog', allow_redirects=False)
        self.assertIn(anonymous.status_code, (301, 302, 303, 401, 403))
        self.authenticate('club_plain', 'club_plain_pw')
        self.assertEqual(self.url_open('/club/api/pos/catalog').status_code, 403)
        self.authenticate('club_staff', 'club_staff_pw')
        reply = self.url_open('/club/api/pos/catalog')
        self.assertEqual(reply.status_code, 200)
        self.assertIn('tables', reply.json())

    def test_public_catalogs_still_work_without_login(self):
        self.assertEqual(self.url_open('/club/api/plans').status_code, 200)
        self.assertEqual(self.url_open('/club/api/courts').status_code, 200)
        self.assertEqual(self.url_open('/club/api/shop/catalog').status_code, 200)
