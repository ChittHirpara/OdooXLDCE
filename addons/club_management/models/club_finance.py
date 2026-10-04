"""The money side beyond the till: GST on club sales, employee salaries and what the club owes.

* GST 18% is built into the club's prices (what the customer sees is what they pay), and every
  invoice shows the tax inside it, so the owner can report taxes without changing any price.
* A payroll run turns each employee's monthly salary into a vendor bill (what the club owes)
  and then pays them.
* ``club.dashboard`` reads all of it for the owner's "what do we owe" numbers.
"""
import logging
from datetime import timedelta

from odoo import Command, api, fields, models
from odoo.exceptions import UserError

from .booking import club_today

_logger = logging.getLogger(__name__)

TAX_NAME = 'GST 18% (included)'
TAX_RATE = 18.0


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    club_monthly_salary = fields.Monetary(
        string='Monthly Salary', currency_field='club_currency_id', groups='club_management.group_club_manager',
        help="Paid by the monthly payroll run (Club > Staff > Payroll).")
    club_currency_id = fields.Many2one(related='company_id.currency_id', string='Club Currency')


class ClubFinance(models.AbstractModel):
    _name = 'club.finance'
    _description = 'Club taxes and payables'

    # ------------------------------------------------------------------
    # GST
    # ------------------------------------------------------------------
    @api.model
    def ensure_tax(self):
        """Create the club's sales tax (once) and put it on every club product that has none.

        Prices already include it, so nothing a customer pays changes; invoices just show the tax
        inside the price. Does nothing on a database without a chart of accounts.
        """
        company = self.env.company
        Tax = self.env['account.tax'].sudo()
        tax = Tax.search([('name', '=', TAX_NAME), ('company_id', '=', company.id)], limit=1)
        if not tax:
            group = (Tax.search([('type_tax_use', '=', 'sale'), ('company_id', '=', company.id)], limit=1).tax_group_id
                     or self.env['account.tax.group'].sudo().search([], limit=1))
            if not group or not self.env['account.account'].sudo().search_count([('company_id', '=', company.id)]):
                _logger.info("No chart of accounts: the club GST tax was not created")
                return Tax
            tax = Tax.create({
                'name': TAX_NAME, 'description': 'GST 18%', 'amount_type': 'percent', 'amount': TAX_RATE,
                'type_tax_use': 'sale', 'price_include': True, 'tax_group_id': group.id,
                'company_id': company.id})
        self.apply_tax(self._club_products(), tax)
        return tax

    @api.model
    def _club_products(self):
        Product = self.env['product.product'].sudo().with_context(active_test=False)
        products = Product.browse()
        court = self.env.ref('club_management.product_court_booking', raise_if_not_found=False)
        if court:
            products |= court
        products |= self.env['club.membership.plan'].sudo().with_context(active_test=False).search([]).product_id
        for xmlid in ('club_management.product_category_shop', 'club_management.product_category_bar'):
            categ = self.env.ref(xmlid, raise_if_not_found=False)
            if categ:
                products |= Product.search([('categ_id', 'child_of', categ.id)])
        return products

    @api.model
    def apply_tax(self, products, tax=None):
        tax = tax or self.env['account.tax'].sudo().search(
            [('name', '=', TAX_NAME), ('company_id', '=', self.env.company.id)], limit=1)
        if not tax:
            return
        for product in products.sudo().filtered(lambda p: not p.taxes_id.filtered(lambda t: t.company_id == tax.company_id)):
            product.taxes_id = [Command.link(tax.id)]

    # ------------------------------------------------------------------
    # reading the books
    # ------------------------------------------------------------------
    @api.model
    def tax_collected(self, date_from=None, date_to=None):
        """GST on posted sales invoices between two dates (credit notes reduce it)."""
        domain = [('tax_line_id', '!=', False), ('parent_state', '=', 'posted'),
                  ('move_id.move_type', 'in', ('out_invoice', 'out_refund')),
                  ('tax_line_id.type_tax_use', '=', 'sale')]
        if date_from:
            domain += [('date', '>=', date_from), ('date', '<=', date_to or club_today())]
        lines = self.env['account.move.line'].sudo().search(domain)
        return {'amount': -sum(lines.mapped('balance')), 'lines': lines}

    @api.model
    def payables(self):
        """What the club owes: unpaid vendor bills (salaries are vendor bills too)."""
        bills = self.env['account.move'].sudo().search([
            ('move_type', '=', 'in_invoice'), ('state', '=', 'posted'),
            ('payment_state', 'in', ('not_paid', 'partial'))])
        salaries = bills.filtered(lambda b: b.ref and b.ref.startswith('Payroll'))
        return {'bills': sum((bills - salaries).mapped('amount_residual')),
                'salaries': sum(salaries.mapped('amount_residual')), 'count': len(bills)}


