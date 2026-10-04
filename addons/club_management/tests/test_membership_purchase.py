from datetime import timedelta

from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged

from ..models.booking import club_today

GOOD_CARD = {'holder': 'Test Buyer', 'number': '4242 4242 4242 4242', 'expiry': '12/40', 'cvc': '123'}


@tagged('post_install', '-at_install', 'club_management')
class TestCard(TransactionCase):

    def check(self, **change):
        card = dict(GOOD_CARD, **change)
        return self.env['club.membership.purchase'].check_card(
            card['holder'], card['number'], card['expiry'], card['cvc'])

    def test_a_valid_test_card_returns_only_the_last_four_digits(self):
        self.assertEqual(self.check(), '4242')
        self.assertEqual(self.check(number='5555555555554444', expiry='1/2040'), '4444')

    def test_the_declined_test_card_is_declined(self):
        with self.assertRaisesRegex(ValidationError, 'declined'):
            self.check(number='4000 0000 0000 0002')

    def test_bad_numbers_dates_and_codes_are_refused_with_a_reason(self):
        for change, message in (
                (dict(number='4242 4242 4242 4241'), 'not valid'), (dict(number='1234'), 'not valid'),
                (dict(number='abcd'), 'not valid'), (dict(expiry='13/40'), 'MM/YY'), (dict(expiry='soon'), 'MM/YY'),
                (dict(expiry='01/20'), 'expired'), (dict(cvc='12'), 'security code'), (dict(cvc='abc'), 'security code'),
                (dict(holder=' '), 'name on the card')):
            with self.assertRaisesRegex(ValidationError, message, msg=str(change)):
                self.check(**change)

    def test_a_card_that_expires_this_month_is_still_good_until_month_end(self):
        today = club_today()
        self.assertEqual(self.check(expiry='%02d/%d' % (today.month, today.year)), '4242')


