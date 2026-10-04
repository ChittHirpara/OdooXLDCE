from odoo.tests import HttpCase, TransactionCase, tagged

from ..models.demo_extras import FEEDBACK, NEW_MEMBERS, NEW_PRODUCTS, ORDERS, TICKETS


@tagged('post_install', '-at_install', 'club_management')
class TestDemoExtras(TransactionCase):
    """The extra demo data (about 50 records) that makes the site look lived in."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env['club.demo'].load_extras()

    def test_it_adds_about_fifty_records(self):
        total = len(NEW_MEMBERS) + len(NEW_PRODUCTS) + len(ORDERS) + len(FEEDBACK) + len(TICKETS)
        self.assertGreaterEqual(total, 40)
        self.assertLessEqual(total, 55)

    def test_members_are_spread_over_the_last_months(self):
        Partner = self.env['res.partner']
        joined = []
        for name, code, months, _age in NEW_MEMBERS:
            partner = Partner.search([('email', '=', '%s@example.com' % name.lower().replace(' ', '.'))])
            self.assertEqual(len(partner), 1, name)
            self.assertTrue(partner.is_member)
            self.assertEqual(partner.plan_id.code, code)
            self.assertEqual(partner.member_state, 'active')
            joined.append(partner.join_date)
        self.assertGreater(max(joined), min(joined), "joining dates differ, so the growth chart has a shape")

    def test_orders_exist_and_are_dated_in_the_past(self):
        orders = self.env['club.order'].search([('customer_name', 'in', ['Kavya Rao', 'Tanvi Shah', 'Imran Khan'])])
        self.assertTrue(orders)
        self.assertEqual({o.channel for o in orders}, {'shop', 'bar'})
        self.assertTrue(any(o.create_date.date() < o.write_date.date() for o in orders),
                        "orders were back-dated, not all created today")

    def test_products_have_pictures_and_sell_in_the_right_place(self):
        for name, channel, *_rest in NEW_PRODUCTS:
            product = self.env['product.product'].search([('name', '=', name)])
            self.assertEqual(len(product), 1, name)
            self.assertTrue(product.image_1920, name)
            self.assertIn(channel.capitalize(), product.categ_id.complete_name.replace('Club ', '').replace('&', ''))

    def test_feedback_tickets_and_public_comments(self):
        Feedback = self.env['club.feedback']
        self.assertGreaterEqual(Feedback.search_count([('public', '=', True)]), 8)
        self.assertTrue(Feedback.search([('rating', '<=', 2), ('reviewed', '=', False)]), "low ratings to act on")
        states = set(self.env['club.ticket'].search([('subject', 'in', [t[1] for t in TICKETS])]).mapped('state'))
        self.assertEqual(states, {'new', 'progress', 'resolved', 'closed'})

    def test_running_it_again_adds_nothing(self):
        counts = {m: self.env[m].search_count([]) for m in ('club.feedback', 'club.ticket', 'club.order', 'res.partner')}
        self.assertFalse(self.env['club.demo'].load_extras())
        self.env['ir.config_parameter'].sudo().set_param('club_management.demo_extras_loaded', '')
        self.env['club.demo'].load_extras()      # even with the flag cleared, nothing is duplicated
        self.assertEqual(counts, {m: self.env[m].search_count([]) for m in counts})


@tagged('post_install', '-at_install', 'club_management', 'club_website')
class TestHomeShowsTheData(HttpCase):

    def test_home_shows_numbers_and_what_members_say(self):
        self.env['club.demo'].load_extras()
        page = self.url_open('/').text
        self.assertIn('Active members', page)
        self.assertIn('Court sessions booked', page)
        self.assertIn('What members say', page)
        self.assertIn('One membership for the courts, the shop and the bar', page)
        self.assertIn('Siddharth J.', page, "only first name and initial are shown")
        self.assertNotIn('Siddharth Jain', page.split('What members say')[1])

    def test_comments_that_are_not_public_or_low_never_show(self):
        self.env['club.demo'].load_extras()
        page = self.url_open('/').text
        self.assertNotIn('Floodlights on Court 3 were flickering', page)
        self.assertNotIn('changing room could be cleaner', page)

    def test_the_shop_lists_the_new_products(self):
        self.env['club.demo'].load_extras()
        page = self.url_open('/club-shop').text
        self.assertIn('Sports Water Bottle', page)
        self.assertIn('Junior Tennis Racket', page)
