from odoo.exceptions import AccessError
from odoo.tests import TransactionCase, tagged

from .common import MON, club_dt


@tagged('post_install', '-at_install', 'club_management')
class TestOwnerDashboard(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.court = cls.env['club.court'].create({'name': 'Court D', 'sport': 'tennis', 'list_price': 800.0})
        cls.env['club.booking'].create({
            'court_id': cls.court.id, 'start_datetime': club_dt(MON, 8), 'walkin_name': 'Guest'})

    def test_court_revenue_and_utilization(self):
        data = self.env['club.dashboard'].get_dashboard_data('all')
        court = next(s for s in data['by_source'] if s['key'] == 'court')
        self.assertGreaterEqual(court['amount'], 800.0)
        self.assertGreaterEqual(data['total_revenue'], court['amount'])
        self.assertTrue(0 < data['court_utilization'] <= 100)

    def test_sources_cover_the_four_revenue_streams(self):
        data = self.env['club.dashboard'].get_dashboard_data('month')
        self.assertEqual([s['key'] for s in data['by_source']], ['membership', 'court', 'shop', 'bar'])

    def test_staff_cannot_open_dashboard(self):
        staff = self.env['res.users'].create({
            'name': 'Desk', 'login': 'desk_dash',
            'groups_id': [(6, 0, [self.env.ref('club_management.group_club_staff').id,
                                  self.env.ref('base.group_user').id])]})
        with self.assertRaises(AccessError):
            self.env['club.dashboard'].with_user(staff).get_dashboard_data()

    def test_court_invoice_is_tagged_with_its_source(self):
        booking = self.env['club.booking'].search([('court_id', '=', self.court.id)], limit=1)
        booking.action_create_invoice()
        self.assertEqual(booking.invoice_id.club_source, 'court')

    def test_bar_order_is_invoiced_and_paid(self):
        product = self.env['product.product'].create({'name': 'Test Cola', 'list_price': 100.0})
        order = self.env['club.order'].create({
            'channel': 'bar', 'payment_method': 'cash', 'customer_name': 'Guest',
            'line_ids': [(0, 0, {'product_id': product.id, 'qty': 2,
                                 'list_price': 100.0, 'unit_price': 100.0})]})
        order._create_invoice()
        self.assertTrue(order.invoice_id, "A bar order should produce an invoice")
        self.assertEqual(order.invoice_id.club_source, 'bar')
        self.assertEqual(order.invoice_id.state, 'posted')
