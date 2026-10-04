import logging

from odoo import models

_logger = logging.getLogger(__name__)


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    def _club_is_membership_quote(self):
        """True for a quotation raised from a club enquiry for the plan the lead asked about."""
        self.ensure_one()
        lead = self.opportunity_id
        plan = lead.interested_plan_id
        return bool(plan and plan.product_id and plan.product_id in self.order_line.product_id)

    def _prepare_invoice(self):
        vals = super()._prepare_invoice()
        if self.opportunity_id and self._club_is_membership_quote():
            vals['club_source'] = 'membership'
        return vals

    def action_confirm(self):
        """Customer accepts the membership quote -> invoice raised -> lead won -> member created."""
        res = super().action_confirm()
        for order in self.filtered('opportunity_id'):
            if order._club_is_membership_quote():
                order._club_invoice_membership()
                order.opportunity_id.action_set_won()
        return res

    def _club_invoice_membership(self):
        """Post the membership invoice so it shows as revenue and, until paid, as outstanding.

        The membership starts on acceptance; a failure to invoice (no chart of accounts) is
        logged and must not undo the acceptance.
        """
        self.ensure_one()
        try:
            with self.env.cr.savepoint():
                invoices = self._create_invoices()
                invoices.action_post()
        except Exception:  # noqa: BLE001
            _logger.exception("Could not invoice membership quote %s", self.name)

    def action_quotation_sent(self):
        res = super().action_quotation_sent()
        for order in self.filtered('opportunity_id'):
            order.opportunity_id._club_advance_to('club_management.stage_quote_sent')
        return res
