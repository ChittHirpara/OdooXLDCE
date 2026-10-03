from datetime import date, timedelta

from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.addons.club_management.models.booking import club_today
from odoo.exceptions import UserError
from odoo.tests import tagged

from .common import MON, TUE, club_dt


@tagged('post_install', '-at_install', 'club_management')
class TestPricing(AccountTestInvoicingCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env.user.groups_id |= cls.env.ref('club_management.group_club_manager')
        today = club_today()

        cls.court = cls.env['club.court'].create({
            'name': 'Court 1', 'sport': 'tennis', 'list_price': 800.0})
        Partner = cls.env['res.partner']

        def member(name, plan_xmlid, **extra):
            partner = Partner.create(dict(
                name=name, plan_id=cls.env.ref('club_management.' + plan_xmlid).id, **extra))
            partner.action_activate_membership()
            return partner

        cls.gold = member('Gold Member', 'plan_gold')
        cls.silver = member('Silver Member', 'plan_silver')
        cls.junior = member('Junior Member', 'plan_junior',
                            date_of_birth=today - timedelta(days=365 * 12))
        # Membership that lapsed the day before the booking date used in the tests.
        cls.lapsed = Partner.create({
            'name': 'Lapsed Member', 'is_member': True,
            'plan_id': cls.env.ref('club_management.plan_gold').id,
            'expiry_date': date(2026, 10, MON - 1)})
        cls.non_member = Partner.create({'name': 'Just A Customer'})

    def _book(self, partner=None, hour=10, day=MON, **kw):
        vals = {'court_id': self.court.id, 'start_datetime': club_dt(day, hour)}
        if partner:
            vals['partner_id'] = partner.id
        else:
            vals.setdefault('walkin_name', 'Walk-in Joe')
        vals.update(kw)
        return self.env['club.booking'].create(vals)

    # --- price by tier ------------------------------------------------------
    def test_gold_is_free(self):
        self.assertEqual(self._book(self.gold).price, 0.0)

    def test_silver_pays_standard_rate(self):
        self.assertEqual(self._book(self.silver).price, 500.0)

    def test_junior_pays_discounted_rate(self):
        self.assertEqual(self._book(self.junior).price, 250.0)

    def test_walkin_pays_full_price(self):
        self.assertEqual(self._book().price, 800.0)

    def test_non_member_contact_pays_full_price(self):
        self.assertEqual(self._book(self.non_member).price, 800.0)

    def test_lapsed_member_pays_full_price(self):
        self.assertEqual(self._book(self.lapsed).price, 800.0)

    def test_member_price_applies_until_expiry_date_inclusive(self):
        self.silver.expiry_date = date(2026, 10, MON)
        self.assertEqual(self._book(self.silver).price, 500.0)
        self.assertEqual(self._book(self.silver, hour=12, day=TUE).price, 800.0)

    def test_price_follows_plan_rate_change(self):
        booking = self._book(self.silver)
        self.env.ref('club_management.plan_silver').court_rate = 450.0
        self.assertEqual(booking.price, 450.0)

    def test_price_follows_court_list_price_for_walkins(self):
        booking = self._book()
        self.court.list_price = 900.0
        self.assertEqual(booking.price, 900.0)

    # --- invoicing ----------------------------------------------------------
    def test_invoice_for_member_booking(self):
        booking = self._book(self.silver)
        booking.action_create_invoice()
        invoice = booking.invoice_id
        self.assertEqual(invoice.move_type, 'out_invoice')
        self.assertEqual(invoice.state, 'draft')
        self.assertEqual(invoice.partner_id, self.silver)
        self.assertEqual(invoice.amount_untaxed, 500.0)
        self.assertEqual(invoice.invoice_origin, booking.name)
        self.assertEqual(invoice.invoice_line_ids.product_id,
                         self.env.ref('club_management.product_court_booking'))

    def test_invoice_for_walkin_uses_walkin_customer(self):
        booking = self._book()
        booking.action_create_invoice()
        self.assertEqual(booking.invoice_id.partner_id, self.env.ref('club_management.partner_walkin'))
        self.assertEqual(booking.invoice_id.amount_untaxed, 800.0)
        self.assertIn('Walk-in Joe', booking.invoice_id.invoice_line_ids.name)

    def test_gold_booking_invoice_is_zero(self):
        booking = self._book(self.gold)
        booking.action_create_invoice()
        self.assertEqual(booking.invoice_id.amount_total, 0.0)

    def test_invoice_can_be_posted(self):
        booking = self._book(self.silver)
        booking.action_create_invoice()
        booking.invoice_id.action_post()
        self.assertEqual(booking.invoice_id.state, 'posted')

    def test_cannot_invoice_twice(self):
        booking = self._book(self.silver)
        booking.action_create_invoice()
        with self.assertRaises(UserError):
            booking.action_create_invoice()

    def test_cannot_invoice_cancelled_booking(self):
        booking = self._book(self.silver)
        booking.action_cancel()
        with self.assertRaises(UserError):
            booking.action_create_invoice()

    def test_cannot_cancel_booking_with_posted_invoice(self):
        booking = self._book(self.silver)
        booking.action_create_invoice()
        booking.invoice_id.action_post()
        with self.assertRaises(UserError):
            booking.action_cancel()

    def test_invoiced_booking_can_move_if_price_is_unchanged(self):
        booking = self._book(self.silver)
        booking.action_create_invoice()
        booking.action_reschedule(club_dt(TUE, 14))
        self.assertEqual(booking.start_datetime, club_dt(TUE, 14))

    def test_invoiced_booking_cannot_move_if_price_changes(self):
        other = self.env['club.court'].create({'name': 'Court 2', 'sport': 'tennis', 'list_price': 900.0})
        booking = self._book()                       # walk-in at 800
        booking.action_create_invoice()
        with self.assertRaises(UserError):
            booking.action_reschedule(club_dt(MON, 10), other)   # would cost 900
        self.assertEqual(booking.court_id, self.court)           # rolled back

    def test_uninvoiced_booking_can_move_and_reprice(self):
        other = self.env['club.court'].create({'name': 'Court 3', 'sport': 'tennis', 'list_price': 900.0})
        booking = self._book()
        booking.action_reschedule(club_dt(MON, 10), other)
        self.assertEqual(booking.price, 900.0)

    def test_can_cancel_booking_with_draft_invoice(self):
        booking = self._book(self.silver)
        booking.action_create_invoice()
        booking.action_cancel()
        self.assertEqual(booking.state, 'cancelled')
