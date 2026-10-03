from unittest.mock import patch

from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.addons.club_management.models.res_company import PARAM_RUPEES_CHECKED
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install', 'club_management')
class TestRupees(TransactionCase):
    """The club trades in rupees. The switch happens once, as the module installs, only for
    the club's own (main) company, and only where Odoo allows it (no accounting entries)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.rupee = cls.env.ref('base.INR')
        cls.dollar = cls.env.ref('base.USD')
        cls.Company = cls.env['res.company']

    def _usd_company(self, name='Dollar Co'):
        company = self.Company.create({'name': name, 'currency_id': self.dollar.id})
        pricelist = self.env['product.pricelist'].create({
            'name': name + ' prices', 'currency_id': self.dollar.id, 'company_id': company.id})
        return company, pricelist

    def test_an_empty_company_is_switched_and_its_pricelists_follow(self):
        company, pricelist = self._usd_company()
        self.Company._club_use_rupees(company)
        self.assertEqual(company.currency_id, self.rupee)
        self.assertEqual(pricelist.currency_id, self.rupee)
        self.assertTrue(self.rupee.active)

    def test_other_companies_are_never_touched_by_the_install_check(self):
        """Odoo's demo adds a second company: converting it would strand the club's shared
        pricelists in a currency the club does not use."""
        other, pricelist = self._usd_company('Other Co')
        self.Company._club_use_rupees()                      # what the install runs: main company only
        self.assertEqual(other.currency_id, self.dollar)
        self.assertEqual(pricelist.currency_id, self.dollar)

    def test_the_club_pricelists_always_match_the_main_company_currency(self):
        currency = self.env.ref('base.main_company').currency_id
        for plan in self.env['club.membership.plan'].search([]):
            self.assertEqual(plan.pricelist_id.currency_id, currency)
        self.assertEqual(self.env.ref('club_management.pricelist_standard').currency_id, currency)

    def test_the_check_runs_once(self):
        params = self.env['ir.config_parameter'].sudo()
        with patch.object(type(self.Company), '_club_use_rupees') as check:
            params.set_param(PARAM_RUPEES_CHECKED, '1')
            self.Company._register_hook()
            check.assert_not_called()
            params.set_param(PARAM_RUPEES_CHECKED, '')
            self.Company._register_hook()
            check.assert_called_once()
            self.assertEqual(params.get_param(PARAM_RUPEES_CHECKED), '1')

    def test_a_company_already_in_rupees_is_untouched(self):
        company = self.Company.create({'name': 'Rupee Co', 'currency_id': self.rupee.id})
        self.Company._club_use_rupees(company)
        self.assertEqual(company.currency_id, self.rupee)

    def test_pos_configs_in_another_currency_do_not_get_the_club_tiers(self):
        """A second company in a different currency must not be offered the club pricelists
        (POS rejects mixed currencies)."""
        main = self.env.ref('base.main_company')
        other_currency = self.dollar if main.currency_id != self.dollar else self.rupee
        company = self.Company.create({'name': 'Other Currency POS Co', 'currency_id': other_currency.id})
        config = self.env['pos.config'].with_company(company).create({'name': 'Other POS', 'company_id': company.id})
        config._enable_club_pricelists()                         # must not raise
        club = self.env['club.membership.plan'].search([]).pricelist_id
        self.assertFalse(club & config.available_pricelist_ids)


@tagged('post_install', '-at_install', 'club_management')
class TestRupeesWithAccounting(AccountTestInvoicingCommon):

    def test_a_company_with_accounting_entries_keeps_its_currency(self):
        company = self.company_data['company']
        invoice = self.init_invoice('out_invoice', products=self.product_a, invoice_date='2026-10-01', post=True)
        self.assertTrue(invoice.line_ids)
        before = company.currency_id
        self.env['res.company']._club_use_rupees(company)
        self.assertEqual(company.currency_id, before)
