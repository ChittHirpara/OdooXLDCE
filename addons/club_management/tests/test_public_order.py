from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install', 'club_management')
class TestPublicOrder(TransactionCase):
    """A visitor orders from the pro-shop online: priced and stocked by the server."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        cls.Service = env['club.order.service']
        shop = env.ref('club_management.product_category_shop')
        bar = env.ref('club_management.product_category_bar')
        location = env['stock.warehouse'].search([], limit=1).lot_stock_id
        Product = env['product.product']
        cls.grip = Product.create({'name': 'Po Grip', 'list_price': 300.0, 'detailed_type': 'product',
                                   'categ_id': shop.id, 'club_category': 'accessories'})
        cls.balls = Product.create({'name': 'Po Balls', 'list_price': 400.0, 'detailed_type': 'product',
                                    'categ_id': shop.id, 'club_category': 'balls'})
        cls.towel = Product.create({'name': 'Po Towel', 'list_price': 350.0, 'detailed_type': 'consu',
                                    'categ_id': shop.id, 'club_category': 'apparel'})
        cls.latte = Product.create({'name': 'Po Latte', 'list_price': 200.0, 'detailed_type': 'consu',
                                    'categ_id': bar.id, 'club_category': 'coffee'})
        cls.hidden = Product.create({'name': 'Po Hidden', 'list_price': 10.0, 'detailed_type': 'consu',
                                     'categ_id': shop.id, 'sale_ok': False})
        env['stock.quant']._update_available_quantity(cls.grip, location, 5)
        env['stock.quant']._update_available_quantity(cls.balls, location, 50)
        cls.gold = env['res.partner'].create({
            'name': 'Gold Orderer', 'email': 'gold.orderer@example.com',
            'plan_id': env.ref('club_management.plan_gold').id})
        cls.gold.action_activate_membership()

    def stock(self, product):
        product.invalidate_recordset(['qty_available'])
        return int(product.qty_available)

    def order(self, *pairs, **kw):
        kw.setdefault('name', 'Visitor')
        kw.setdefault('phone', '+91 90000 12345')
        kw.setdefault('email', 'visitor.order@example.com')
        return self.Service.place_public_order([{'product_id': p.id, 'qty': q} for p, q in pairs], **kw)

    # --- a guest orders ----------------------------------------------------
    def test_guest_order_is_priced_at_list_and_deducts_stock(self):
        order = self.order((self.grip, 2), (self.balls, 1))
        self.assertEqual((order.channel, order.source, order.state), ('shop', 'website', 'paid'))
        self.assertEqual((order.subtotal, order.discount, order.total), (1000.0, 0.0, 1000.0))
        self.assertEqual(order.fulfillment, 'Collect at Club')
        self.assertFalse(order.partner_id)
        self.assertEqual(order.customer_name, 'Visitor')
        self.assertTrue(order.name.startswith('ORD/'))
        self.assertGreaterEqual(len(order.access_token), 32)
        self.assertEqual(self.stock(self.grip), 3)
        self.assertEqual(self.stock(self.balls), 49)

    def test_untracked_products_can_be_ordered_without_a_stock_figure(self):
        self.assertTrue(self.order((self.towel, 3)))

    def test_contact_is_kept_and_normalised(self):
        order = self.order((self.towel, 1), phone='+91 (900) 00-12345', email=' Visitor.Order@Example.COM ')
        self.assertEqual(order.customer_phone, '+919000012345')
        self.assertEqual(order.customer_email, 'visitor.order@example.com')

    def test_delivery_needs_an_address_and_is_recorded(self):
        with self.assertRaisesRegex(ValidationError, 'delivery address'):
            self.order((self.towel, 1), fulfillment='delivery', address='12 MG')
        order = self.order((self.towel, 1), fulfillment='delivery', address='12 MG Road, Pune 411001')
        self.assertEqual((order.fulfillment, order.delivery_address), ('Home Delivery', '12 MG Road, Pune 411001'))

    def test_collect_ignores_any_address(self):
        self.assertFalse(self.order((self.towel, 1), address='somewhere').delivery_address)

    def test_unknown_fulfillment_is_refused(self):
        with self.assertRaises(ValidationError):
            self.order((self.towel, 1), fulfillment='drone')

    def test_a_guest_must_give_a_name_and_a_way_to_be_reached(self):
        with self.assertRaises(ValidationError):
            self.order((self.towel, 1), name=' ')
        with self.assertRaises(ValidationError):
            self.order((self.towel, 1), phone='', email='')

    # --- members get their price ------------------------------------------
    def test_a_verified_member_gets_the_tier_discount(self):
        order = self.order((self.grip, 1), name='ignored', member_ref=self.gold.member_id,
                           member_email='Gold.Orderer@example.com')
        self.assertEqual((order.partner_id, order.plan_id.code), (self.gold, 'gold'))
        self.assertEqual((order.subtotal, order.discount, order.total), (300.0, 60.0, 240.0))     # 20% shop
        self.assertEqual(order.customer_name, 'Gold Orderer')

    def test_a_failed_member_check_is_refused_with_one_vague_message(self):
        with self.assertRaisesRegex(ValidationError, 'could not verify'):
            self.order((self.grip, 1), member_ref=self.gold.member_id, member_email='wrong@example.com')
        with self.assertRaisesRegex(ValidationError, 'could not verify'):
            self.order((self.grip, 1), member_ref='CC-99999', member_email=self.gold.email)

    # --- only the public shop can be ordered online ------------------------
    def test_bar_items_membership_products_hidden_and_unknown_products_are_refused(self):
        plan_product = self.env.ref('club_management.plan_gold').product_id
        for product_id in (self.latte.id, plan_product.id, self.hidden.id, 999999999, 0):
            with self.assertRaisesRegex(ValidationError, 'not available online'):
                self.Service.place_public_order([{'product_id': product_id, 'qty': 1}],
                                                'V', phone='9000011111')

    def test_quantities_must_be_sensible(self):
        for qty in (0, -1, 21):
            with self.assertRaisesRegex(ValidationError, 'between 1 and 20'):
                self.order((self.towel, qty))
        self.assertTrue(self.order((self.towel, 20)))

    def test_an_empty_cart_is_refused(self):
        with self.assertRaisesRegex(ValidationError, 'empty'):
            self.Service.place_public_order([], 'V', phone='9000011111')

    # --- stock is respected ------------------------------------------------
    def test_more_than_the_stock_is_refused_and_nothing_changes(self):
        before = self.env['club.order'].search_count([])
        with self.assertRaisesRegex(ValidationError, 'Only 5 x Po Grip'):
            self.order((self.grip, 6))
        self.assertEqual(self.env['club.order'].search_count([]), before)
        self.assertEqual(self.stock(self.grip), 5)

    def test_a_failed_second_line_does_not_deduct_the_first(self):
        with self.assertRaises(ValidationError):
            self.order((self.balls, 2), (self.grip, 6))
        self.assertEqual(self.stock(self.balls), 50)

    def test_the_last_units_can_be_bought_then_it_is_sold_out(self):
        self.order((self.grip, 5))
        self.assertEqual(self.stock(self.grip), 0)
        with self.assertRaisesRegex(ValidationError, 'Only 0'):
            self.order((self.grip, 1))

    # --- e-mail and the private link ---------------------------------------
    def test_a_confirmation_email_with_the_order_and_link(self):
        order = self.order((self.grip, 2), email='order.mail@example.com')
        mail = self.env['mail.mail'].search([('email_to', '=', 'order.mail@example.com')])
        self.assertEqual(len(mail), 1)
        self.assertIn(order.name, mail.subject)
        self.assertIn('Po Grip', mail.body_html)
        self.assertIn('₹600', mail.body_html)
        self.assertIn('/club-shop/order/%s' % order.access_token, mail.body_html)

    def test_no_email_for_a_phone_only_guest(self):
        before = self.env['mail.mail'].search_count([('subject', 'like', 'Your Champions Club order')])
        self.order((self.towel, 1), email='')
        self.assertEqual(self.env['mail.mail'].search_count([('subject', 'like', 'Your Champions Club order')]), before)

    def test_lookup_by_token(self):
        order = self.order((self.towel, 1))
        self.assertEqual(self.env['club.order'].get_by_token(order.access_token), order)
        for bad in ('', None, 'short', 'q' * 40):
            self.assertFalse(self.env['club.order'].get_by_token(bad))

    def test_staff_orders_have_no_online_fields(self):
        result = self.env['club.pos.order'].process_payment_api({
            'member_id': 0, 'payment_method': 'cash', 'items': [{'product_id': self.towel.id, 'qty': 1}]})
        order = self.env['club.order'].browse(result['order_id'])
        self.assertEqual(order.source, 'staff')
        self.assertFalse(order.access_token)
