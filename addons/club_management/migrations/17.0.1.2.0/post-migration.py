from odoo import SUPERUSER_ID, api

# The "Annual Fee" field was added with a default of 5000 for every plan, so existing
# databases show the same fee on Gold, Silver and Junior. Give Silver and Junior their
# intended fee, but only where nobody has changed it yet.
INTENDED_FEES = {'silver': 3000.0, 'junior': 1500.0}


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    for code, fee in INTENDED_FEES.items():
        env['club.membership.plan'].with_context(active_test=False).search(
            [('code', '=', code), ('price', '=', 5000.0)]).write({'price': fee})
