from datetime import date

from odoo.addons.club_management.models.booking import FRIDAY, club_today
from odoo.addons.club_management.models.demo_data import PARAM_BUSY_DAY, PARAM_SOCIAL_DAY
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install', 'club_management')
class TestDemoData(TransactionCase):
    """These run only on databases created with demo data."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.params = cls.env['ir.config_parameter'].sudo()

    def setUp(self):
        super().setUp()
        if not self.env.ref('club_management.demo_member_arjun', raise_if_not_found=False):
            self.skipTest("database has no demo data")

    def _member(self, key):
        return self.env.ref('club_management.demo_member_%s' % key)

    def _day(self, param):
        return date.fromisoformat(self.params.get_param(param))

    # --- members ------------------------------------------------------------
    def test_members_in_every_tier(self):
        for code in ('gold', 'silver', 'junior'):
            members = self.env['res.partner'].search([('plan_id.code', '=', code), ('is_member', '=', True),
                                                      ('id', 'in', [self._member(k).id for k in (
                                                          'arjun', 'priya', 'rohan', 'sneha', 'vikram',
                                                          'meera', 'karan', 'aarav', 'diya')])])
            self.assertTrue(members, "no demo %s member" % code)

    def test_active_members_have_ids_and_tier_pricelists(self):
        for key, code in (('arjun', 'gold'), ('rohan', 'silver'), ('aarav', 'junior')):
            member = self._member(key)
            self.assertEqual(member.member_state, 'active')
            self.assertTrue(member.member_id.startswith('CC-'))
            plan = self.env.ref('club_management.plan_%s' % code)
            self.assertEqual(member.property_product_pricelist, plan.pricelist_id)

    def test_juniors_are_under_18(self):
        self.assertTrue(self._member('aarav').is_junior)
        self.assertTrue(self._member('diya').is_junior)
        self.assertFalse(self._member('arjun').is_junior)

    def test_one_expired_member(self):
        karan = self._member('karan')
        self.assertEqual(karan.member_state, 'expired')
        self.assertNotEqual(karan.property_product_pricelist, karan.plan_id.pricelist_id)

    def test_expiring_member_gets_the_reminder_email(self):
        meera = self._member('meera')
        self.env['res.partner']._cron_send_expiry_reminders()
        mails = self.env['mail.mail'].search([('recipient_ids', 'in', meera.ids)])
        self.assertEqual(len(mails), 1)
        self.assertFalse(self.env['mail.mail'].search([('recipient_ids', 'in', self._member('arjun').ids)]))

    # --- bookings -----------------------------------------------------------
    def test_busy_evening_is_fully_booked(self):
        day = self._day(PARAM_BUSY_DAY)
        self.assertNotEqual(day.weekday(), FRIDAY)
        courts = self.env['club.court'].search([('id', 'in', [
            self.env.ref('club_management.demo_court_%s' % k).id
            for k in ('tennis_1', 'tennis_2', 'tennis_3', 'cricket_1', 'cricket_2')])])
        for data in courts.get_availability(day):
            by_start = {s['start']: s['available'] for s in data['slots']}
            first = 17 if data['sport'] == 'tennis' else 18
            for hour in range(first, 21):
                self.assertFalse(by_start['%02d:00' % hour],
                                 "%s free at %s:00" % (data['court'], hour))
            self.assertTrue(by_start['08:00'], "%s should be free in the morning" % data['court'])

    def test_busy_evening_also_covers_the_frontend_demo_courts(self):
        day = self._day(PARAM_BUSY_DAY)
        for key in ('court_1', 'court_2', 'court_3', 'court_4'):
            court = self.env.ref('club_management.%s' % key, raise_if_not_found=False)
            if not court:
                self.skipTest("frontend demo courts not installed")
            by_start = {s['start']: s['available'] for s in court.get_availability(day)[0]['slots']}
            for hour in range(17, 21):
                self.assertFalse(by_start['%02d:00' % hour], "%s free at %s:00" % (court.name, hour))

    def test_frontend_demo_products_get_tier_discounts(self):
        product = self.env.ref('club_management.product_racket_tennis_1', raise_if_not_found=False)
        if not product:
            self.skipTest("frontend demo products not installed")
        gold = self.env.ref('club_management.plan_gold').pricelist_id
        self.assertAlmostEqual(gold._get_product_price(product, 1.0), product.list_price * 0.8)

    def test_busy_evening_mixes_members_and_walkins(self):
        day = self._day(PARAM_BUSY_DAY)
        bookings = self.env['club.booking'].search([
            ('booking_date', '=', day), ('state', '=', 'confirmed')])
        self.assertGreaterEqual(len(bookings), 15)
        self.assertTrue(bookings.filtered('partner_id'))
        self.assertTrue(bookings.filtered(lambda b: not b.partner_id))
        for partner in bookings.partner_id:
            self.assertLessEqual(len(bookings.filtered(lambda b: b.partner_id == partner)), 2)

    def test_friday_social_play(self):
        day = self._day(PARAM_SOCIAL_DAY)
        self.assertEqual(day.weekday(), FRIDAY)
        court = self.env.ref('club_management.demo_court_tennis_1')
        slots = {s['start']: s for s in court.get_availability(day)[0]['slots']}
        self.assertTrue(court.get_availability(day)[0]['is_social'])
        self.assertEqual(slots['18:00']['places_left'], 1)    # 7 of 8 taken
        self.assertFalse(slots['19:00']['available'])         # 8 of 8 taken

    def test_history_gives_the_reports_something_to_show(self):
        past = self.env['club.booking'].search([
            ('state', '=', 'done'), ('booking_date', '<', club_today())])
        self.assertGreaterEqual(len(past), 30)
        self.assertGreater(sum(past.mapped('price')), 0)
        self.assertGreaterEqual(len(set(past.mapped('tier'))), 3)
        self.assertGreaterEqual(len(set(past.mapped('booking_date'))), 10)

    def test_demo_bookings_respect_the_rules(self):
        demo_courts = self.env['club.court'].search([('id', 'in', [
            self.env.ref('club_management.demo_court_%s' % k).id
            for k in ('tennis_1', 'tennis_2', 'tennis_3', 'cricket_1', 'cricket_2')])])
        bookings = self.env['club.booking'].search([
            ('court_id', 'in', demo_courts.ids), ('state', '!=', 'cancelled'), ('is_social', '=', False)])
        seen = set()
        for booking in bookings:
            key = (booking.court_id.id, booking.start_datetime)
            self.assertNotIn(key, seen, "double booking on %s" % booking.court_id.name)
            seen.add(key)

    # --- CRM ----------------------------------------------------------------
    def test_demo_enquiries_in_crm(self):
        tag = self.env.ref('club_management.crm_tag_club_enquiry')
        leads = self.env['crm.lead'].search([('tag_ids', 'in', tag.ids), ('email_from', 'like', '@example.com')])
        self.assertGreaterEqual(len(leads), 3)

    # --- stock --------------------------------------------------------------
    def test_low_stock_products_are_below_reorder_minimum(self):
        Orderpoint = self.env['stock.warehouse.orderpoint']
        low = []
        for key in ('balls', 'grip', 'energy', 'sandwich', 'shake'):
            product = self.env.ref('club_management.demo_product_%s' % key)
            rule = Orderpoint.search([('product_id', '=', product.id)], limit=1)
            self.assertTrue(rule, "no reorder rule for %s" % product.name)
            self.assertLess(product.qty_available, rule.product_min_qty, product.name)
            low.append(product)
        self.assertEqual(len(low), 5)

    def test_healthy_products_are_above_reorder_minimum(self):
        Orderpoint = self.env['stock.warehouse.orderpoint']
        for key in ('racket', 'bat', 'towel', 'water', 'coffee', 'lime'):
            product = self.env.ref('club_management.demo_product_%s' % key)
            rule = Orderpoint.search([('product_id', '=', product.id)], limit=1)
            self.assertGreaterEqual(product.qty_available, rule.product_min_qty, product.name)

    def test_demo_products_are_in_the_discount_categories_and_pos(self):
        shop = self.env.ref('club_management.product_category_shop')
        bar = self.env.ref('club_management.product_category_bar')
        gold = self.env.ref('club_management.plan_gold').pricelist_id
        for key, categ, expected in (('racket', shop, 5200.0), ('coffee', bar, 153.0)):
            product = self.env.ref('club_management.demo_product_%s' % key)
            self.assertEqual(product.categ_id, categ)
            self.assertTrue(product.available_in_pos)
            self.assertAlmostEqual(gold._get_product_price(product, 1.0), expected)

    # --- loader -------------------------------------------------------------
    def test_loader_runs_only_once(self):
        before = self.env['club.booking'].search_count([])
        self.assertFalse(self.env['club.demo'].load())
        self.assertEqual(self.env['club.booking'].search_count([]), before)