class ClubPayrollRun(models.Model):
    _name = 'club.payroll.run'
    _description = 'Monthly payroll run'
    _inherit = ['mail.thread']
    _order = 'month desc'

    name = fields.Char(compute='_compute_name', store=True)
    month = fields.Date(required=True, default=lambda s: club_today().replace(day=1),
                        help="Any day of the month being paid.")
    state = fields.Selection([('draft', 'Draft'), ('posted', 'Bills raised'), ('paid', 'Paid')],
                             default='draft', tracking=True)
    line_ids = fields.One2many('club.payroll.run.line', 'run_id')
    company_id = fields.Many2one('res.company', default=lambda s: s.env.company, required=True)
    currency_id = fields.Many2one(related='company_id.currency_id')
    total = fields.Monetary(compute='_compute_total', store=True)

    _sql_constraints = [('month_company_unique', 'unique(month, company_id)',
                         "There is already a payroll run for that month.")]

    @api.depends('month')
    def _compute_name(self):
        for run in self:
            run.name = "Payroll %s" % run.month.strftime('%B %Y') if run.month else "Payroll"

    @api.depends('line_ids.amount')
    def _compute_total(self):
        for run in self:
            run.total = sum(run.line_ids.mapped('amount'))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('month'):
                vals['month'] = fields.Date.to_date(vals['month']).replace(day=1)
        return super().create(vals_list)

    def action_compute(self):
        """List every active employee with a monthly salary."""
        for run in self:
            if run.state != 'draft':
                raise UserError("Only a draft payroll run can be recalculated.")
            employees = self.env['hr.employee'].sudo().search(
                [('company_id', '=', run.company_id.id), ('club_monthly_salary', '>', 0)])
            run.line_ids.unlink()
            run.line_ids = [Command.create({'employee_id': e.id, 'amount': e.club_monthly_salary}) for e in employees]
        return True

    def action_post(self):
        """Raise one vendor bill per employee: from now on the club owes the salaries."""
        for run in self:
            if run.state != 'draft':
                raise UserError("The bills for this run are already raised.")
            if not run.line_ids:
                run.action_compute()
            if not run.line_ids:
                raise UserError("No employee has a monthly salary yet. Set one on the employee form.")
            account = self.env['account.account'].sudo().search(
                [('company_id', '=', run.company_id.id), ('account_type', '=', 'expense')], order='code', limit=1)
            end = (run.month.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
            for line in run.line_ids:
                line._raise_bill(account, end)
            run.state = 'posted'
            run.message_post(body="%d salary bills raised, %s in total." % (len(run.line_ids), run.total))
        return True

    def action_pay(self):
        """Pay every salary bill from the bank."""
        for run in self:
            if run.state != 'posted':
                raise UserError("Raise the salary bills first.")
            bills = run.line_ids.bill_id.filtered(lambda b: b.payment_state in ('not_paid', 'partial'))
            if bills:
                journal = self.env['account.journal'].sudo().search(
                    [('company_id', '=', run.company_id.id), ('type', '=', 'bank')], limit=1)
                if not journal:
                    raise UserError("There is no bank journal to pay from.")
                self.env['account.payment.register'].sudo().with_context(
                    active_model='account.move', active_ids=bills.ids).create({
                        'journal_id': journal.id, 'communication': run.name, 'group_payment': False,
                }).action_create_payments()
            run.state = 'paid'
            run.message_post(body="Salaries paid.")
        return True


class ClubPayrollRunLine(models.Model):
    _name = 'club.payroll.run.line'
    _description = 'Payroll run line'

    run_id = fields.Many2one('club.payroll.run', required=True, ondelete='cascade')
    employee_id = fields.Many2one('hr.employee', required=True)
    currency_id = fields.Many2one(related='run_id.currency_id')
    amount = fields.Monetary(required=True)
    bill_id = fields.Many2one('account.move', string='Salary Bill', readonly=True, copy=False)
    payment_state = fields.Selection(related='bill_id.payment_state', string='Payment')

    def _raise_bill(self, account, bill_date):
        self.ensure_one()
        employee = self.employee_id.sudo()
        partner = employee.work_contact_id
        if not partner:
            partner = self.env['res.partner'].sudo().create({'name': employee.name, 'email': employee.work_email or False})
            employee.work_contact_id = partner
        label = "Salary %s - %s" % (self.run_id.month.strftime('%B %Y'), employee.name)
        move = self.env['account.move'].sudo().with_company(self.run_id.company_id).create({
            'move_type': 'in_invoice', 'partner_id': partner.id, 'invoice_date': bill_date,
            'ref': "Payroll %s" % self.run_id.month.strftime('%Y-%m'),
            'invoice_line_ids': [Command.create({'name': label, 'quantity': 1, 'price_unit': self.amount,
                                                 'account_id': account.id, 'tax_ids': [Command.clear()]})]})
        move.action_post()
        self.bill_id = move
