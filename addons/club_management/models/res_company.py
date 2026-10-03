import logging

from odoo import models

_logger = logging.getLogger(__name__)

PARAM_RUPEES_CHECKED = 'club_management.rupees_checked'


class ResCompany(models.Model):
    _inherit = 'res.company'

    def _register_hook(self):
        super()._register_hook()
        params = self.env['ir.config_parameter'].sudo()
        if not params.get_param(PARAM_RUPEES_CHECKED):
            self._club_use_rupees()
            params.set_param(PARAM_RUPEES_CHECKED, '1')

    def _club_use_rupees(self, companies=None):
        """The club trades in rupees: switch the club's company to INR, once, as the module installs.

        Only the main company is the club (``companies`` exists for tests). Other companies in
        a multi-company database are never touched: the club's pricelists are shared, so
        converting a different company would leave them in a currency the club does not use.

        This runs at the end of the first registry load, not in an install hook, because
        Odoo loads the chart of accounts after all modules are installed and the chart loader
        resets the company currency to its fiscal country's (USD for a US address).

        Odoo only lets a company change currency while it has no accounting entries, so a
        company that already has some (for example from Odoo's accounting demo data) is left
        alone with a warning; scripts/create_demo_db.sh builds a database that avoids that.
        It runs once, so an administrator who later picks another currency is not overridden.
        """
        rupee = self.env.ref('base.INR')
        for company in (companies or self.env.ref('base.main_company')).sudo():
            old = company.currency_id
            if old == rupee:
                continue
            if self.env['account.move.line'].sudo().search_count([('company_id', '=', company.id)]):
                _logger.warning(
                    "Company %s already has accounting entries, so its currency stays %s. "
                    "Create the database with scripts/create_demo_db.sh to start in rupees.",
                    company.name, old.name)
                continue
            rupee.active = True
            # Pricelists take the currency of the company that was current when they were
            # created (dollars, for the club's own tier pricelists), and POS refuses to mix.
            pricelists = self.env['product.pricelist'].sudo().with_context(active_test=False).search([
                ('currency_id', '=', old.id), ('company_id', 'in', [company.id, False])])
            company.currency_id = rupee
            pricelists.write({'currency_id': rupee.id})
            _logger.info("Company %s now uses %s (%d pricelists converted).",
                         company.name, rupee.name, len(pricelists))
