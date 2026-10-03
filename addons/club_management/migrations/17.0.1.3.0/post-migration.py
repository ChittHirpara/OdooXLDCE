from odoo import SUPERUSER_ID, api, tools


def migrate(cr, version):
    """Existing databases get the club CRM pipeline and a product for every plan.

    The pipeline file is noupdate, so a normal update would not rename Odoo's stock stages;
    load it explicitly.
    """
    env = api.Environment(cr, SUPERUSER_ID, {})
    tools.convert_file(env, 'club_management', 'data/crm_pipeline.xml', {}, mode='update',
                       noupdate=False, kind='data')
    env['club.membership.plan'].with_context(active_test=False).search([])._sync_product()
