from odoo.exceptions import UserError, ValidationError
from odoo.tests import TransactionCase, tagged

from .common import FRI, MON, TUE, club_dt


@tagged('post_install', '-at_install', 'club_management')
class TestBookingRules(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.court = cls.env['club.court'].create({
            'name': 'Court 1', 'sport': 'tennis', 'list_price': 800.0, 'social_capacity': 4})
        cls.court2 = cls.env['club.court'].create({
            'name': 'Court 2', 'sport': 'tennis', 'list_price': 800.0})
        cls.member = cls.env['res.partner'].create({'name': 'Member A'})
        cls.member2 = cls.env['res.partner'].create({'name': 'Member B'})

    def _book(self, day, hour, minute=0, court=None, partner=None, **kw):
        vals = {
            'court_id': (court or self.court).id,
            'start_datetime': club_dt(day, hour, minute),
        }
        if partner is None and 'walkin_name' not in kw:
            partner = self.member
        if partner:
            vals['partner_id'] = partner.id
        vals.update(kw)
        return self.env['club.booking'].create(vals)

    # --- duration and slots -------------------------------------------------
    def test_booking_lasts_one_hour(self):
        booking = self._book(MON, 10)
        self.assertEqual((booking.end_datetime - booking.start_datetime).seconds, 3600)
        self.assertTrue(booking.name.startswith('BK/'))

    def test_start_on_hour_and_half_hour_allowed(self):
        self._book(MON, 10, 0)
        self._book(MON, 12, 30, partner=self.member2)

    def test_start_off_grid_rejected(self):
        for minute in (15, 45, 10):
            with self.assertRaises(ValidationError):
                self._book(MON, 10, minute)

    def test_outside_opening_hours_rejected(self):
        with self.assertRaises(ValidationError):
            self._book(MON, 5, 30)          # before 06:00
        with self.assertRaises(ValidationError):
            self._book(MON, 21, 30)         # would end 22:30
        self._book(MON, 6, 0)               # first slot
        self._book(MON, 21, 0, partner=self.member2)  # last slot

    # --- overlap ------------------------------------------------------------
    def test_overlap_same_court_rejected(self):
        self._book(MON, 10, 0)
        for hour, minute in ((10, 0), (10, 30), (9, 30)):
            with self.assertRaises(ValidationError):
                self._book(MON, hour, minute, partner=self.member2)

    def test_adjacent_and_other_court_allowed(self):
        self._book(MON, 10, 0)
        self._book(MON, 11, 0, partner=self.member2)                    # back to back
        self._book(MON, 10, 0, court=self.court2, partner=self.member2)  # other court

    def test_cancelled_booking_frees_slot(self):
        booking = self._book(MON, 10)
        booking.action_cancel()
        self._book(MON, 10, partner=self.member2)

    def test_reactivating_cancelled_booking_rechecks_overlap(self):
        booking = self._book(MON, 10)
        booking.action_cancel()
        self._book(MON, 10, partner=self.member2)
        with self.assertRaises(ValidationError):
            booking.action_draft()

    # --- max 2 per member per day -------------------------------------------
    def test_max_two_bookings_per_member_per_day(self):
        self._book(MON, 8)
        self._book(MON, 10)
        with self.assertRaises(ValidationError):
            self._book(MON, 12)

    def test_daily_limit_is_per_member_and_per_day(self):
        self._book(MON, 8)
        self._book(MON, 10)
        self._book(MON, 12, partner=self.member2)   # other member
        self._book(TUE, 8)                          # other day

    def test_cancelled_booking_does_not_count_for_daily_limit(self):
        first = self._book(MON, 8)
        self._book(MON, 10)
        first.action_cancel()
        self._book(MON, 12)

    def test_walkins_have_no_daily_limit(self):
        for hour in (8, 10, 12):
            self._book(MON, hour, partner=False, walkin_name='Walk-in Joe')

    def test_booking_needs_member_or_walkin_name(self):
        with self.assertRaises(ValidationError):
            self._book(MON, 10, partner=False, walkin_name=False)

    def test_daily_limit_uses_club_timezone(self):
        # 01:00 IST Tuesday is Monday 19:30 UTC: it must count towards Tuesday, not Monday.
        night_court = self.env['club.court'].create({
            'name': 'Night Court', 'sport': 'cricket', 'list_price': 100.0,
            'open_hour': 0.0, 'close_hour': 24.0})
        self._book(MON, 8)
        self._book(MON, 10)
        self._book(TUE, 1, court=night_court)   # different club day, allowed
        with self.assertRaises(ValidationError):
            self._book(MON, 12)

    # --- Friday social play -------------------------------------------------
    def test_friday_is_social_and_monday_is_not(self):
        self.assertTrue(self._book(FRI, 18).is_social)
        self.assertFalse(self._book(MON, 18).is_social)

    def test_friday_detected_in_club_timezone(self):
        # With normal hours IST and UTC share a date, so use a court open after
        # midnight: 02:00 IST Friday is Thursday 20:30 UTC.
        night_court = self.env['club.court'].create({
            'name': 'Night Court', 'sport': 'cricket', 'list_price': 100.0,
            'open_hour': 0.0, 'close_hour': 24.0})
        booking = self._book(FRI, 2, court=night_court)
        self.assertEqual(booking.start_datetime.weekday(), 3)
        self.assertTrue(booking.is_social)
        self.assertEqual(booking.booking_date.day, FRI)

    def test_friday_many_players_share_a_court(self):
        names = ['P1', 'P2', 'P3', 'P4']
        for name in names:
            self._book(FRI, 18, partner=False, walkin_name=name)   # capacity is 4

    def test_friday_capacity_exceeded_rejected(self):
        self._book(FRI, 18, partner=False, walkin_name='Group', players=3)
        self._book(FRI, 18, partner=False, walkin_name='Solo', players=1)
        with self.assertRaises(ValidationError):
            self._book(FRI, 18, partner=False, walkin_name='Late', players=1)

    def test_friday_capacity_counts_partially_overlapping_slots(self):
        self._book(FRI, 18, partner=False, walkin_name='A', players=3)
        with self.assertRaises(ValidationError):
            self._book(FRI, 18, 30, partner=False, walkin_name='B', players=2)
        self._book(FRI, 19, partner=False, walkin_name='C', players=3)  # no overlap with 18:00-19:00

    def test_friday_group_larger_than_capacity_rejected(self):
        with self.assertRaises(ValidationError):
            self._book(FRI, 18, partner=False, walkin_name='Crowd', players=5)

    def test_friday_cancelled_players_free_capacity(self):
        big = self._book(FRI, 18, partner=False, walkin_name='Big', players=4)
        big.action_cancel()
        self._book(FRI, 18, partner=False, walkin_name='Next', players=4)

    def test_friday_still_enforces_daily_limit(self):
        self._book(FRI, 17)
        self._book(FRI, 18)
        with self.assertRaises(ValidationError):
            self._book(FRI, 19)

    # --- workflow: cancel / reschedule --------------------------------------
    def test_state_flow(self):
        booking = self._book(MON, 10)
        self.assertEqual(booking.state, 'draft')
        booking.action_confirm()
        self.assertEqual(booking.state, 'confirmed')
        booking.action_done()
        self.assertEqual(booking.state, 'done')
        with self.assertRaises(UserError):
            booking.action_cancel()

    def test_reschedule_moves_booking(self):
        booking = self._book(MON, 10)
        booking.action_reschedule(club_dt(MON, 14))
        self.assertEqual(booking.start_datetime, club_dt(MON, 14))
        self.assertEqual(booking.end_datetime, club_dt(MON, 15))

    def test_reschedule_conflict_rejected(self):
        self._book(MON, 14, partner=self.member2)
        booking = self._book(MON, 10)
        with self.assertRaises(ValidationError):
            booking.action_reschedule(club_dt(MON, 14, 30))

    def test_reschedule_across_midnight_respects_new_day_limit(self):
        self._book(TUE, 8)
        self._book(TUE, 10)
        booking = self._book(MON, 10)
        with self.assertRaises(ValidationError):
            booking.action_reschedule(club_dt(TUE, 12))

    def test_cannot_reschedule_cancelled_booking(self):
        booking = self._book(MON, 10)
        booking.action_cancel()
        with self.assertRaises(UserError):
            booking.action_reschedule(club_dt(MON, 12))
