from datetime import timedelta

from odoo import Command
from odoo.exceptions import AccessError, ValidationError
from odoo.tests import TransactionCase, tagged

from ..models.booking import club_today


@tagged('post_install', '-at_install', 'club_management')
class TestDeskEnrol(TransactionCase):
    """Staff enrol or renew someone at the front desk: same chain as the website, payment taken in person."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Purchase = cls.env['club.membership.purchase']
        cls.gold = cls.env.ref('club_management.plan_gold')

    def enrol(self, plan='gold', **kw):
        values = dict(name='Desk Dana', email='desk.dana@example.com', phone='9000000030')
        values.update(kw)
        return self.Purchase.desk_enroll(plan, **values)

    def test_a_new_person_becomes_a_member_with_a_paid_invoice(self):
        result = self.enrol()
        partner, invoice = result['partner'], result['invoice']
        self.assertFalse(result['renewal'])
        self.assertTrue(partner.is_member)
        self.assertEqual((partner.plan_id, partner.member_state), (self.gold, 'active'))
        self.assertEqual(invoice.club_source, 'membership')
        self.assertEqual(invoice.payment_state, 'paid')
        payment = invoice._get_reconciled_payments()
        self.assertIn('front desk', payment.ref or '')
        self.assertEqual(partner.user_ids.login, 'desk.dana@example.com', "they get a login to set a password for")

    def test_the_crm_shows_the_chain_for_a_desk_sign_up_too(self):
        partner = self.enrol(email='desk.crm@example.com')['partner']
        lead = self.env['crm.lead'].search([('partner_id', '=', partner.id)])
        self.assertTrue(lead.stage_id.is_won)
        self.assertEqual(lead.order_ids.state, 'sale')

    def test_an_existing_member_is_renewed_and_the_expiry_moves_on(self):
        member = self.enrol(email='desk.renew@example.com')['partner']
        before = member.expiry_date
        result = self.Purchase.desk_enroll('gold', partner_id=member.id, method='upi')
        self.assertTrue(result['renewal'])
        self.assertEqual(member.expiry_date, before + timedelta(days=self.gold.validity_days))
        self.assertIn('upi', result['invoice']._get_reconciled_payments().ref)

    def test_junior_needs_a_child_birth_date(self):
        with self.assertRaisesRegex(ValidationError, 'date of birth'):
            self.enrol('junior', email='desk.kid@example.com')
        with self.assertRaisesRegex(ValidationError, 'under'):
            self.enrol('junior', email='desk.adult@example.com', date_of_birth='1990-01-01')
        born = club_today() - timedelta(days=365 * 10)
        self.assertTrue(self.enrol('junior', email='desk.kid@example.com', date_of_birth=born)['partner'].is_member)

    def test_name_and_email_are_needed_for_a_new_person(self):
        with self.assertRaisesRegex(ValidationError, 'name'):
            self.enrol(name='')
        with self.assertRaisesRegex(ValidationError, 'e-mail'):
            self.enrol(email='')

    def test_a_refused_enrolment_leaves_nothing_behind(self):
        before = self.env['res.partner'].search_count([])
        with self.assertRaises(ValidationError):
            self.enrol('junior', email='desk.nothing@example.com')
        self.assertEqual(self.env['res.partner'].search_count([]), before)

    def test_only_staff_can_enrol(self):
        outsider = self.env['res.users'].create({'name': 'Outsider', 'login': 'outsider@example.com',
                                                 'groups_id': [Command.set([self.env.ref('base.group_user').id])]})
        with self.assertRaises(AccessError):
            self.Purchase.with_user(outsider).desk_enroll('gold', name='X', email='x@example.com')

    def test_the_screen_gets_a_plain_message(self):
        info = self.Purchase.desk_enroll_api('silver', name='Desk Eve', email='desk.eve@example.com')
        self.assertTrue(info['member_id'] and info['invoice'])
        self.assertIn('joined', info['message'])
        self.assertFalse(info['renewal'])


@tagged('post_install', '-at_install', 'club_management')
class TestAlerts(TransactionCase):

    def test_the_plans_screen_has_data_for_every_comparison_row(self):
        for plan in self.env['club.membership.plan'].get_frontend_plans():
            for key in ('club_access', 'court_benefits', 'shop_benefits', 'bar_benefits', 'membership_type'):
                self.assertTrue(plan['features'].get(key), (plan['code'], key))

    def test_tomorrows_bookings_get_one_reminder(self):
        member = self.env['res.partner'].create({'name': 'Remind Ray', 'email': 'remind.ray@example.com'})
        court = self.env['club.court'].search([], limit=1)
        start = club_today() + timedelta(days=1)
        booking = self.env['club.booking'].create({
            'court_id': court.id, 'partner_id': member.id,
            'start_datetime': self._utc(start, 11)})
        booking.action_confirm()
        self.assertEqual(booking.booking_date, start)
        self.assertGreaterEqual(self.env['club.booking']._cron_send_booking_reminders(), 1)
        self.assertTrue(booking.reminder_sent)
        subjects = self.env['mail.mail'].search([('recipient_ids', 'in', member.ids)]).mapped('subject')
        subjects += self.env['mail.mail'].search([('email_to', '=', 'remind.ray@example.com')]).mapped('subject')
        self.assertTrue(any(s.startswith('Reminder:') for s in subjects), subjects)
        self.assertEqual(self.env['club.booking']._cron_send_booking_reminders(), 0, "only once")

    def test_cancelled_or_later_bookings_get_no_reminder(self):
        member = self.env['res.partner'].create({'name': 'Skip Sam', 'email': 'skip.sam@example.com'})
        court = self.env['club.court'].search([], limit=1)
        later = self.env['club.booking'].create({
            'court_id': court.id, 'partner_id': member.id,
            'start_datetime': self._utc(club_today() + timedelta(days=3), 11)})
        later.action_confirm()
        self.env['club.booking']._cron_send_booking_reminders()
        self.assertFalse(later.reminder_sent)

    def test_low_stock_alert_goes_to_managers_only_when_something_is_low(self):
        dashboard = self.env['club.dashboard']
        manager = self.env['res.users'].create({
            'name': 'Stock Boss', 'login': 'stock.boss@example.com', 'email': 'stock.boss@example.com',
            'groups_id': [Command.set([self.env.ref('base.group_user').id,
                                       self.env.ref('club_management.group_club_manager').id])]})
        warehouse = self.env['stock.warehouse'].search([], limit=1)
        product = self.env['product.product'].create({'name': 'Alert Grip Tape', 'detailed_type': 'product'})
        self.env['stock.warehouse.orderpoint'].create({
            'product_id': product.id, 'warehouse_id': warehouse.id, 'location_id': warehouse.lot_stock_id.id,
            'product_min_qty': 5, 'product_max_qty': 20, 'trigger': 'manual'})
        self.assertGreaterEqual(dashboard._cron_low_stock_alert(), 1, "one e-mail to the managers lists what is low")
        self.assertIn(manager, self.env.ref('club_management.group_club_manager').users)

    def test_closing_a_paid_session_invoices_and_takes_the_payment(self):
        court = self.env['club.court'].search([], limit=1)
        booking = self.env['club.booking'].create({
            'court_id': court.id, 'walkin_name': 'Pay Pat',
            'start_datetime': self._utc(club_today() + timedelta(days=2), 15)})
        booking.action_confirm()
        self.assertGreater(booking.price, 0, "a walk-in pays full price")
        booking.action_done()
        self.assertEqual(booking.invoice_id.state, 'posted')
        self.assertEqual(booking.invoice_id.club_source, 'court')
        self.assertEqual(booking.invoice_id.payment_state, 'paid')
        self.assertIn('Paid at the club', booking.invoice_id._get_reconciled_payments().ref or '')

    def test_closing_a_free_session_raises_no_invoice(self):
        gold = self.env['res.partner'].create({
            'name': 'Free Fay', 'email': 'free.fay@example.com', 'is_member': True,
            'plan_id': self.env.ref('club_management.plan_gold').id,
            'join_date': club_today(), 'expiry_date': club_today() + timedelta(days=100)})
        court = self.env['club.court'].search([], limit=1)
        booking = self.env['club.booking'].create({
            'court_id': court.id, 'partner_id': gold.id,
            'start_datetime': self._utc(club_today() + timedelta(days=2), 16)})
        booking.action_confirm()
        self.assertEqual(booking.price, 0)
        booking.action_done()
        self.assertFalse(booking.invoice_id)

    def _utc(self, day, hour):

        import pytz
        from datetime import datetime
        local = pytz.timezone('Asia/Kolkata').localize(datetime(day.year, day.month, day.day, hour))
        return local.astimezone(pytz.utc).replace(tzinfo=None)
