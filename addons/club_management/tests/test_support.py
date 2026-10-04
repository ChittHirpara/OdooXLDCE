from datetime import timedelta

from psycopg2 import IntegrityError

from odoo import fields
from odoo.exceptions import AccessError, ValidationError
from odoo.tests import TransactionCase, tagged
from odoo.tools import mute_logger

from .common import MON, club_dt


@tagged('post_install', '-at_install', 'club_management')
class TestFeedback(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Feedback = cls.env['club.feedback']
        cls.court = cls.env['club.court'].create({'name': 'Court F', 'sport': 'tennis', 'list_price': 500.0})

    def test_a_visitor_can_leave_a_rating(self):
        feedback = self.Feedback.create_public('court', 5, comment=' Great court ', name='Fay', email='fay@example.com')
        self.assertEqual((feedback.area, feedback.rating, feedback.comment), ('court', 5, 'Great court'))
        self.assertEqual(feedback.stars, '★' * 5)
        self.assertEqual(feedback.source, 'website')

    def test_bad_input_is_refused_with_a_message(self):
        for args, message in (
                (('nowhere', 4), 'what you are rating'), (('club', 0), '1 to 5'), (('club', 6), '1 to 5'),
                (('club', 'abc'), '1 to 5'), (('club', 4, None, None, 'not-an-email'), 'not valid')):
            with self.assertRaises(ValidationError, msg=str(args)) as caught:
                self.Feedback.create_public(*args)
            self.assertIn(message, caught.exception.args[0])

    def test_the_database_also_enforces_the_range(self):
        with self.assertRaises(IntegrityError), mute_logger('odoo.sql_db'):
            self.Feedback.create({'area': 'club', 'rating': 9})

    def test_booking_link_brings_the_member(self):
        member = self.env['res.partner'].create({'name': 'Rated Member', 'email': 'rated@example.com'})
        booking = self.env['club.booking'].create({
            'court_id': self.court.id, 'partner_id': member.id, 'start_datetime': club_dt(MON, 9)})
        booking.access_token = 'feedback-token-0123456789'
        feedback = self.Feedback.create_public('court', 4, booking_token='feedback-token-0123456789')
        self.assertEqual(feedback.booking_id, booking)
        self.assertEqual(feedback.partner_id, member)
        self.assertEqual(feedback.email, 'rated@example.com')

    def test_summary_averages_per_area(self):
        self.Feedback.search([]).unlink()
        self.Feedback.create_public('bar', 5)
        self.Feedback.create_public('bar', 3)
        self.Feedback.create_public('shop', 2)
        summary = self.Feedback.rating_summary()
        by_area = {row['area']: row for row in summary['rows']}
        self.assertEqual(by_area['bar']['average'], 4.0)
        self.assertEqual(by_area['bar']['count'], 2)
        self.assertEqual(by_area['court']['count'], 0)
        self.assertEqual(summary['count'], 3)
        self.assertAlmostEqual(summary['average'], 3.33, places=2)


@tagged('post_install', '-at_install', 'club_management')
class TestSupportTickets(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Ticket = cls.env['club.ticket']

    def ticket(self, **kw):
        values = dict(name='Tina', category='complaint', subject='Cold showers', description='No hot water.',
                      email='tina@example.com')
        values.update(kw)
        return self.Ticket.create_public(
            values.pop('name'), values.pop('category'), values.pop('subject'), **values)

    def test_website_ticket_is_numbered_assigned_and_acknowledged(self):
        ticket = self.ticket()
        self.assertTrue(ticket.name.startswith('TKT-'))
        self.assertEqual(ticket.state, 'new')
        self.assertEqual(ticket.source, 'website')
        self.assertGreaterEqual(len(ticket.access_token), 24)
        self.assertTrue(ticket.user_id, "a manager is assigned")
        self.assertTrue(ticket.activity_ids, "the assignee gets a to-do")
        self.assertTrue(self.env['mail.mail'].search([('email_to', '=', 'tina@example.com'),
                                                      ('subject', 'ilike', ticket.name)]))

    def test_refund_requests_are_high_priority(self):
        self.assertEqual(self.ticket(category='refund').priority, '1')
        self.assertEqual(self.ticket(category='complaint').priority, '0')

    def test_bad_input_is_refused(self):
        for kwargs, message in (
                (dict(name=' '), 'your name'), (dict(email='', phone=''), 'email address or a phone'),
                (dict(email='nope'), 'not valid'), (dict(category='x'), 'what your request'),
                (dict(subject=' '), 'short title')):
            with self.assertRaises(ValidationError, msg=str(kwargs)) as caught:
                self.ticket(**kwargs)
            self.assertIn(message, caught.exception.args[0])

    def test_workflow_start_resolve_close_reopen(self):
        ticket = self.ticket()
        ticket.action_start()
        self.assertEqual(ticket.state, 'progress')
        ticket.resolution = 'We fixed the boiler.'
        ticket.action_resolve()
        self.assertEqual(ticket.state, 'resolved')
        self.assertTrue(ticket.resolved_date)
        self.assertTrue(self.env['mail.mail'].search([('email_to', '=', 'tina@example.com'),
                                                      ('subject', 'ilike', 'has been resolved')]))
        ticket.action_close()
        self.assertEqual(ticket.state, 'closed')
        ticket.action_reopen()
        self.assertEqual((ticket.state, ticket.resolved_date), ('progress', False))

    def test_public_status_hides_internal_notes_until_resolved(self):
        ticket = self.ticket()
        ticket.resolution = 'Internal plan'
        self.assertFalse(ticket._public_status()['resolution'])
        ticket.action_resolve()
        self.assertEqual(ticket._public_status()['resolution'], 'Internal plan')
        self.assertNotIn('user_id', ticket._public_status())

    def test_ticket_lookup_needs_the_secret_token(self):
        ticket = self.ticket()
        self.assertEqual(self.Ticket.get_by_token(ticket.access_token), ticket)
        self.assertFalse(self.Ticket.get_by_token('short'))
        self.assertFalse(self.Ticket.get_by_token('x' * 30))

    def test_order_link_brings_the_customer(self):
        member = self.env['res.partner'].create({'name': 'Order Member', 'email': 'order.member@example.com'})
        order = self.env['club.order'].create({'channel': 'shop', 'partner_id': member.id, 'customer_name': 'Order Member'})
        order.access_token = 'order-token-0123456789abcd'
        ticket = self.ticket(order_token='order-token-0123456789abcd', category='order')
        self.assertEqual((ticket.order_id, ticket.partner_id), (order, member))

    def test_staff_can_work_tickets_and_the_manager_can_delete(self):
        desk = self.env['res.users'].create({
            'name': 'Desk S', 'login': 'desk_support',
            'groups_id': [(6, 0, [self.env.ref('club_management.group_club_staff').id])]})
        ticket = self.ticket()
        ticket.with_user(desk).action_start()
        self.assertEqual(ticket.state, 'progress')
        with self.assertRaises(AccessError):
            ticket.with_user(desk).unlink()


@tagged('post_install', '-at_install', 'club_management')
class TestMonitoring(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Dash = cls.env['club.dashboard']

    def check(self, key):
        return next(c for c in self.Dash.get_monitoring()['checks'] if c['key'] == key)

    def test_all_the_requested_checks_exist(self):
        keys = [c['key'] for c in self.Dash.get_monitoring()['checks']]
        for expected in ('failed_payments', 'failed_bookings', 'low_inventory', 'expiring_memberships',
                         'pos_sessions', 'open_tickets', 'low_ratings'):
            self.assertIn(expected, keys)

    def test_status_follows_the_count(self):
        data = self.Dash.get_monitoring()
        for check in data['checks']:
            self.assertEqual(check['status'] == 'ok', check['count'] == 0)
        self.assertIn(data['overall'], ('ok', 'warn', 'alert'))

    def test_cancelled_bookings_show_as_failed_bookings(self):
        court = self.env['club.court'].create({'name': 'Court M', 'sport': 'padel', 'list_price': 600.0})
        before = self.check('failed_bookings')['count']
        booking = self.env['club.booking'].create({
            'court_id': court.id, 'walkin_name': 'Guest M', 'start_datetime': club_dt(MON, 10)})
        booking.action_cancel()
        after = self.check('failed_bookings')
        self.assertEqual(after['count'], before + 1)
        self.assertEqual(after['status'], 'warn')

    def test_expiring_memberships_are_listed(self):
        gold = self.env.ref('club_management.plan_gold')
        member = self.env['res.partner'].create({
            'name': 'Expiring Eve', 'is_member': True, 'plan_id': gold.id,
            'join_date': fields.Date.today() - timedelta(days=300),
            'expiry_date': fields.Date.today() + timedelta(days=3)})
        self.assertTrue(any(i['title'] == member.name for i in self.check('expiring_memberships')['items']
                            ) or self.check('expiring_memberships')['count'] > 8)

    def test_an_unpaid_old_club_invoice_is_a_failed_payment(self):
        partner = self.env['res.partner'].create({'name': 'Late Payer'})
        product = self.env['product.product'].create({'name': 'Late Cola', 'list_price': 100.0})
        invoice = self.env['account.move'].create({
            'move_type': 'out_invoice', 'club_source': 'bar', 'partner_id': partner.id,
            'invoice_date': fields.Date.today() - timedelta(days=10),
            'invoice_line_ids': [(0, 0, {'product_id': product.id, 'quantity': 1, 'price_unit': 100.0})]})
        invoice.action_post()
        check = self.check('failed_payments')
        self.assertEqual(check['status'], 'alert')
        self.assertTrue(any(i['title'] == invoice.name for i in check['items']) or check['count'] > 8)

    def test_open_tickets_and_low_ratings_show_up(self):
        self.env['club.ticket'].create_public('Mo', 'refund', 'Refund please', email='mo@example.com')
        self.env['club.feedback'].create_public('court', 1, comment='Terrible')
        self.assertGreaterEqual(self.check('open_tickets')['count'], 1)
        self.assertGreaterEqual(self.check('low_ratings')['count'], 1)

    def test_monitoring_is_for_managers_only(self):
        desk = self.env['res.users'].create({
            'name': 'Desk Mon', 'login': 'desk_mon',
            'groups_id': [(6, 0, [self.env.ref('club_management.group_club_staff').id])]})
        with self.assertRaises(AccessError):
            self.Dash.with_user(desk).get_monitoring()

    def test_dashboard_carries_ratings_and_open_tickets(self):
        self.env['club.feedback'].create_public('shop', 4)
        data = self.Dash.get_dashboard_data('all')
        self.assertGreaterEqual(data['ratings']['count'], 1)
        self.assertIn('open_tickets', data)

    def test_the_new_menus_exist(self):
        Menu = self.env['ir.ui.menu'].with_user(self.env.ref('base.user_admin'))
        names = Menu.browse(list(Menu._visible_menu_ids())).mapped('name')
        for expected in ('Feedback & Support', 'Support Tickets', 'Feedback & Ratings', 'Ratings Analysis',
                         'System Monitoring'):
            self.assertIn(expected, names)
