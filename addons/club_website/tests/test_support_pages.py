from odoo import Command, http
from odoo.tests import HttpCase, tagged


@tagged('post_install', '-at_install', 'club_management', 'club_website')
class TestFeedbackAndSupportPages(HttpCase):

    def post(self, path, **data):
        self.authenticate(None, None)
        data['csrf_token'] = http.Request.csrf_token(self)
        return self.url_open(path, data=data, allow_redirects=False)

    def test_pages_render_and_are_linked_from_the_footer(self):
        self.assertIn('name="rating"', self.url_open('/feedback').text)
        self.assertIn('name="category"', self.url_open('/support').text)
        home = self.url_open('/').text
        self.assertIn('href="/feedback"', home)
        self.assertIn('href="/support"', home)

    def test_a_rating_is_saved_and_thanked(self):
        before = self.env['club.feedback'].search_count([])
        response = self.post('/feedback/submit', area='bar', rating='5', comment='Lovely coffee')
        self.assertEqual(response.status_code, 200)
        self.assertIn('Thank you', response.text)
        feedback = self.env['club.feedback'].search([], limit=1)
        self.assertEqual((feedback.area, feedback.rating, feedback.comment), ('bar', 5, 'Lovely coffee'))
        self.assertEqual(self.env['club.feedback'].search_count([]), before + 1)

    def test_a_low_rating_points_to_support(self):
        response = self.post('/feedback/submit', area='court', rating='1')
        self.assertIn('/support', response.text)

    def test_a_missing_rating_is_refused_with_the_form_kept(self):
        before = self.env['club.feedback'].search_count([])
        response = self.post('/feedback/submit', area='court', comment='Forgot the stars')
        self.assertEqual(response.status_code, 400)
        self.assertIn('rating from 1 to 5', response.text)
        self.assertIn('Forgot the stars', response.text)
        self.assertEqual(self.env['club.feedback'].search_count([]), before)

    def test_a_support_request_creates_a_ticket_and_a_private_status_page(self):
        response = self.post('/support/submit', name='Sam', email='sam@example.com', category='refund',
                             subject='Double charged', description='Paid twice for court 2.')
        self.assertEqual(response.status_code, 303)
        ticket = self.env['club.ticket'].search([('contact_email', '=', 'sam@example.com')])
        self.assertEqual(len(ticket), 1)
        self.assertEqual(response.headers['Location'].split('?')[0].rsplit('/', 1)[1], ticket.access_token)
        page = self.url_open('/support/ticket/%s' % ticket.access_token).text
        self.assertIn(ticket.name, page)
        self.assertIn('Double charged', page)
        self.assertNotIn('Paid twice for court 2.', page, "the description stays internal")
        self.assertEqual(self.url_open('/support/ticket/not-a-real-token-0123456789').status_code, 404)

    def test_resolution_text_appears_once_resolved(self):
        self.post('/support/submit', name='Rae', email='rae@example.com', category='order', subject='Wrong grip')
        ticket = self.env['club.ticket'].search([('contact_email', '=', 'rae@example.com')])
        ticket.resolution = 'We swapped it for the right one.'
        self.assertNotIn('swapped it', self.url_open('/support/ticket/%s' % ticket.access_token).text)
        ticket.action_resolve()
        page = self.url_open('/support/ticket/%s' % ticket.access_token).text
        self.assertIn('swapped it', page)
        self.assertIn('Resolved', page)

    def test_bad_support_input_shows_the_message_and_makes_no_ticket(self):
        before = self.env['club.ticket'].search_count([])
        response = self.post('/support/submit', name='', email='x@example.com', category='complaint', subject='Hi')
        self.assertEqual(response.status_code, 400)
        self.assertIn('your name', response.text)
        self.assertEqual(self.env['club.ticket'].search_count([]), before)

    def test_honeypots_create_nothing(self):
        tickets = self.env['club.ticket'].search_count([])
        ratings = self.env['club.feedback'].search_count([])
        self.post('/support/submit', name='Bot', email='bot@example.com', category='other', subject='Spam',
                  website_url='http://spam.example')
        self.post('/feedback/submit', area='club', rating='5', website_url='http://spam.example')
        self.assertEqual(self.env['club.ticket'].search_count([]), tickets)
        self.assertEqual(self.env['club.feedback'].search_count([]), ratings)

    def test_booking_page_links_to_rating_and_reporting_a_problem(self):
        court = self.env['club.court'].create({'name': 'Link Court', 'sport': 'tennis', 'list_price': 400.0})
        from odoo.addons.club_management.models.booking import club_today
        from datetime import timedelta
        day = (club_today() + timedelta(days=2)).isoformat()
        self.authenticate(None, None)
        data = {'court_id': court.id, 'date': day, 'time': '09:00', 'name': 'Link Guest',
                'phone': '9000000001', 'email': 'link.guest@example.com', 'players': '1',
                'csrf_token': http.Request.csrf_token(self)}
        response = self.url_open('/book/submit', data=data)
        self.assertEqual(response.status_code, 200)
        booking = self.env['club.booking'].search([('guest_email', '=', 'link.guest@example.com')])
        self.assertIn('/feedback?area=court&amp;booking=%s' % booking.access_token, response.text)
        self.assertIn('/support?category=booking&amp;booking=%s' % booking.access_token, response.text)
        # the link carries the booking into the ticket
        self.post('/support/submit', name='Link Guest', email='link.guest@example.com', category='booking',
                  subject='Court was wet', booking=booking.access_token)
        self.assertEqual(self.env['club.ticket'].search([('subject', '=', 'Court was wet')]).booking_id, booking)

    def test_a_signed_in_member_gets_the_forms_filled_in(self):
        gold = self.env.ref('club_management.plan_gold')
        partner = self.env['res.partner'].create({'name': 'Filled Fran', 'email': 'fran@example.com'})
        partner.plan_id = gold
        partner.action_activate_membership()
        self.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Filled Fran', 'login': 'fran@example.com', 'partner_id': partner.id,
            'password': 'fran-test-pw-1', 'groups_id': [Command.set([self.env.ref('base.group_portal').id])]})
        self.authenticate('fran@example.com', 'fran-test-pw-1')
        self.assertIn('value="Filled Fran"', self.url_open('/support').text)
        self.assertIn('value="fran@example.com"', self.url_open('/support').text)
        data = {'area': 'shop', 'rating': '4', 'csrf_token': http.Request.csrf_token(self)}
        self.url_open('/feedback/submit', data=data)
        self.assertEqual(self.env['club.feedback'].search([], limit=1).partner_id, partner)
