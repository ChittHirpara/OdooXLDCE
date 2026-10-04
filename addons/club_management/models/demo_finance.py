"""Demo data for the money side the owner asks about: employees and their leave, a paid payroll run,
business clients with invoices (some unpaid) and a couple of supplier bills. Safe to run again."""
import logging
from datetime import timedelta

from odoo import Command, api, models

from .booking import club_today

_logger = logging.getLogger(__name__)

# name, job, monthly salary
EMPLOYEES = [
    ('Meera Pillai', 'Front Desk Manager', 42000),
    ('Arjun Rao', 'Head Coach', 55000),
    ('Sunita Das', 'Bar Supervisor', 28000),
    ('Rohit Yadav', 'Groundskeeper', 22000),
    ('Farah Sheikh', 'Front Desk Executive', 26000),
    ('Deepak Nair', 'Pro-Shop Assistant', 24000),
]

# company, contact e-mail, [(product xmlid, description, qty, unit price, days ago, paid share 0..1)]
BUSINESS_CLIENTS = [
    ('Apex Tech Pvt Ltd', 'sports@apextech.example', [
        ('club_management.product_court_booking', 'Corporate court block: 20 hours', 20, 600, 24, 1.0),
    ]),
    ('Northwind Logistics', 'hr@northwind.example', [
        ('club_management.product_court_booking', 'Team-building day: 12 court hours', 12, 600, 15, 0.0),
    ]),
    ('Greenfield School', 'office@greenfield.example', [
        ('club_management.product_court_booking', 'Inter-house tennis meet: 8 court hours', 8, 600, 9, 0.5),
    ]),
    ('Zenith Finance Ltd', 'admin@zenith.example', [
        ('club_management.product_court_booking', 'Staff wellness sessions: 6 court hours', 6, 600, 2, 0.0),
    ]),
]

# supplier, reference, description, amount, days ago, paid
SUPPLIER_BILLS = [
    ('City Power Utility', 'EB-OCT-1187', 'Floodlight and clubhouse electricity', 18500, 12, False),
    ('Court Surface Works', 'CSW-2291', 'Hard court resurfacing, courts 1 and 2', 64000, 20, True),
    ('Fresh Farms Wholesale', 'FF-5530', 'Cafeteria supplies for the month', 21400, 4, False),
]


