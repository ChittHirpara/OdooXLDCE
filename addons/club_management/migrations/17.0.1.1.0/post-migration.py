from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    """Existing databases: create the tier pricelists and give them to active members."""
    env = api.Environment(cr, SUPERUSER_ID, {})
    env['club.membership.plan'].with_context(active_test=False).search([])._sync_pricelist()
    env['res.partner'].search([('is_member', '=', True)])._sync_club_pricelist()
