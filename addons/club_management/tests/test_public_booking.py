from datetime import timedelta

from odoo import fields
from odoo.addons.club_management.models.booking import WEBSITE_BOOKING_DAYS, club_today
from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install', 'club_management')
class TestPublicBooking(TransactionCase):
    """A visitor books a court online: instant, no staff, the same rules as at the front desk."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        cls.Booking = env['club.booking']
        cls.court = env['club.court'].create({
            'name': 'Online Court', 'sport': 'tennis', 'list_price': 800.0, 'social_capacity': 4})
        cls.court2 = env['club.court'].create({'name': 'Online Court 2', 'sport': 'padel', 'list_price': 900.0})
        cls.gold = env['res.partner'].create({
            'name': 'Gold Online', 'email': 'gold.online@example.com',
            'plan_id': env.ref('club_management.plan_gold').id})
        cls.gold.action_activate_membership()
        cls.lapsed = env['res.partner'].create({
            'name': 'Lapsed Online', 'email': 'lapsed.online@example.com', 'is_member': True,
            'plan_id': env.ref('club_management.plan_gold').id, 'expiry_date': club_today() - timedelta(days=3)})

    # --- helpers -----------------------------------------------------------
    def day(self, offset):
        """A date `offset` days ahead that is not a Friday (Fridays are social play)."""
        day = club_today() + timedelta(days=offset)
        while day.weekday() == 4:
            day += timedelta(days=1)
        return day.isoformat()

    def friday(self):
        day = club_today() + timedelta(days=1)
        while day.weekday() != 4:
            day += timedelta(days=1)
        return day.isoformat()

    def book(self, time='10:00', offset=2, court=None, name='Guest Person', phone='+91 90000 11111',
             email='guest.person@example.com', **kw):
        return self.Booking.create_public_booking(
            (court or self.court).id, self.day(offset), time, name, phone=phone, email=email, **kw)

    # --- a guest books -----------------------------------------------------
    def test_guest_booking_is_instantly_confirmed_at_the_list_price(self):
        booking = self.book()
        self.assertEqual((booking.state, booking.tier, booking.price), ('confirmed', 'guest', 800.0))
        self.assertEqual((booking.booking_source, booking.walkin_name), ('website', 'Guest Person'))
        self.assertFalse(booking.partner_id)
        self.assertTrue(booking.name.startswith('BK/'))
        self.assertGreaterEqual(len(booking.access_token), 32)

    def test_guest_contact_is_kept_and_the_phone_is_normalised(self):
        booking = self.book(phone='+91 (900) 00-11111', email='  Guest.Person@Example.COM ')
        self.assertEqual(booking.guest_phone, '+919000011111')
        self.assertEqual(booking.guest_email, 'guest.person@example.com')

    def test_each_booking_gets_its_own_secret_link(self):
        first, second = self.book(), self.book('12:00')
        self.assertNotEqual(first.access_token, second.access_token)

    def test_a_guest_must_give_a_name_and_a_way_to_be_reached(self):
        with self.assertRaises(ValidationError):
            self.book(name='  ')
        with self.assertRaises(ValidationError):
            self.book(phone='', email='')

    def test_phone_only_or_email_only_is_enough(self):
        self.assertTrue(self.book(phone='', email='only.email@example.com'))
        self.assertTrue(self.book('12:00', phone='+91 98000 22222', email=''))

    # --- the booking window ------------------------------------------------
    def test_past_times_are_refused(self):
        yesterday = (club_today() - timedelta(days=1)).isoformat()
        with self.assertRaisesRegex(ValidationError, 'already passed'):
            self.Booking.create_public_booking(self.court.id, yesterday, '10:00', 'Late', phone='9000011111')

    def test_only_two_weeks_ahead(self):
        last = (club_today() + timedelta(days=WEBSITE_BOOKING_DAYS)).isoformat()
        beyond = (club_today() + timedelta(days=WEBSITE_BOOKING_DAYS + 1)).isoformat()
        with self.assertRaisesRegex(ValidationError, 'days ahead'):
            self.Booking.create_public_booking(self.court.id, beyond, '10:00', 'Early', phone='9000011111')
        self.Booking.create_public_booking(self.court.id, last, '10:00', 'Just In', phone='9000011111')

    def test_bad_input_is_refused(self):
        for date, time in (('not-a-date', '10:00'), (self.day(2), 'ten'), (self.day(2), '')):
            with self.assertRaises(ValidationError):
                self.Booking.create_public_booking(self.court.id, date, time, 'X', phone='9000011111')
        with self.assertRaisesRegex(ValidationError, 'does not exist'):
            self.Booking.create_public_booking(999999999, self.day(2), '10:00', 'X', phone='9000011111')

    # --- the same booking rules as the front desk --------------------------
    def test_a_taken_slot_is_refused_and_nothing_is_saved(self):
        self.book('10:00')
        count = self.Booking.search_count([])
        for time in ('10:00', '10:30', '09:30'):
            with self.assertRaisesRegex(ValidationError, 'already booked'):
                self.book(time, name='Other', phone='+91 91111 00000', email='other@example.com')
        self.assertEqual(self.Booking.search_count([]), count)

    def test_adjacent_slots_and_other_courts_are_fine(self):
        self.book('10:00')
        self.book('11:00', name='Other', phone='+91 91111 00000', email='other@example.com')
        self.book('10:00', court=self.court2, name='Third', phone='+91 92222 00000', email='third@example.com')

    def test_off_grid_and_out_of_hours_times_are_refused(self):
        with self.assertRaisesRegex(ValidationError, 'hour or half hour'):
            self.book('10:15')
        with self.assertRaises(ValidationError):
            self.book('05:30')
        with self.assertRaises(ValidationError):
            self.book('21:30')

    def test_a_cancelled_slot_can_be_booked_again(self):
        booking = self.book('10:00')
        booking.cancel_by_visitor()
        self.book('10:00', name='Next', phone='+91 93333 00000', email='next@example.com')

    def test_friday_social_play_shares_the_court_up_to_capacity(self):
        friday = self.friday()
        book = lambda name, phone, players: self.Booking.create_public_booking(  # noqa: E731
            self.court.id, friday, '18:00', name, phone=phone, players=players)
        first = book('Group A', '9000000001', 3)
        self.assertTrue(first.is_social)
        book('Solo B', '9000000002', 1)                          # 4 of 4
        with self.assertRaisesRegex(ValidationError, 'full'):
            book('Late C', '9000000003', 1)

    def test_players_are_clamped_to_something_sensible(self):
        self.assertEqual(self.book(players=99, phone='9000000021', email='p1@example.com').players, 4)   # court capacity
        self.assertEqual(self.book('12:00', players=0, phone='9000000022', email='p2@example.com').players, 1)
        self.assertEqual(self.book('14:00', players='x', phone='9000000023', email='p3@example.com').players, 1)

    # --- guests get the same two-a-day limit -------------------------------
    def test_a_guest_cannot_book_more_than_two_a_day_by_phone(self):
        self.book('08:00', name='One', email='a1@example.com')
        self.book('10:00', name='Two', email='a2@example.com')
        with self.assertRaisesRegex(ValidationError, 'maximum per day'):
            self.book('12:00', name='Three', email='a3@example.com')       # same phone, new name and e-mail

    def test_a_guest_cannot_get_round_the_limit_by_changing_the_phone(self):
        self.book('08:00', phone='9000000011')
        self.book('10:00', phone='9000000012')
        with self.assertRaisesRegex(ValidationError, 'maximum per day'):
            self.book('12:00', phone='9000000013')                          # same e-mail

    def test_different_guests_and_different_days_are_independent(self):
        self.book('08:00')
        self.book('10:00')
        self.book('12:00', name='Different', phone='+91 94444 00000', email='different@example.com')
        self.book('12:00', offset=3)

    def test_cancelling_gives_the_guest_the_slot_back(self):
        first = self.book('08:00')
        self.book('10:00')
        first.cancel_by_visitor()
        self.book('12:00')

    # --- members book with their ID and e-mail -----------------------------
    def test_a_verified_member_books_at_their_tier_price(self):
        booking = self.Booking.create_public_booking(
            self.court.id, self.day(2), '10:00', 'ignored', member_ref=self.gold.member_id,
            member_email='GOLD.online@example.com')
        self.assertEqual((booking.partner_id, booking.tier, booking.price), (self.gold, 'gold', 0.0))
        self.assertFalse(booking.walkin_name)
        self.assertEqual(booking.booking_source, 'website')

    def test_member_id_is_not_case_sensitive(self):
        self.assertTrue(self.Booking.create_public_booking(
            self.court.id, self.day(2), '10:00', '', member_ref=self.gold.member_id.lower(),
            member_email=self.gold.email))

    def test_a_failed_verification_gives_one_vague_message(self):
        messages = set()
        for ref, email in ((self.gold.member_id, 'wrong@example.com'), ('CC-99999', self.gold.email),
                           (self.gold.member_id, ''), ('', '')):
            if not ref:
                continue
            with self.assertRaises(ValidationError) as error:
                self.Booking.create_public_booking(self.court.id, self.day(2), '10:00', 'X',
                                                   member_ref=ref, member_email=email)
            messages.add(error.exception.args[0])
        self.assertEqual(len(messages), 1)                       # cannot tell which part was wrong
        self.assertIn('could not verify', messages.pop())

    def test_a_lapsed_member_verifies_but_pays_full_price(self):
        self.lapsed.member_id = 'CC-77777'
        booking = self.Booking.create_public_booking(
            self.court.id, self.day(2), '10:00', 'x', member_ref='CC-77777', member_email=self.lapsed.email)
        self.assertEqual((booking.tier, booking.price), ('guest', 800.0))

    def test_members_keep_their_two_a_day_limit_online(self):
        for time in ('08:00', '10:00'):
            self.Booking.create_public_booking(self.court.id, self.day(2), time, 'x',
                                               member_ref=self.gold.member_id, member_email=self.gold.email)
        with self.assertRaisesRegex(ValidationError, 'maximum per day'):
            self.Booking.create_public_booking(self.court.id, self.day(2), '12:00', 'x',
                                               member_ref=self.gold.member_id, member_email=self.gold.email)

    # --- e-mail and the follow-up lead -------------------------------------
    def test_a_confirmation_email_with_the_private_link_is_queued(self):
        booking = self.book(email='mail.guest@example.com')
        mail = self.env['mail.mail'].search([('email_to', '=', 'mail.guest@example.com'),
                                             ('subject', 'like', 'Court booked')])
        self.assertEqual(len(mail), 1)
        self.assertIn(booking.name, mail.subject)
        self.assertIn(booking.name, mail.body_html)
        self.assertIn('/booking/%s' % booking.access_token, mail.body_html)
        self.assertIn('Online Court', mail.body_html)
        self.assertIn('₹800', mail.body_html)

    def test_no_email_is_sent_to_a_phone_only_guest(self):
        before = self.env['mail.mail'].search_count([('subject', 'like', 'Court booked')])
        self.book(email='')
        self.assertEqual(self.env['mail.mail'].search_count([('subject', 'like', 'Court booked')]), before)

    def test_a_guest_booking_files_a_follow_up_lead_without_a_second_email(self):
        booking = self.book(email='lead.guest@example.com')
        lead = self.env['crm.lead'].search([('email_from', '=', 'lead.guest@example.com')])
        self.assertEqual(len(lead), 1)
        self.assertEqual((lead.enquiry_type, lead.sport_interest, lead.enquiry_source), ('court', 'tennis', 'website'))
        self.assertIn(booking.name, lead.description)
        self.assertIn('Offer a membership', lead.description)
        self.assertEqual(self.env['mail.mail'].search_count(
            [('email_to', '=', 'lead.guest@example.com'), ('subject', 'like', 'We received your enquiry')]), 0)

    def test_a_member_booking_files_no_lead(self):
        before = self.env['crm.lead'].search_count([])
        self.Booking.create_public_booking(self.court.id, self.day(2), '10:00', 'x',
                                           member_ref=self.gold.member_id, member_email=self.gold.email)
        self.assertEqual(self.env['crm.lead'].search_count([]), before)

    # --- the private link: view and cancel ---------------------------------
    def test_lookup_by_token(self):
        booking = self.book()
        self.assertEqual(self.Booking.get_by_token(booking.access_token), booking)
        for bad in ('', None, 'short', 'z' * 40):
            self.assertFalse(self.Booking.get_by_token(bad))

    def test_cancelling_from_the_link_frees_the_slot(self):
        booking = self.book()
        booking.cancel_by_visitor()
        self.assertEqual(booking.state, 'cancelled')

    def test_a_cancelled_booking_cannot_be_cancelled_again(self):
        booking = self.book()
        booking.cancel_by_visitor()
        with self.assertRaisesRegex(ValidationError, 'no longer'):
            booking.cancel_by_visitor()

    def test_a_session_that_has_started_cannot_be_cancelled_online(self):
        yesterday = (club_today() - timedelta(days=1)).isoformat()
        started = self.Booking.create({
            'court_id': self.court2.id, 'walkin_name': 'Past', 'state': 'confirmed',
            'start_datetime': self.Booking._club_start_utc(yesterday, '10:00')})
        with self.assertRaisesRegex(ValidationError, 'already started'):
            started.cancel_by_visitor()

    def test_an_invoiced_booking_cannot_be_cancelled_online(self):
        booking = self.book()
        booking.invoice_id = self.env['account.move'].create({
            'move_type': 'out_invoice', 'partner_id': self.gold.id})
        with self.assertRaisesRegex(ValidationError, 'invoiced'):
            booking.cancel_by_visitor()

    # --- the front desk still works ----------------------------------------
    def test_front_desk_bookings_are_unaffected(self):
        booking = self.Booking.create({
            'court_id': self.court.id, 'walkin_name': 'Desk Walk-in',
            'start_datetime': self.Booking._club_start_utc(self.day(3), '10:00')})
        self.assertEqual(booking.booking_source, 'staff')
        self.assertFalse(booking.access_token)
        self.assertFalse(booking.guest_phone)
