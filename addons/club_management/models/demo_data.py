"""Demo data generator.

Static demo records (courts, members, products) live in demo/*.xml. Anything that
must be relative to "today" (bookings, enquiries, stock) is generated here so the
demo never goes stale. Only called from demo/demo_activity.xml.
"""
import base64
import random
from datetime import datetime, time, timedelta

import pytz

from odoo import api, models
from odoo.exceptions import ValidationError
from odoo.modules.module import get_manifest
from odoo.tools import convert_file, file_path

from .booking import CLUB_TZ, FRIDAY, club_today

PARAM_LOADED = 'club_management.demo_loaded'
PARAM_BUSY_DAY = 'club_management.demo_busy_day'
PARAM_SOCIAL_DAY = 'club_management.demo_social_day'

MEMBERS = ['arjun', 'priya', 'rohan', 'sneha', 'vikram', 'meera', 'aarav', 'diya', 'karan']
TENNIS = ['tennis_1', 'tennis_2', 'tennis_3']
CRICKET = ['cricket_1', 'cricket_2']
# Courts and members from data/demo_club_data.xml (added by the frontend work). They join
# the generated bookings when present so every screen shows the same busy club.
EXTRA_COURTS = ['court_1', 'court_2', 'court_3', 'court_4']
EXTRA_MEMBERS = ['partner_member_chitt', 'partner_member_aarav', 'partner_member_rohan']
WALKIN_NAMES = ['Imran Khan', 'Divya Menon', 'Suresh Rao', 'Neha Gupta', 'Tarun Joshi', 'Pooja Bhatt']

# product xmlid suffix -> (stock on hand, reorder minimum, reorder maximum)
STOCK = {
    'racket': (12, 4, 15), 'bat': (8, 3, 10), 'towel': (25, 10, 40),
    'water': (60, 24, 120), 'coffee': (40, 15, 60), 'lime': (30, 12, 50),
    # below their minimum: the "low stock" demo
    'balls': (3, 10, 40), 'grip': (2, 8, 30), 'energy': (4, 12, 48),
    'sandwich': (5, 10, 30), 'shake': (0, 6, 24),
}


# product xmlid -> picture in static/img/products (see scripts/gen_product_images.py)
PRODUCT_IMAGES = {
    'demo_product_racket': 'tennis_racket', 'demo_product_balls': 'tennis_balls',
    'demo_product_bat': 'cricket_bat', 'demo_product_grip': 'grip_tape',
    'demo_product_towel': 'towel', 'demo_product_water': 'water_bottle',
    'demo_product_coffee': 'cold_coffee', 'demo_product_energy': 'energy_drink',
    'demo_product_lime': 'lime_soda', 'demo_product_sandwich': 'sandwich',
    'demo_product_shake': 'protein_shake',
    'product_racket_padel_1': 'padel_racket', 'product_racket_tennis_1': 'tennis_racket',
    'product_racket_badminton_1': 'badminton_racket', 'product_balls_tennis_can': 'tennis_balls',
    'product_balls_padel_can': 'padel_balls', 'product_shuttlecocks_doz': 'shuttlecocks',
    'product_bar_espresso': 'espresso', 'product_bar_cappuccino': 'cappuccino',
    'product_bar_shake': 'protein_shake', 'product_bar_water': 'water_bottle',
    'product_bar_burger': 'burger', 'product_bar_wrap': 'wrap',
}


def utc(day, hour, minute=0):
    """Club-local wall time on ``day`` as the naive UTC datetime Odoo stores."""
    local = CLUB_TZ.localize(datetime.combine(day, time(hour, minute)))
    return local.astimezone(pytz.utc).replace(tzinfo=None)


