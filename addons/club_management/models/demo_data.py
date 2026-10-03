"""Demo data generator.

Static demo records (courts, members, products) live in demo/*.xml. Anything that
must be relative to "today" (bookings, enquiries, stock) is generated here so the
demo never goes stale. Only called from demo/demo_activity.xml.
"""
import random
from datetime import datetime, time, timedelta

import pytz

from odoo import api, models
from odoo.exceptions import ValidationError

from .booking import CLUB_TZ, FRIDAY, club_today

PARAM_LOADED = 'club_management.demo_loaded'
PARAM_BUSY_DAY = 'club_management.demo_busy_day'
PARAM_SOCIAL_DAY = 'club_management.demo_social_day'

MEMBERS = ['arjun', 'priya', 'rohan', 'sneha', 'vikram', 'meera', 'aarav', 'diya', 'karan']
TENNIS = ['tennis_1', 'tennis_2', 'tennis_3']
CRICKET = ['cricket_1', 'cricket_2']
WALKIN_NAMES = ['Imran Khan', 'Divya Menon', 'Suresh Rao', 'Neha Gupta', 'Tarun Joshi', 'Pooja Bhatt']

# product xmlid suffix -> (stock on hand, reorder minimum, reorder maximum)
STOCK = {
    'racket': (12, 4, 15), 'bat': (8, 3, 10), 'towel': (25, 10, 40),
    'water': (60, 24, 120), 'coffee': (40, 15, 60), 'lime': (30, 12, 50),
    # below their minimum: the "low stock" demo
    'balls': (3, 10, 40), 'grip': (2, 8, 30), 'energy': (4, 12, 48),
    'sandwich': (5, 10, 30), 'shake': (0, 6, 24),
}


def utc(day, hour, minute=0):
    """Club-local wall time on ``day`` as the naive UTC datetime Odoo stores."""
    local = CLUB_TZ.localize(datetime.combine(day, time(hour, minute)))
    return local.astimezone(pytz.utc).replace(tzinfo=None)


