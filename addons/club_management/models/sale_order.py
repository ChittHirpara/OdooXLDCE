from odoo import models


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    def _club_is_membership_quote(self):
        """True for a quotation raised from a club enquiry for the plan the lead asked about."""
        self.ensure_one()
        lead = self.opportunity_id
        plan = lead.interested_plan_id
        return bool(plan and plan.product_id and plan.product_id in self.order_line.product_id)

    def action_confirm(self):
        """Customer accepts the membership quote -> the lead is won -> the member is created."""
        res = super().action_confirm()
        for order in self.filtered('opportunity_id'):
            if order._club_is_membership_quote():
                order.opportunity_id.action_set_won()
        return res

    def action_quotation_sent(self):
        res = super().action_quotation_sent()
        for order in self.filtered('opportunity_id'):
            order.opportunity_id._club_advance_to('club_management.stage_quote_sent')
        return res
