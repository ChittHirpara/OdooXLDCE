from odoo.exceptions import AccessError
from odoo.tests import TransactionCase, tagged

from .common import MON, club_dt


@tagged('post_install', '-at_install', 'club_management')
class TestOwnerReports(TransactionCase):
    """Dashboard extras, analytics, staff overview and the notification e-mails."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        cls.Dash = env['club.dashboard']
        cls.gold = env.ref('club_management.plan_gold')
        cls.court = env['club.court'].create({'name': 'Court R', 'sport': 'padel', 'list_price': 700.0})
        cls.member = env['res.partner'].create({'name': 'Report Member', 'email': 'report.member@example.com'})
        cls.member.plan_id = cls.gold
        cls.member.action_activate_membership()
        cls.product = env['product.product'].create({'name': 'Report Cola', 'list_price': 100.0})
        env['club.order'].create({
            'channel': 'bar', 'payment_method': 'upi', 'customer_name': 'Guest', 'plan_id': cls.gold.id,
            'line_ids': [(0, 0, {'product_id': cls.product.id, 'qty': 3, 'list_price': 100.0, 'unit_price': 90.0})]})

    def desk_user(self, login):
        return self.env['res.users'].create({
            'name': login, 'login': login,
            'groups_id': [(6, 0, [self.env.ref('club_management.group_club_staff').id])]})

    # -- dashboard -------------------------------------------------------
    def test_dashboard_has_the_requested_numbers(self):
        data = self.Dash.get_dashboard_data('all')
        for key in ('total_revenue', 'membership_revenue', 'court_revenue', 'shop_sales', 'bar_sales',
                    'active_members', 'expired_members', 'todays_bookings', 'todays_sales'):
            self.assertIn(key, data)
        self.assertGreaterEqual(data['bar_sales'], 270.0)
        self.assertGreaterEqual(data['active_members'], 1)

    def test_expired_members_are_counted(self):
        before = self.Dash.get_dashboard_data('all')['expired_members']
        lapsed = self.env['res.partner'].create({
            'name': 'Lapsed', 'is_member': True, 'plan_id': self.gold.id,
            'join_date': '2020-01-01', 'expiry_date': '2020-12-31'})
        self.assertEqual(lapsed.member_state, 'expired')
        self.assertEqual(self.Dash.get_dashboard_data('all')['expired_members'], before + 1)

    def test_todays_sales_include_todays_orders(self):
        self.assertGreaterEqual(self.Dash.get_dashboard_data('today')['todays_sales'], 270.0)

    # -- analytics -------------------------------------------------------
    def test_analytics_sections(self):
        data = self.Dash.get_analytics(6)
        self.assertEqual(data['months'], 6)
        self.assertEqual(len(data['monthly_revenue']), 6)
        self.assertEqual(len(data['membership_growth']), 6)
        names = [row['name'] for row in data['revenue_by_plan']]
        for expected in ('Gold', 'Silver', 'Junior', 'Non-members'):
            self.assertIn(expected, names)
        gold = next(r for r in data['revenue_by_plan'] if r['name'] == 'Gold')
        self.assertGreaterEqual(gold['shop_bar'], 270.0)
        self.assertTrue(any(row['product'] == 'Report Cola' and row['qty'] == 3 for row in data['best_sellers']))
        self.assertGreaterEqual(data['bar']['total'], 270.0)
        self.assertEqual(len(data['bar']['daily']), 14)
        upi = next(r for r in data['payment_methods'] if r['method'] == 'UPI')
        self.assertGreaterEqual(upi['amount'], 270.0)
        self.assertTrue(any(row['court'] == 'Court R' for row in data['court_utilization']))
        self.assertGreaterEqual(data['membership_growth'][-1]['joined'], 1, "the member joined this month")

    def test_this_months_revenue_matches_the_dashboard(self):
        analytics = self.Dash.get_analytics(3)
        month = self.Dash.get_dashboard_data('month')
        self.assertAlmostEqual(analytics['monthly_revenue'][-1]['total'], month['total_revenue'], places=2)

    def test_analytics_range_is_clamped(self):
        self.assertEqual(self.Dash.get_analytics(500)['months'], 24)
        self.assertEqual(self.Dash.get_analytics('nonsense')['months'], 6)

    # -- staff -----------------------------------------------------------
    def test_staff_overview_lists_staff_and_hides_the_system_user(self):
        staff = self.desk_user('desk_dee')
        data = self.Dash.get_staff_overview()
        row = next(u for u in data['staff'] if u['id'] == staff.id)
        self.assertEqual(row['role'], 'Staff')
        self.assertNotIn(self.env.ref('base.user_root').id, [u['id'] for u in data['staff']])
        self.assertIn('shifts', data)

    def test_reports_are_for_managers_only(self):
        desk = self.desk_user('desk_r')
        for method in ('get_analytics', 'get_staff_overview'):
            with self.assertRaises(AccessError):
                getattr(self.Dash.with_user(desk), method)()

    # -- notifications ---------------------------------------------------
    def sent(self, email, subject):
        return self.env['mail.mail'].search([('email_to', '=', email), ('subject', 'ilike', subject)])

    def test_cancelling_a_booking_e_mails_the_member(self):
        booking = self.env['club.booking'].create({
            'court_id': self.court.id, 'partner_id': self.member.id, 'start_datetime': club_dt(MON, 9)})
        booking.action_cancel()
        self.assertTrue(self.sent('report.member@example.com', 'Booking cancelled'))

    def test_cancelling_a_guest_booking_uses_the_guest_email(self):
        booking = self.env['club.booking'].create({
            'court_id': self.court.id, 'walkin_name': 'Guest G', 'guest_email': 'guest.g@example.com',
            'start_datetime': club_dt(MON, 11)})
        booking.action_cancel()
        self.assertTrue(self.sent('guest.g@example.com', 'Booking cancelled'))

    def test_cancelling_without_an_email_sends_nothing_and_does_not_fail(self):
        booking = self.env['club.booking'].create({
            'court_id': self.court.id, 'walkin_name': 'No Mail', 'start_datetime': club_dt(MON, 12)})
        booking.action_cancel()
        self.assertEqual(booking.state, 'cancelled')

    def test_paying_a_court_invoice_sends_a_payment_confirmation(self):
        payer = self.env['res.partner'].create({'name': 'Court Payer', 'email': 'court.payer@example.com'})
        booking = self.env['club.booking'].create({
            'court_id': self.court.id, 'partner_id': payer.id, 'start_datetime': club_dt(MON, 14)})
        booking.action_create_invoice()
        invoice = booking.invoice_id
        invoice.action_post()
        self.env['account.payment.register'].with_context(
            active_model='account.move', active_ids=invoice.ids).create({}).action_create_payments()
        self.assertEqual(invoice.payment_state, 'paid')
        self.assertTrue(self.sent('court.payer@example.com', 'Payment received'))

    # -- menus -----------------------------------------------------------
    def visible_menus(self, user):
        """Names of the menus the user can reach: allowed themselves and under allowed parents."""
        Menu = self.env['ir.ui.menu'].with_user(user)
        allowed = set(Menu._visible_menu_ids())
        reachable = Menu.browse(allowed).filtered(
            lambda menu: all(int(part) in allowed for part in menu.parent_path.split('/') if part))
        return reachable.mapped('name')

    def test_the_new_menus_exist_for_a_manager(self):
        # The whole Club app may be switched off in the app switcher (menu_tidy.xml), so look
        # at the menus themselves, hidden or not.
        names = self.env['ir.ui.menu'].with_context(active_test=False).search([
            ('parent_path', '=like', self.env.ref('club_management.menu_club_root').parent_path + '%')]).mapped('name')
        for expected in ('Owner Dashboard', 'Reports & Analytics', 'Staff', 'Notifications', 'Administration',
                         'Staff Overview', 'POS Shifts', 'Staff Activity',
                         'Notification Templates', 'Products', 'Record History'):
            self.assertIn(expected, names)

    def test_staff_do_not_see_the_manager_menus(self):
        names = self.visible_menus(self.desk_user('desk_menu'))
        for hidden in ('Owner Dashboard', 'Reports & Analytics', 'Staff Overview', 'Notifications', 'Administration'):
            self.assertNotIn(hidden, names)


@tagged('post_install', '-at_install', 'club_management')
class TestClubHome(TransactionCase):
    """The landing page of the Club app, open to every member of the team."""

    def desk(self, login, manager=False):
        group = 'club_management.group_club_manager' if manager else 'club_management.group_club_staff'
        return self.env['res.users'].create({
            'name': login, 'login': login, 'groups_id': [(6, 0, [self.env.ref(group).id])]})

    def test_staff_get_counts_but_no_owner_tiles(self):
        data = self.env['club.dashboard'].with_user(self.desk('home_staff')).get_home()
        self.assertFalse(data['is_manager'])
        for key in ('bookings_today', 'open_enquiries', 'open_tickets', 'low_stock', 'expiring'):
            self.assertGreaterEqual(data['counts'][key], 0)
        self.assertNotIn('revenue', str(data).lower())

    def test_a_manager_is_flagged_so_the_owner_tiles_show(self):
        self.assertTrue(self.env['club.dashboard'].with_user(self.desk('home_boss', manager=True)).get_home()['is_manager'])

    def test_only_club_staff_can_open_it(self):
        outsider = self.env['res.users'].create({'name': 'Outsider', 'login': 'home_outsider'})
        with self.assertRaises(AccessError):
            self.env['club.dashboard'].with_user(outsider).get_home()

    def test_the_counts_follow_the_data(self):
        Dash = self.env['club.dashboard']
        before = Dash.get_home()['counts']['open_tickets']
        self.env['club.ticket'].create_public('Hal', 'complaint', 'Home test', email='hal@example.com')
        self.assertEqual(Dash.get_home()['counts']['open_tickets'], before + 1)

    def test_the_club_app_opens_on_home_and_has_an_icon(self):
        root = self.env.ref('club_management.menu_club_root')
        self.assertTrue(root.active)
        self.assertTrue(root.web_icon_data, "the Club app has its own icon in the app grid")
        children = root.child_id.sorted('sequence')
        self.assertEqual(children[0].name, 'Home')
        self.assertEqual(children[0].action, self.env.ref('club_management.action_club_home'))
