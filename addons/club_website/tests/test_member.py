import re

from odoo import Command
from odoo.tests import HttpCase, tagged

PNG_OR_SVG = ('image/png', 'image/svg+xml', 'image/jpeg')


@tagged('post_install', '-at_install', 'club_management', 'club_website')
class TestShopImages(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        shop = env.ref('club_management.product_category_shop')
        bar = env.ref('club_management.product_category_bar')
        svg = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10"><rect width="10" height="10"/></svg>')
        import base64
        picture = base64.b64encode(svg.encode())
        Product = env['product.product']
        cls.with_picture = Product.create({
            'name': 'Imgtest Racket', 'list_price': 100.0, 'categ_id': shop.id, 'image_1920': picture})
        cls.no_picture = Product.create({'name': 'Imgtest Plain', 'list_price': 10.0, 'categ_id': shop.id})
        cls.bar_item = Product.create({
            'name': 'Imgtest Latte', 'list_price': 10.0, 'categ_id': bar.id, 'image_1920': picture})
        cls.hidden = Product.create({
            'name': 'Imgtest Hidden', 'list_price': 10.0, 'categ_id': shop.id, 'sale_ok': False,
            'image_1920': picture})

    def test_visitor_sees_the_picture_of_a_shop_product(self):
        response = self.url_open('/club-shop/image/%d' % self.with_picture.id)
        self.assertEqual(response.status_code, 200)
        self.assertIn(response.headers['Content-Type'].split(';')[0], PNG_OR_SVG)

    def test_no_picture_is_a_404_and_the_page_falls_back_to_an_icon(self):
        self.assertEqual(self.url_open('/club-shop/image/%d' % self.no_picture.id).status_code, 404)
        page = self.url_open('/club-shop/%d' % self.no_picture.id).text
        self.assertIn('club-no-image', page)
        self.assertNotIn('/club-shop/image/%d' % self.no_picture.id, page)

    def test_only_products_for_sale_in_the_shop_are_served(self):
        self.assertEqual(self.url_open('/club-shop/image/%d' % self.bar_item.id).status_code, 404)
        self.assertEqual(self.url_open('/club-shop/image/%d' % self.hidden.id).status_code, 404)

    def test_shop_and_product_pages_use_the_picture(self):
        shop_page = self.url_open('/club-shop?q=Imgtest').text
        self.assertIn('/club-shop/image/%d' % self.with_picture.id, shop_page)
        product_page = self.url_open('/club-shop/%d' % self.with_picture.id).text
        self.assertIn('/club-shop/image/%d' % self.with_picture.id, product_page)

    def test_home_page_has_icons_and_no_emoji(self):
        page = self.url_open('/').text
        self.assertGreaterEqual(page.count('class="club-icon"'), 6)
        self.assertFalse(re.search('[\U0001F300-\U0001FAFF☀-➿]', page.split('id="wrap"')[1].split('club-footer')[0]
                                   .replace('✓', '')), "emoji found in the page body")


@tagged('post_install', '-at_install', 'club_management', 'club_website')
class TestMyClub(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        cls.gold = env.ref('club_management.plan_gold')
        cls.partner = env['res.partner'].create({'name': 'Tara Member', 'email': 'tara.member@example.com'})
        cls.partner.plan_id = cls.gold
        cls.partner.action_activate_membership()
        cls.user = env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Tara Member', 'login': 'tara.member@example.com', 'email': 'tara.member@example.com',
            'partner_id': cls.partner.id, 'password': 'tara-test-pw-1',
            'groups_id': [Command.set([env.ref('base.group_portal').id])]})

    def test_my_club_needs_a_login(self):
        response = self.url_open('/my/club', allow_redirects=False)
        self.assertEqual(response.status_code, 303)
        self.assertIn('/web/login', response.headers['Location'])

    def test_member_sees_their_membership(self):
        self.authenticate('tara.member@example.com', 'tara-test-pw-1')
        page = self.url_open('/my/club').text
        self.assertIn('Welcome, Tara', page)
        self.assertIn(self.partner.member_id, page)
        self.assertIn('Gold', page)
        self.assertIn('Active', page)

    def test_member_sees_only_their_own_bookings(self):
        env = self.env
        court = env['club.court'].create({'name': 'Mine Court', 'sport': 'tennis', 'list_price': 500.0})
        other = env['res.partner'].create({'name': 'Other Person', 'email': 'other.person@example.com'})
        from datetime import timedelta
        from odoo import fields
        start = fields.Datetime.now().replace(minute=0, second=0, microsecond=0) + timedelta(days=3)
        if start.hour < 6:
            start = start.replace(hour=8)
        mine = env['club.booking'].create({'court_id': court.id, 'partner_id': self.partner.id,
                                            'start_datetime': start, 'state': 'confirmed'})
        theirs = env['club.booking'].create({'court_id': court.id, 'partner_id': other.id,
                                              'start_datetime': start + timedelta(hours=2), 'state': 'confirmed'})
        self.authenticate('tara.member@example.com', 'tara-test-pw-1')
        page = self.url_open('/my/club').text
        self.assertIn(mine.name, page)
        self.assertNotIn(theirs.name, page)

    def test_a_non_member_account_gets_the_join_prompt(self):
        env = self.env
        partner = env['res.partner'].create({'name': 'Just Visiting', 'email': 'visiting@example.com'})
        env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Just Visiting', 'login': 'visiting@example.com', 'partner_id': partner.id,
            'password': 'visit-test-pw-1', 'groups_id': [Command.set([env.ref('base.group_portal').id])]})
        self.authenticate('visiting@example.com', 'visit-test-pw-1')
        page = self.url_open('/my/club').text
        self.assertIn('not a member yet', page)

    def test_booking_form_is_filled_in_for_a_signed_in_member(self):
        court = self.env['club.court'].create({'name': 'Prefill Court', 'sport': 'tennis', 'list_price': 500.0})
        self.authenticate('tara.member@example.com', 'tara-test-pw-1')
        from odoo.addons.club_management.models.booking import club_today
        from datetime import timedelta
        day = (club_today() + timedelta(days=2)).isoformat()
        page = self.url_open('/book?court_id=%d&date=%s&time=09:00' % (court.id, day)).text
        self.assertIn('value="Tara Member"', page)
        self.assertIn('value="%s"' % self.partner.member_id, page)

    def test_portal_home_and_menu_link_to_my_club(self):
        self.authenticate('tara.member@example.com', 'tara-test-pw-1')
        self.assertIn('/my/club', self.url_open('/my/home').text)
        self.assertIn('/my/club', self.url_open('/').text)
