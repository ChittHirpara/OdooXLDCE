from datetime import timedelta

from odoo import Command, http
from odoo.exceptions import AccessError, UserError
from odoo.tests import HttpCase, TransactionCase, tagged

from ..models.booking import club_today


@tagged('post_install', '-at_install', 'club_management')
class TestTaxAndPayroll(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Finance = cls.env['club.finance']
        cls.tax = cls.Finance.ensure_tax()

    def need_tax(self):
        if not self.tax:
            self.skipTest("no chart of accounts in this database")

    def test_the_club_gst_is_included_in_the_prices_and_on_club_products(self):
        self.need_tax()
        self.assertTrue(self.tax.price_include)
        self.assertEqual(self.tax.amount, 18)
        court = self.env.ref('club_management.product_court_booking')
        self.assertIn(self.tax, court.taxes_id)
        self.assertIn(self.tax, self.env.ref('club_management.plan_gold').product_id.taxes_id)
        self.assertEqual(self.Finance.ensure_tax(), self.tax, "running it again changes nothing")

    def test_an_invoice_shows_the_tax_inside_an_unchanged_total(self):
        self.need_tax()
        court = self.env.ref('club_management.product_court_booking')
        move = self.env['account.move'].create({
            'move_type': 'out_invoice', 'partner_id': self.env.ref('club_management.partner_walkin').id,
            'invoice_line_ids': [Command.create({'product_id': court.id, 'quantity': 1, 'price_unit': 590})]})
        self.assertEqual(move.amount_total, 590)
        self.assertAlmostEqual(move.amount_tax, 590 * 18 / 118, places=2)

    def test_tax_collected_counts_posted_sales_and_credit_notes_reduce_it(self):
        self.need_tax()
        court = self.env.ref('club_management.product_court_booking')
        before = self.Finance.tax_collected()['amount']
        today = club_today()
        before_today = self.Finance.tax_collected(today, today)['amount']
        move = self.env['account.move'].create({
            'move_type': 'out_invoice', 'partner_id': self.env.ref('club_management.partner_walkin').id,
            'invoice_line_ids': [Command.create({'product_id': court.id, 'quantity': 2, 'price_unit': 590})]})
        self.assertEqual(self.Finance.tax_collected()['amount'], before, "a draft invoice is not reported")
        move.action_post()
        self.assertAlmostEqual(self.Finance.tax_collected()['amount'] - before, 1180 * 18 / 118, places=2)
        self.assertAlmostEqual(self.Finance.tax_collected(today, today)['amount'] - before_today, 1180 * 18 / 118, places=2)

    def _employee(self, name='Pay Person', salary=30000):
        return self.env['hr.employee'].create({'name': name, 'club_monthly_salary': salary})

    def test_a_payroll_run_raises_bills_that_are_owed_and_then_paid(self):
        employee = self._employee()
        owed_before = self.Finance.payables()['salaries']
        run = self.env['club.payroll.run'].create({'month': '2030-01-15'})
        self.assertEqual(run.month.day, 1)
        self.assertEqual(run.name, 'Payroll January 2030')
        run.action_compute()
        self.assertIn(employee, run.line_ids.employee_id)
        run.action_post()
        self.assertEqual(run.state, 'posted')
        bill = run.line_ids.filtered(lambda l: l.employee_id == employee).bill_id
        self.assertEqual((bill.state, bill.amount_total), ('posted', 30000))
        self.assertGreaterEqual(self.Finance.payables()['salaries'] - owed_before, 30000)
        run.action_pay()
        self.assertEqual(run.state, 'paid')
        self.assertEqual(bill.payment_state, 'paid')
        self.assertEqual(self.Finance.payables()['salaries'], owed_before)

    def test_one_run_per_month_and_nothing_to_pay_is_explained(self):
        self.env['club.payroll.run'].create({'month': '2030-02-01'})
        with self.assertRaises(Exception):
            with self.env.cr.savepoint():
                self.env['club.payroll.run'].create({'month': '2030-02-20'})
        self.env['hr.employee'].search([('club_monthly_salary', '>', 0)]).write({'club_monthly_salary': 0})
        empty = self.env['club.payroll.run'].create({'month': '2030-03-01'})
        with self.assertRaisesRegex(UserError, 'monthly salary'):
            empty.action_post()

    def test_managers_can_approve_leave_and_see_employees(self):
        manager = self.env.ref('club_management.group_club_manager')
        self.assertIn(self.env.ref('hr_holidays.group_hr_holidays_user'), manager.trans_implied_ids)
        self.assertIn(self.env.ref('hr.group_hr_user'), manager.trans_implied_ids)

    def test_the_salary_is_for_managers_only(self):
        field = self.env['hr.employee']._fields['club_monthly_salary']
        self.assertEqual(field.groups, 'club_management.group_club_manager')


@tagged('post_install', '-at_install', 'club_management')
class TestOwnerMoney(TransactionCase):

    def test_the_dashboard_has_the_money_block(self):
        money = self.env['club.dashboard'].get_dashboard_data('all')['money']
        for key in ('tax_collected', 'owed_bills', 'owed_salaries', 'owed_total', 'business_billed',
                    'business_open', 'payroll_total', 'payroll_state', 'employees', 'pending_leave'):
            self.assertIn(key, money)
        self.assertAlmostEqual(money['owed_total'], money['owed_bills'] + money['owed_salaries'])

    def test_unpaid_supplier_bills_are_what_we_owe(self):
        account = self.env['account.account'].search([('account_type', '=', 'expense')], limit=1)
        if not account:
            self.skipTest("no chart of accounts")
        before = self.env['club.dashboard'].get_dashboard_data('all')['money']['owed_bills']
        bill = self.env['account.move'].create({
            'move_type': 'in_invoice', 'partner_id': self.env['res.partner'].create({'name': 'Test Supplier'}).id,
            'invoice_date': club_today(), 'ref': 'TS-1',
            'invoice_line_ids': [Command.create({'name': 'Balls', 'quantity': 1, 'price_unit': 5000,
                                                 'account_id': account.id, 'tax_ids': [Command.clear()]})]})
        bill.action_post()
        after = self.env['club.dashboard'].get_dashboard_data('all')['money']['owed_bills']
        self.assertAlmostEqual(after - before, 5000)

    def test_business_clients_are_companies_with_their_own_totals(self):
        court = self.env.ref('club_management.product_court_booking')
        company = self.env['res.partner'].create({'name': 'Test Co', 'is_company': True})
        before = self.env['club.dashboard'].get_dashboard_data('all')['money']
        move = self.env['account.move'].create({
            'move_type': 'out_invoice', 'partner_id': company.id, 'invoice_date': club_today(),
            'invoice_line_ids': [Command.create({'product_id': court.id, 'quantity': 4, 'price_unit': 500})]})
        move.action_post()
        after = self.env['club.dashboard'].get_dashboard_data('all')['money']
        self.assertAlmostEqual(after['business_billed'] - before['business_billed'], 2000)
        self.assertAlmostEqual(after['business_open'] - before['business_open'], 2000)

    def test_the_numbers_can_be_shared_as_rows_and_by_email(self):
        dashboard = self.env['club.dashboard']
        rows = dashboard.report_rows('month')
        self.assertIn(('Owed', 'Total we owe'), [(a, b) for a, b, _c in rows])
        self.assertTrue(all(isinstance(value, str) for _a, _b, value in rows))
        self.assertEqual(dashboard.email_report('month', 'Owner@Example.com'), 'owner@example.com')
        with self.assertRaisesRegex(UserError, 'valid e-mail'):
            dashboard.email_report('month', 'not an address')

    def test_only_managers_can_share_the_numbers(self):
        staff = self.env['res.users'].create({
            'name': 'Desk Only', 'login': 'desk.only@example.com',
            'groups_id': [Command.set([self.env.ref('club_management.group_club_staff').id])]})
        with self.assertRaises(AccessError):
            self.env['club.dashboard'].with_user(staff).report_rows('month')
        with self.assertRaises(AccessError):
            self.env['club.dashboard'].with_user(staff).email_report('month', 'x@example.com')


@tagged('post_install', '-at_install', 'club_management')
class TestReportDownload(HttpCase):

    def test_a_manager_downloads_the_csv_and_others_cannot(self):
        self.authenticate('admin', 'admin')
        response = self.url_open('/club/report.csv?period=month')
        self.assertEqual(response.status_code, 200)
        self.assertIn('text/csv', response.headers['Content-Type'])
        self.assertIn('attachment', response.headers['Content-Disposition'])
        self.assertTrue(response.text.startswith('Section,Measure,Value'))
        self.assertIn('Total we owe', response.text)
        self.env['res.users'].create({
            'name': 'Portal Pat', 'login': 'portal.pat.csv@example.com', 'password': 'portal-pat-pw-1',
            'groups_id': [Command.set([self.env.ref('base.group_portal').id])]})
        self.authenticate('portal.pat.csv@example.com', 'portal-pat-pw-1')
        self.assertEqual(self.url_open('/club/report.csv').status_code, 404)


@tagged('post_install', '-at_install', 'club_management')
class TestMemberLookup(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Lookup = cls.env['club.member.lookup']
        cls.gold = cls.env.ref('club_management.plan_gold')
        cls.member = cls.env['res.partner'].create({
            'name': 'Lookup Lena', 'email': 'lookup.lena@example.com', 'phone': '9000011111',
            'is_member': True, 'plan_id': cls.gold.id,
            'join_date': club_today() - timedelta(days=30), 'expiry_date': club_today() + timedelta(days=5)})

    def test_a_scanned_member_id_finds_exactly_that_member(self):
        result = self.Lookup.find(self.member.member_id.lower())
        self.assertEqual(result['member']['name'], 'Lookup Lena')
        self.assertEqual(result['matches'], [])

    def test_a_name_gives_the_member_or_a_short_list(self):
        self.assertEqual(self.Lookup.find('Lookup Le')['member']['id'], self.member.id)
        self.env['res.partner'].create({'name': 'Lookup Liam', 'is_member': True, 'plan_id': self.gold.id,
                                        'expiry_date': club_today() + timedelta(days=90)})
        result = self.Lookup.find('Lookup L')
        self.assertIsNone(result['member'])
        self.assertEqual(len(result['matches']), 2)
        self.assertEqual(self.Lookup.find('x'), {'member': None, 'matches': []})

    def test_the_profile_shows_the_plan_history_and_warnings(self):
        court = self.env['club.court'].search([], limit=1)
        booking = self.env['club.booking'].create({
            'court_id': court.id, 'partner_id': self.member.id,
            'start_datetime': self._utc(club_today() + timedelta(days=2), 9)})
        booking.action_confirm()
        profile = self.Lookup.profile(self.member.id)
        self.assertEqual((profile['plan'], profile['status']), ('Gold', 'active'))
        self.assertEqual(profile['days_left'], 5)
        self.assertTrue(any('ends in 5 days' in a['text'] for a in profile['alerts']))
        self.assertEqual(len(profile['upcoming']), 1)
        self.assertEqual(profile['upcoming'][0]['court'], court.name)

    def _utc(self, day, hour):
        import pytz
        from datetime import datetime
        local = pytz.timezone('Asia/Kolkata').localize(datetime(day.year, day.month, day.day, hour))
        return local.astimezone(pytz.utc).replace(tzinfo=None)

    def test_an_expired_member_is_flagged(self):
        lapsed = self.env['res.partner'].create({
            'name': 'Lapsed Lou', 'is_member': True, 'plan_id': self.gold.id,
            'join_date': '2020-01-01', 'expiry_date': '2020-12-31'})
        profile = self.Lookup.profile(lapsed.id)
        self.assertEqual(profile['status'], 'expired')
        self.assertEqual(profile['plan'], 'Guest')
        self.assertTrue(any(a['level'] == 'danger' for a in profile['alerts']))

    def test_check_in_is_counted_and_noted(self):
        self.Lookup.check_in(self.member.id)
        profile = self.Lookup.check_in(self.member.id)
        self.assertEqual(profile['check_in_count'], 2)
        self.assertTrue(profile['last_check_in'])
        self.assertTrue(any('Checked in at the front desk' in (m.body or '') for m in self.member.message_ids))

    def test_only_staff_can_look_people_up_and_only_members(self):
        outsider = self.env['res.users'].create({
            'name': 'Not Staff', 'login': 'not.staff@example.com',
            'groups_id': [Command.set([self.env.ref('base.group_user').id])]})
        with self.assertRaises(AccessError):
            self.Lookup.with_user(outsider).find('Lookup')
        with self.assertRaises(UserError):
            self.Lookup.profile(self.env.ref('club_management.partner_walkin').id)


@tagged('post_install', '-at_install', 'club_management')
class TestFinanceDemo(TransactionCase):

    def test_the_demo_loader_is_safe_to_run_twice(self):
        demo = self.env['club.demo']
        demo.load_finance_demo()
        employees = self.env['hr.employee'].search_count([])
        invoices = self.env['account.move'].search_count([])
        runs = self.env['club.payroll.run'].search_count([])
        demo.load_finance_demo()
        self.assertEqual(self.env['hr.employee'].search_count([]), employees)
        self.assertEqual(self.env['account.move'].search_count([]), invoices)
        self.assertEqual(self.env['club.payroll.run'].search_count([]), runs)
        self.assertTrue(self.env['res.partner'].search([('name', '=', 'Apex Tech Pvt Ltd'), ('is_company', '=', True)]))
        self.assertTrue(self.env['hr.employee'].search([('name', '=', 'Meera Pillai')]))
