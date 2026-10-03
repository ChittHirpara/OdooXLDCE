import json
from datetime import date

from odoo.tests import HttpCase, TransactionCase, tagged

from .common import FRI, MON, club_dt


def slot(court_data, start):
    return next(s for s in court_data['slots'] if s['start'] == start)


@tagged('post_install', '-at_install', 'club_management')
class TestAvailability(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.court = cls.env['club.court'].create({
            'name': 'Court 1', 'sport': 'tennis', 'list_price': 800.0, 'social_capacity': 4})

    def _book(self, day, hour, minute=0, **kw):
        vals = {'court_id': self.court.id, 'start_datetime': club_dt(day, hour, minute),
                'walkin_name': 'Guest'}
        vals.update(kw)
        return self.env['club.booking'].create(vals)

    def _data(self, day):
        return self.court.get_availability(date(2026, 10, day))[0]

    def test_slots_cover_opening_hours_every_30_minutes(self):
        data = self._data(MON)
        starts = [s['start'] for s in data['slots']]
        self.assertEqual(starts[0], '06:00')
        self.assertEqual(starts[1], '06:30')
        self.assertEqual(starts[-1], '21:00')   # last 1-hour slot before 22:00 close
        self.assertEqual(len(starts), 31)
        self.assertTrue(all(s['available'] for s in data['slots']))
        self.assertFalse(data['is_social'])

    def test_booked_slot_blocks_overlapping_slots(self):
        self._book(MON, 10)
        data = self._data(MON)
        self.assertFalse(slot(data, '09:30')['available'])
        self.assertFalse(slot(data, '10:00')['available'])
        self.assertFalse(slot(data, '10:30')['available'])
        self.assertTrue(slot(data, '09:00')['available'])
        self.assertTrue(slot(data, '11:00')['available'])

    def test_cancelled_booking_does_not_block(self):
        self._book(MON, 10).action_cancel()
        self.assertTrue(slot(self._data(MON), '10:00')['available'])

    def test_other_day_unaffected(self):
        self._book(MON, 10)
        self.assertTrue(slot(self._data(MON + 1), '10:00')['available'])

    def test_friday_reports_places_left(self):
        self._book(FRI, 18, players=3)
        data = self._data(FRI)
        self.assertTrue(data['is_social'])
        self.assertEqual(data['capacity'], 4)
        self.assertEqual(slot(data, '18:00')['places_left'], 1)
        self.assertEqual(slot(data, '18:30')['places_left'], 1)
        self.assertEqual(slot(data, '19:00')['places_left'], 4)

    def test_friday_full_slot_not_available(self):
        self._book(FRI, 18, players=4)
        data = self._data(FRI)
        self.assertFalse(slot(data, '18:00')['available'])
        self.assertEqual(slot(data, '18:00')['places_left'], 0)

    def test_availability_matches_booking_rules(self):
        """A slot reported available must really be bookable."""
        self._book(MON, 10)
        for s in self._data(MON)['slots']:
            hour, minute = map(int, s['start'].split(':'))
            if s['available']:
                self.env['club.booking'].create({
                    'court_id': self.court.id, 'start_datetime': club_dt(MON, hour, minute),
                    'walkin_name': 'Check'}).action_cancel()


@tagged('post_install', '-at_install', 'club_management')
class TestAvailabilityHttp(HttpCase):

    def setUp(self):
        super().setUp()
        self.court = self.env['club.court'].create({
            'name': 'Court HTTP', 'sport': 'cricket', 'list_price': 300.0})
        self.env['club.booking'].create({
            'court_id': self.court.id, 'start_datetime': club_dt(MON, 10), 'walkin_name': 'Guest'})

    def test_endpoint_returns_slots_for_public_user(self):
        response = self.url_open('/club/availability?date=2026-10-05&sport=cricket')
        self.assertEqual(response.status_code, 200)
        courts = json.loads(response.text)['courts']
        mine = next(c for c in courts if c['court_id'] == self.court.id)
        self.assertFalse(slot(mine, '10:00')['available'])
        self.assertTrue(slot(mine, '12:00')['available'])

    def test_endpoint_filters_by_court(self):
        response = self.url_open('/club/availability?date=2026-10-05&court_id=%s' % self.court.id)
        courts = json.loads(response.text)['courts']
        self.assertEqual([c['court_id'] for c in courts], [self.court.id])

    def test_endpoint_rejects_bad_date(self):
        self.assertEqual(self.url_open('/club/availability?date=05-10-2026').status_code, 400)
        self.assertEqual(self.url_open('/club/availability?court_id=abc').status_code, 400)

    def test_endpoint_exposes_no_customer_data(self):
        text = self.url_open('/club/availability?date=2026-10-05').text
        self.assertNotIn('Guest', text)