class ClubDemo(models.AbstractModel):
    _name = 'club.demo'
    _description = 'Club demo data loader'

    @api.model
    def install_demo_files(self):
        """Load the club's demo files into a database created WITHOUT Odoo's demo data.

        Odoo's accounting demo data creates journal entries, after which a company can no
        longer change currency. scripts/create_demo_db.sh therefore installs without any
        demo data, so the club can be set up in rupees, and then calls this to add only the
        club's own demo (courts, members, products and the date-relative activity).
        """
        for filename in get_manifest('club_management')['demo']:
            convert_file(self.env, 'club_management', filename, {}, mode='init',
                         noupdate=True, kind='demo')
        return True

    @api.model
    def load_product_images(self):
        """Give the demo products their picture. Safe to run again: a picture someone
        uploaded is never replaced, and products that are not installed are skipped."""
        for xmlid, name in PRODUCT_IMAGES.items():
            product = self.env.ref('club_management.%s' % xmlid, raise_if_not_found=False)
            if not product or product.image_1920:
                continue
            with open(file_path('club_management/static/img/products/%s.svg' % name), 'rb') as picture:
                product.image_1920 = base64.b64encode(picture.read())
        return True

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

    def _ref_all(self, xmlids):
        refs = (self.env.ref('club_management.%s' % x, raise_if_not_found=False) for x in xmlids)
        return [rec for rec in refs if rec]

    def _all_members(self):
        return [self._member(key) for key in MEMBERS] + self._ref_all(EXTRA_MEMBERS)

    def _all_courts(self):
        return [self._court(key) for key in TENNIS + CRICKET] + self._ref_all(EXTRA_COURTS)

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
        members = self._all_members()
        courts = self._all_courts()
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
        pool = self._all_members()
        used, walkins = {}, 0
        courts = self._all_courts()
        # cricket nets start at 18:00, every other sport at 17:00
        slots = [(court, hour) for hour in (17, 18, 19, 20) for court in courts
                 if hour >= (18 if court.sport == 'cricket' else 17)]
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
        """A pipeline with a lead in every stage, so the CRM looks like a club mid-season."""
        Lead = self.env['crm.lead']
        today = club_today()
        stage = lambda xmlid: self.env.ref(xmlid)  # noqa: E731

        def enquire(name, email, plan, sport, message):
            return Lead.create_club_enquiry(name, email=email, plan=plan, sport=sport, message=message)

        def follow_up_in(lead, days, summary):
            lead.activity_ids.action_feedback()        # close the automatic first call
            lead.activity_schedule('mail.mail_activity_data_call', summary=summary,
                                   date_deadline=today + timedelta(days=days),
                                   user_id=(lead.user_id or self.env.user).id)

        # NEW, first call overdue
        late = enquire('Ananya Desai', 'ananya.desai@example.com', 'gold', 'tennis',
                       'Looking for a family membership. Do you offer coaching?')
        late.activity_ids.date_deadline = today - timedelta(days=2)
        # NEW, fresh
        enquire('Meghna Joshi', 'meghna.joshi@example.com', 'silver', 'padel',
                'Can I try a court before joining?')
        # CONTACTED
        contacted = enquire('Rahul Verma', 'rahul.verma@example.com', 'silver', 'cricket',
                            'Interested in net practice on weekday evenings.')
        contacted.stage_id = stage('crm.stage_lead2')
        follow_up_in(contacted, 3, "Send the cricket net timetable")
        # INTERESTED (Junior: birth date captured for the membership)
        interested = enquire('Kavita Shah', 'kavita.shah@example.com', 'junior', 'tennis',
                             'My daughter is 11 and wants to join the junior programme.')
        interested.member_date_of_birth = today.replace(year=today.year - 11)
        interested.stage_id = stage('crm.stage_lead3')
        follow_up_in(interested, 2, "Confirm junior coaching slots")
        # QUOTE SENT
        quoted = enquire('Nikhil Rao', 'nikhil.rao@example.com', 'silver', 'badminton',
                         'Looking for evening badminton and the gym discount.')
        quoted.stage_id = stage('crm.stage_lead3')
        quoted.action_create_membership_quote()
        follow_up_in(quoted, 4, "Ask whether the quote works for them")
        # NEGOTIATION
        negotiating = enquire('Sana Qureshi', 'sana.qureshi@example.com', 'gold', 'tennis',
                              'Corporate rate for 4 colleagues?')
        negotiating.action_create_membership_quote()
        negotiating.stage_id = stage('club_management.stage_negotiation')
        follow_up_in(negotiating, 1, "Agree the group discount")
        # LOST
        lost = enquire('Dev Malhotra', 'dev.malhotra@example.com', 'silver', 'tennis',
                       'Just looking at prices.')
        lost.action_set_lost(lost_reason_id=self.env.ref('club_management.lost_competitor').id)
        # WON: the quote is accepted, so a member is created
        won = enquire('Isha Kulkarni', 'isha.kulkarni@example.com', 'silver', 'tennis',
                      'Joined after a trial session.')
        won.stage_id = stage('crm.stage_lead3')
        won.action_create_membership_quote()
        won.order_ids.filtered(lambda o: o.state in ('draft', 'sent')).action_confirm()

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