class ClubDemoFinance(models.AbstractModel):
    _inherit = 'club.demo'

    @api.model
    def load_finance_demo(self):
        """Employees, leave, payroll, business clients and supplier bills. Idempotent."""
        today = club_today()
        self.env['club.finance'].ensure_tax()
        for step in (self._demo_employees, self._demo_leave, self._demo_payroll, self._demo_business_clients,
                     self._demo_supplier_bills):
            try:
                with self.env.cr.savepoint():
                    step(today)
            except Exception:   # noqa: BLE001 - one missing piece must not stop the demo load
                _logger.exception("Demo finance step %s failed", step.__name__)

    def _demo_employees(self, today):
        Employee, Job = self.env['hr.employee'], self.env['hr.job']
        for name, job_name, salary in EMPLOYEES:
            if Employee.search_count([('name', '=', name)]):
                continue
            job = Job.search([('name', '=', job_name)], limit=1) or Job.create({'name': job_name})
            Employee.create({
                'name': name, 'job_id': job.id, 'job_title': job_name, 'club_monthly_salary': salary,
                'work_email': '%s@champions.example' % name.lower().replace(' ', '.')})

    def _demo_leave(self, today):
        Leave = self.env['hr.leave'].sudo().with_context(leave_skip_state_check=True, mail_notrack=True)
        # next Monday on, so they are working days
        monday = today + timedelta(days=(7 - today.weekday()) % 7 or 7)
        plans = [('Rohit Yadav', 'hr_holidays.holiday_status_sl', -10, 1, True),
                 ('Sunita Das', 'hr_holidays.holiday_status_unpaid', 7, 2, False),
                 ('Farah Sheikh', 'hr_holidays.holiday_status_unpaid', 14, 3, False)]
        for name, type_xmlid, offset, days, approve in plans:
            employee = self.env['hr.employee'].search([('name', '=', name)], limit=1)
            if not employee or Leave.search_count([('employee_id', '=', employee.id)]):
                continue
            start = monday + timedelta(days=offset)
            while start.weekday() > 4:
                start += timedelta(days=1)
            leave = Leave.create({
                'employee_id': employee.id, 'holiday_status_id': self.env.ref(type_xmlid).id,
                'request_date_from': start, 'request_date_to': start + timedelta(days=days - 1)})
            if approve:
                leave.action_approve()
                if leave.state == 'validate1':
                    leave.action_validate()

    def _demo_payroll(self, today):
        Run = self.env['club.payroll.run']
        last_month = (today.replace(day=1) - timedelta(days=1)).replace(day=1)
        if not Run.search_count([('month', '=', last_month)]):
            run = Run.create({'month': last_month})
            run.action_compute()
            run.action_post()
            run.action_pay()
        if not Run.search_count([('month', '=', today.replace(day=1))]):
            Run.create({'month': today.replace(day=1)}).action_compute()

    def _demo_business_clients(self, today):
        Partner, Move = self.env['res.partner'], self.env['account.move']
        for company, email, lines in BUSINESS_CLIENTS:
            if Partner.search_count([('name', '=', company), ('is_company', '=', True)]):
                continue
            partner = Partner.create({'name': company, 'is_company': True, 'email': email, 'customer_rank': 1})
            for xmlid, label, qty, price, days_ago, paid_share in lines:
                product = self.env.ref(xmlid)
                day = today - timedelta(days=days_ago)
                move = Move.create({
                    'move_type': 'out_invoice', 'partner_id': partner.id, 'invoice_date': day,
                    'invoice_date_due': day + timedelta(days=7), 'club_source': 'court',
                    'invoice_line_ids': [Command.create({
                        'product_id': product.id, 'name': label, 'quantity': qty, 'price_unit': price})]})
                move.action_post()
                if paid_share:
                    self._pay(move, move.amount_total * paid_share, day + timedelta(days=3), 'Bank transfer')

    def _demo_supplier_bills(self, today):
        Move = self.env['account.move']
        account = self.env['account.account'].search(
            [('company_id', '=', self.env.company.id), ('account_type', '=', 'expense')], order='code', limit=1)
        for supplier, ref, label, amount, days_ago, paid in SUPPLIER_BILLS:
            if Move.search_count([('ref', '=', ref), ('move_type', '=', 'in_invoice')]):
                continue
            partner = self.env['res.partner'].search([('name', '=', supplier)], limit=1) \
                or self.env['res.partner'].create({'name': supplier, 'supplier_rank': 1})
            day = today - timedelta(days=days_ago)
            bill = Move.create({
                'move_type': 'in_invoice', 'partner_id': partner.id, 'ref': ref, 'invoice_date': day,
                'invoice_date_due': day + timedelta(days=15),
                'invoice_line_ids': [Command.create({
                    'name': label, 'quantity': 1, 'price_unit': amount, 'account_id': account.id,
                    'tax_ids': [Command.clear()]})]})
            bill.action_post()
            if paid:
                self._pay(bill, amount, day + timedelta(days=5), 'Bank transfer')

    def _pay(self, move, amount, day, memo):
        journal = self.env['account.journal'].search(
            [('company_id', '=', move.company_id.id), ('type', '=', 'bank')], limit=1)
        if journal and move.state == 'posted':
            self.env['account.payment.register'].with_context(
                active_model='account.move', active_ids=move.ids).create({
                    'journal_id': journal.id, 'amount': amount, 'payment_date': day, 'communication': memo,
            })._create_payments()