@tagged('post_install', '-at_install', 'club_management')
class TestPurchase(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Buy = cls.env['club.membership.purchase']
        cls.gold = cls.env.ref('club_management.plan_gold')
        cls.junior = cls.env.ref('club_management.plan_junior')

    def buy(self, plan='gold', email='buyer.one@example.com', card=None, **kw):
        values = dict(name='Buyer One', email=email, phone='9000000010',
                      password='buy-test-pw-1', password_confirm='buy-test-pw-1')
        values.update(kw)
        return self.Buy.purchase(plan, card or GOOD_CARD, **values)

    def counts(self):
        return {m: self.env[m].search_count([]) for m in
                ('res.partner', 'res.users', 'crm.lead', 'sale.order', 'account.move', 'account.payment')}

    # -- a new customer ---------------------------------------------------
    def test_a_new_customer_pays_and_becomes_an_active_member_with_a_login(self):
        result = self.buy()
        partner = result['partner']
        self.assertTrue(result['created'] and not result['renewal'])
        self.assertTrue(partner.is_member)
        self.assertEqual((partner.plan_id, partner.member_state), (self.gold, 'active'))
        self.assertTrue(partner.member_id)
        self.assertEqual(partner.expiry_date, club_today() + timedelta(days=self.gold.validity_days))
        self.assertEqual(partner.user_ids.login, 'buyer.one@example.com')
        self.assertTrue(partner.user_ids.share)
        self.assertEqual(len(partner.user_ids), 1, "the chosen password is kept: no second login on activation")

    def test_the_invoice_is_posted_tagged_and_paid(self):
        invoice = self.buy()['invoice']
        self.assertEqual(invoice.state, 'posted')
        self.assertEqual(invoice.club_source, 'membership')
        self.assertEqual(invoice.amount_total, self.gold.price)
        self.assertEqual(invoice.payment_state, 'paid')
        payment = self.env['account.payment'].search([('reconciled_invoice_ids', 'in', invoice.id)])
        self.assertIn('****4242', payment.ref or '')
        self.assertNotIn('4242 4242', payment.ref or '', "only the last four digits are kept")

    def test_the_crm_shows_the_whole_chain(self):
        partner = self.buy()['partner']
        lead = self.env['crm.lead'].search([('partner_id', '=', partner.id)])
        self.assertEqual(len(lead), 1)
        self.assertTrue(lead.stage_id.is_won)
        self.assertTrue(lead.member_activated)
        self.assertEqual(lead.order_ids.state, 'sale')

    def test_the_customer_gets_a_welcome_and_a_receipt(self):
        partner = self.buy(email='mail.buyer2@example.com')['partner']
        mails = self.env['mail.mail'].search([('recipient_ids', 'in', partner.id)]).mapped('subject')
        mails += self.env['mail.mail'].search([('email_to', '=', 'mail.buyer2@example.com')]).mapped('subject')
        self.assertTrue(any('Welcome to The Champions Club' in s for s in mails), mails)
        self.assertTrue(any('Payment received' in s for s in mails), mails)

    # -- nothing happens unless everything can happen ----------------------
    def test_a_declined_card_leaves_nothing_behind(self):
        before = self.counts()
        with self.assertRaisesRegex(ValidationError, 'declined'):
            self.buy(card=dict(GOOD_CARD, number='4000000000000002'))
        self.assertEqual(self.counts(), before)

    def test_a_known_email_is_refused_before_any_money_moves(self):
        member = self.env['res.partner'].create({'name': 'Known Kim', 'email': 'known.kim@example.com'})
        before = self.counts()
        with self.assertRaisesRegex(ValidationError, 'already registered'):
            self.buy(email='Known.Kim@example.com')
        self.assertEqual(self.counts(), before)
        self.assertFalse(member.user_ids)

    def test_weak_or_mismatched_passwords_are_refused(self):
        for change, message in ((dict(password='short', password_confirm='short'), 'at least 8'),
                                (dict(password_confirm='different-pw-9'), 'do not match')):
            with self.assertRaisesRegex(ValidationError, message):
                self.buy(**change)

    def test_junior_needs_a_birth_date_and_an_age_under_18(self):
        before = self.counts()
        with self.assertRaisesRegex(ValidationError, 'date of birth'):
            self.buy('junior')
        with self.assertRaisesRegex(ValidationError, 'under 18'):
            self.buy('junior', date_of_birth=club_today() - timedelta(days=365 * 30))
        self.assertEqual(self.counts(), before, "a refused junior purchase leaves no enquiry, order or login")
        result = self.buy('junior', date_of_birth=club_today() - timedelta(days=365 * 12))
        self.assertEqual(result['partner'].plan_id, self.junior)
        self.assertTrue(result['partner'].is_junior)

    def test_unknown_plan_and_missing_name_are_refused(self):
        with self.assertRaisesRegex(ValidationError, 'Unknown membership plan'):
            self.buy('platinum')
        with self.assertRaisesRegex(ValidationError, 'your name'):
            self.buy(name=' ')

    # -- renewing -----------------------------------------------------------
    def member(self, email, days_left):
        partner = self.env['res.partner'].create({'name': 'Renewer', 'email': email})
        partner.plan_id = self.env.ref('club_management.plan_silver')
        partner.action_activate_membership()
        partner.expiry_date = club_today() + timedelta(days=days_left)
        return partner

    def test_renewing_early_extends_from_the_end_date(self):
        partner = self.member('renew.early@example.com', 10)
        result = self.Buy.purchase('gold', GOOD_CARD, partner=partner)
        self.assertTrue(result['renewal'] and not result['created'])
        self.assertEqual(partner.plan_id, self.gold)
        self.assertEqual(partner.expiry_date, club_today() + timedelta(days=10 + self.gold.validity_days))
        self.assertEqual(result['invoice'].payment_state, 'paid')
        self.assertEqual(result['invoice'].club_source, 'membership')
        self.assertFalse(partner.user_ids, "renewing does not create a login")

    def test_renewing_a_lapsed_membership_starts_from_today(self):
        partner = self.member('renew.late@example.com', -30)
        self.assertEqual(partner.member_state, 'expired')
        self.Buy.purchase('silver', GOOD_CARD, partner=partner)
        self.assertEqual(partner.member_state, 'active')
        self.assertEqual(partner.expiry_date, club_today() + timedelta(days=self.env.ref('club_management.plan_silver').validity_days))

    def test_a_signed_in_customer_who_is_not_a_member_joins_without_a_second_login(self):
        partner = self.env['res.partner'].create({'name': 'Portal Pat', 'email': 'portal.pat@example.com'})
        user = self.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Portal Pat', 'login': 'portal.pat@example.com', 'partner_id': partner.id,
            'groups_id': [(6, 0, [self.env.ref('base.group_portal').id])]})
        result = self.Buy.purchase('gold', GOOD_CARD, partner=partner)
        self.assertTrue(partner.is_member and not result['created'] and not result['renewal'])
        self.assertEqual(partner.user_ids, user)

    def test_renewal_with_a_declined_card_changes_nothing(self):
        partner = self.member('renew.declined@example.com', 5)
        expiry, before = partner.expiry_date, self.counts()
        with self.assertRaisesRegex(ValidationError, 'declined'):
            self.Buy.purchase('gold', dict(GOOD_CARD, number='4000000000000002'), partner=partner)
        self.assertEqual((partner.expiry_date, partner.plan_id.code, self.counts()), (expiry, 'silver', before))
