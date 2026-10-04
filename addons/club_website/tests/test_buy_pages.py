from odoo import Command, http
from odoo.tests import HttpCase, tagged

CARD = {'holder': 'Web Buyer', 'number': '4242 4242 4242 4242', 'expiry': '12/40', 'cvc': '123'}


@tagged('post_install', '-at_install', 'club_management', 'club_website')
class TestBuyMembershipPages(HttpCase):

    def post(self, code, **data):
        self.authenticate(None, None)
        return self.submit(code, **data)

    def submit(self, code, **data):
        values = dict(CARD, name='Web Buyer', email='web.buyer@example.com', phone='9000000020',
                      password='web-buy-pw-1', password_confirm='web-buy-pw-1')
        values.update(data)
        values['csrf_token'] = http.Request.csrf_token(self)
        response = self.url_open('/membership/buy/%s/submit' % code, data=values, allow_redirects=False)
        new_session = response.cookies.get('session_id')
        if new_session:     # the server rotated the session (a login): keep only the new cookie
            self.opener.cookies.clear()
            self.opener.cookies.set('session_id', new_session)
        return response

    def test_plan_cards_lead_to_the_buy_page_and_keep_a_way_to_ask(self):
        page = self.url_open('/membership').text
        for code in ('gold', 'silver', 'junior'):
            self.assertIn('/membership/buy/%s' % code, page)
        self.assertIn('Questions first? Ask us', page)
        self.assertIn('/join?type=membership&amp;plan=gold', page)

    def test_the_buy_page_shows_the_plan_the_test_card_and_the_login_fields(self):
        page = self.url_open('/membership/buy/gold').text
        for expected in ('Gold membership', 'Test mode', '4242 4242 4242 4242', 'name="number"', 'name="password"',
                         'name="email"', 'Pay ₹'):
            self.assertIn(expected, page)
        self.assertNotIn('name="dob"', page, "only the Junior plan asks for a birth date")
        self.assertIn('name="dob"', self.url_open('/membership/buy/junior').text)
        self.assertEqual(self.url_open('/membership/buy/platinum').status_code, 404)

    def test_a_guest_pays_joins_is_signed_in_and_sees_their_card(self):
        response = self.post('gold')
        self.assertEqual(response.status_code, 303, response.text[:400])
        self.assertIn('/my/club?paid=joined', response.headers['Location'])
        partner = self.env['res.partner'].search([('email', '=', 'web.buyer@example.com')])
        self.assertTrue(partner.is_member)
        self.assertEqual(partner.plan_id.code, 'gold')
        page = self.url_open('/my/club?paid=joined').text
        self.assertIn('Welcome to the club', page)
        self.assertIn(partner.member_id, page)
        self.assertIn('Active', page)
        invoice = self.env['account.move'].search([('partner_id', '=', partner.id), ('club_source', '=', 'membership')])
        self.assertEqual(invoice.payment_state, 'paid')

    def test_a_declined_card_shows_the_message_and_makes_no_member(self):
        response = self.post('silver', number='4000 0000 0000 0002')
        self.assertEqual(response.status_code, 400)
        self.assertIn('declined', response.text)
        self.assertIn('value="Web Buyer"', response.text, "what they typed is kept")
        self.assertFalse(self.env['res.partner'].search([('email', '=', 'web.buyer@example.com')]))

    def test_an_email_the_club_knows_is_refused_with_a_sign_in_hint(self):
        self.env['res.partner'].create({'name': 'Known', 'email': 'web.known@example.com'})
        response = self.post('gold', email='web.known@example.com')
        self.assertEqual(response.status_code, 400)
        self.assertIn('already registered', response.text)

    def test_junior_asks_for_a_birth_date(self):
        response = self.post('junior')
        self.assertEqual(response.status_code, 400)
        self.assertIn('date of birth', response.text)
        ok = self.post('junior', dob='2014-05-05', email='web.junior@example.com')
        self.assertEqual(ok.status_code, 303, ok.text[:300])

    def test_the_honeypot_buys_nothing(self):
        response = self.post('gold', website_url='http://spam.example', email='web.bot@example.com')
        self.assertEqual(response.status_code, 303)
        self.assertFalse(self.env['res.partner'].search([('email', '=', 'web.bot@example.com')]))

    def test_a_signed_in_member_renews_without_filling_in_their_details(self):
        env = self.env
        partner = env['res.partner'].create({'name': 'Renew Rae', 'email': 'renew.rae@example.com'})
        partner.plan_id = env.ref('club_management.plan_silver')
        partner.action_activate_membership()
        env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Renew Rae', 'login': 'renew.rae@example.com', 'partner_id': partner.id,
            'password': 'renew-pw-1234', 'groups_id': [Command.set([env.ref('base.group_portal').id])]})
        expiry = partner.expiry_date
        self.authenticate('renew.rae@example.com', 'renew-pw-1234')
        page = self.url_open('/membership/buy/gold').text
        self.assertIn('Renewing for', page)
        self.assertNotIn('name="password"', page, "a signed-in customer is not asked for a password")
        response = self.submit('gold', name='', email='', password='', password_confirm='')
        self.assertEqual(response.status_code, 303, response.text[:300])
        self.assertIn('paid=renewed', response.headers['Location'])
        self.assertGreater(partner.expiry_date, expiry)
        self.assertEqual(partner.plan_id.code, 'gold')
        self.assertIn('membership is renewed', self.url_open('/my/club?paid=renewed').text)

    def test_my_club_renew_button_goes_to_the_payment_page(self):
        env = self.env
        partner = env['res.partner'].create({
            'name': 'Lapsed Lee', 'email': 'lapsed.lee@example.com', 'is_member': True,
            'plan_id': env.ref('club_management.plan_gold').id,
            'join_date': '2020-01-01', 'expiry_date': '2020-12-31'})
        env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Lapsed Lee', 'login': 'lapsed.lee@example.com', 'partner_id': partner.id,
            'password': 'lapsed-pw-1234', 'groups_id': [Command.set([env.ref('base.group_portal').id])]})
        self.authenticate('lapsed.lee@example.com', 'lapsed-pw-1234')
        self.assertIn('/membership/buy/gold', self.url_open('/my/club').text)
