from datetime import date

from odoo.tests import TransactionCase, tagged

from .common import FRI, MON, TUE, club_dt


@tagged('post_install', '-at_install', 'club_management')
class TestBookingReports(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.court = cls.env['club.court'].create({
            'name': 'Court R', 'sport': 'tennis', 'list_price': 800.0})
        cls.cricket = cls.env['club.court'].create({
            'name': 'Net R', 'sport': 'cricket', 'list_price': 400.0})
        Partner = cls.env['res.partner']
        cls.silver = Partner.create({
            'name': 'Report Silver', 'plan_id': cls.env.ref('club_management.plan_silver').id})
        cls.silver.action_activate_membership()
        cls.gold = Partner.create({
            'name': 'Report Gold', 'plan_id': cls.env.ref('club_management.plan_gold').id})
        cls.gold.action_activate_membership()

    def _book(self, hour, day=MON, court=None, partner=None, **kw):
        vals = {'court_id': (court or self.court).id, 'start_datetime': club_dt(day, hour)}
        if partner:
            vals['partner_id'] = partner.id
        else:
            vals['walkin_name'] = 'Guest'
        vals.update(kw)
        return self.env['club.booking'].create(vals)

    def test_tier_dimension(self):
        self.assertEqual(self._book(8, partner=self.silver).tier, 'silver')
        self.assertEqual(self._book(9, partner=self.gold).tier, 'gold')
        self.assertEqual(self._book(10).tier, 'guest')

    def test_expired_member_counts_as_guest(self):
        lapsed = self.env['res.partner'].create({
            'name': 'Lapsed R', 'is_member': True,
            'plan_id': self.env.ref('club_management.plan_gold').id,
            'expiry_date': date(2026, 10, MON - 1)})
        self.assertEqual(self._book(8, partner=lapsed).tier, 'guest')

    def test_start_hour_uses_club_time(self):
        self.assertEqual(self._book(18).start_hour, 18)
        night = self.env['club.court'].create({
            'name': 'Night R', 'sport': 'cricket', 'list_price': 1.0, 'open_hour': 0.0, 'close_hour': 24.0})
        self.assertEqual(self._book(1, court=night).start_hour, 1)   # 01:00 IST = 19:30 UTC previous day

    def test_sport_is_stored_for_grouping(self):
        self.assertEqual(self._book(8, court=self.cricket).sport, 'cricket')

    def test_revenue_by_tier(self):
        self._book(8, partner=self.silver)            # 500
        self._book(10, partner=self.gold)             # 0
        self._book(12)                                # 800 (guest)
        self._book(14, court=self.cricket)            # 400 (guest)
        domain = [('court_id', 'in', (self.court | self.cricket).ids)]
        groups = self.env['club.booking']._read_group(domain, ['tier'], ['price:sum'])
        revenue = {tier: total for tier, total in groups}
        self.assertEqual(revenue['silver'], 500.0)
        self.assertEqual(revenue['gold'], 0.0)
        self.assertEqual(revenue['guest'], 1200.0)

    def test_revenue_by_court_and_month(self):
        self._book(8, partner=self.silver)
        self._book(10, day=TUE)
        groups = self.env['club.booking']._read_group(
            [('court_id', '=', self.court.id)], ['court_id', 'booking_date:month'], ['price:sum'])
        self.assertEqual(len(groups), 1)               # both in October 2026
        self.assertEqual(groups[0][-1], 1300.0)

    def test_peak_hours_grouping(self):
        # Friday is social play, so several bookings can share a court and hour.
        for partner in (None, self.silver, self.gold):
            self._book(18, day=FRI, partner=partner, court=self.cricket)
        self._book(9, day=FRI, court=self.cricket)
        groups = self.env['club.booking']._read_group(
            [('court_id', '=', self.cricket.id)], ['start_hour'], ['__count'])
        counts = dict(groups)
        self.assertEqual(counts[18], 3)
        self.assertEqual(counts[9], 1)

    def test_cancelled_bookings_excluded_by_report_domain(self):
        booking = self._book(8)
        booking.action_cancel()
        action = self.env.ref('club_management.action_club_booking_revenue')
        domain = [('court_id', '=', self.court.id)] + eval(action.domain)  # noqa: S307 (trusted data file)
        self.assertFalse(self.env['club.booking'].search(domain))

    def test_report_views_are_valid(self):
        for xmlid in ('view_club_booking_pivot', 'view_club_booking_graph',
                      'view_club_booking_pivot_hours', 'view_club_booking_graph_hours'):
            view = self.env.ref('club_management.' + xmlid)
            arch = self.env['club.booking'].get_view(view.id, view.type)['arch']
            self.assertTrue(arch)
