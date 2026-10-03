from odoo import Command, api, models


class PosConfig(models.Model):
    _inherit = 'pos.config'

    @api.model_create_multi
    def create(self, vals_list):
        configs = super().create(vals_list)
        configs._enable_club_pricelists()
        return configs

    def _enable_club_pricelists(self):
        """Make the tier pricelists available in the POS so that choosing a
        member as customer applies their bar/shop discount."""
        club = self.env['club.membership.plan'].sudo().with_context(
            active_test=False).search([]).pricelist_id
        if not club:
            return
        standard = self.env.ref('club_management.pricelist_standard', raise_if_not_found=False)
        for config in self.sudo():
            base = config.pricelist_id or standard or self.env['product.pricelist']
            wanted = config.available_pricelist_ids | club | base
            if config.use_pricelist and config.available_pricelist_ids == wanted:
                continue
            # Full-set command: pos.config rejects 'link' commands while a session is open.
            config.write({
                'use_pricelist': True,
                'pricelist_id': base.id or False,
                'available_pricelist_ids': [Command.set(wanted.ids)],
            })