class ClubDemo(models.AbstractModel):
    _name = 'club.demo'
    _description = 'Club demo data loader'

    @api.model
    def load(self):
        """Generate the date-relative demo data once per database."""
        params = self.env['ir.config_parameter'].sudo()
        if params.get_param(PARAM_LOADED):
            return False
        today = club_today()
        busy_day = self._next_non_friday(today + timedelta(days=1))
        social_day = today + timedelta(days=(FRIDAY - today.weekday()) % 7 or 7)
        self._load_history(today)
        self._load_today(today)
        self._load_busy_evening(busy_day)
        self._load_friday_social(social_day)
        self._load_enquiries()
        self._load_stock()
        params.set_param(PARAM_BUSY_DAY, busy_day.isoformat())
        params.set_param(PARAM_SOCIAL_DAY, social_day.isoformat())
        params.set_param(PARAM_LOADED, '1')
        return True

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _next_non_friday(day):
        return day + timedelta(days=1) if day.weekday() == FRIDAY else day

    def _member(self, key):
        return self.env.ref('club_management.demo_member_%s' % key)

    def _court(self, key):
        return self.env.ref('club_management.demo_court_%s' % key)

    def _book(self, court, start, partner=None, walkin=None, players=1, state='confirmed'):
        """Create a booking, skipping it if a booking rule rejects it."""
        Booking = self.env['club.booking'].with_context(tracking_disable=True, mail_create_nolog=True)
        vals = {'court_id': court.id, 'start_datetime': start, 'players': players, 'state': state}
        if partner:
            vals['partner_id'] = partner.id
        else:
            vals['walkin_name'] = walkin or 'Walk-in'
        try:
            with self.env.cr.savepoint():
                return Booking.create(vals)
        except ValidationError:
            return Booking

    # ------------------------------------------------------------------
    # bookings
    # ------------------------------------------------------------------
    def _load_history(self, today):
        """Two weeks of finished bookings so the revenue reports have shape."""
        rng = random.Random(2026)
        members = [self._member(key) for key in MEMBERS]
        courts = [self._court(key) for key in TENNIS + CRICKET]
        hours = [7, 8, 9, 10, 16, 17, 18, 18, 19, 19, 20, 20, 21]   # evenings are busiest
        cancelled = 0
        for offset in range(14, 0, -1):
            day = today - timedelta(days=offset)
            for _ in range(rng.randint(5, 10)):
                court = rng.choice(courts)
                start = utc(day, rng.choice(hours), rng.choice([0, 0, 30]))
                if rng.random() < 0.6:
                    partner, walkin = rng.choice(members), None
                else:
                    partner, walkin = None, rng.choice(WALKIN_NAMES)
                players = rng.randint(1, 4) if day.weekday() == FRIDAY else 1
                state = 'done'
                if cancelled < 3 and rng.random() < 0.05:
                    state, cancelled = 'cancelled', cancelled + 1
                self._book(court, start, partner, walkin, players, state)

    def _load_today(self, today):
        court = self._court('tennis_2')
        self._book(court, utc(today, 17), self._member('rohan'))
        self._book(court, utc(today, 18), None, 'Imran Khan')
        self._book(court, utc(today, 19), self._member('sneha'), state='draft')

    def _load_busy_evening(self, day):
        """Every court booked solid from 17:00/18:00 to 21:00: the 'busy evening'."""
        pool = [self._member(key) for key in MEMBERS]
        used, walkins = {}, 0
        slots = [(court, hour) for hour in (17, 18, 19, 20)
                 for court in map(self._court, TENNIS)]
        slots += [(court, hour) for hour in (18, 19, 20)
                  for court in map(self._court, CRICKET)]
        for index, (court, hour) in enumerate(slots):
            # every third slot goes to a walk-in, who pays the full court price
            partner = None if index % 3 == 2 else next(
                (m for m in pool if used.get(m.id, 0) < 2), None)
            if partner:
                used[partner.id] = used.get(partner.id, 0) + 1
                pool.append(pool.pop(pool.index(partner)))   # rotate so members are spread out
                self._book(court, utc(day, hour), partner)
            else:
                walkins += 1
                self._book(court, utc(day, hour), None, 'Walk-in %s' % walkins)
        # one cancellation and one pending request on the same evening
        self._book(self._court('tennis_1'), utc(day, 21), None, 'Late Cancel', state='cancelled')
        self._book(self._court('cricket_1'), utc(day, 17), None, 'Walk-in Pending', state='draft')

    def _load_friday_social(self, day):
        """Friday social play: groups share a court up to its capacity."""
        groups = [
            ('tennis_1', 18, [3, 2, 2]),     # 7 of 8 places
            ('tennis_1', 19, [4, 4]),        # full
            ('cricket_1', 18, [5, 4]),       # 9 of 10 places
        ]
        letter = iter('ABCDEFGH')
        for key, hour, sizes in groups:
            for size in sizes:
                self._book(self._court(key), utc(day, hour), None,
                           'Friday Group %s' % next(letter), players=size)

    # ------------------------------------------------------------------
    # CRM and stock
    # ------------------------------------------------------------------
    def _load_enquiries(self):
        Lead = self.env['crm.lead']
        for name, email, plan, sport, message in [
            ('Ananya Desai', 'ananya.desai@example.com', 'gold', 'tennis',
             'Looking for a family membership. Do you offer coaching?'),
            ('Rahul Verma', 'rahul.verma@example.com', 'silver', 'cricket',
             'Interested in net practice on weekday evenings.'),
            ('Kavita Shah', 'kavita.shah@example.com', 'junior', 'tennis',
             'My daughter is 11 and wants to join the junior programme.'),
        ]:
            Lead.create_club_enquiry(name, email=email, plan=plan, sport=sport, message=message)

    def _load_stock(self):
        warehouse = self.env['stock.warehouse'].search([], limit=1)
        if not warehouse:
            return
        location = warehouse.lot_stock_id
        for key, (on_hand, minimum, maximum) in STOCK.items():
            product = self.env.ref('club_management.demo_product_%s' % key)
            if on_hand:
                self.env['stock.quant']._update_available_quantity(product, location, on_hand)
            self.env['stock.warehouse.orderpoint'].create({
                'product_id': product.id,
                'warehouse_id': warehouse.id,
                'location_id': location.id,
                'product_min_qty': minimum,
                'product_max_qty': maximum,
                'trigger': 'manual',
            })
