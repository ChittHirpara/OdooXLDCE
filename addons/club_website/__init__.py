from . import models
from . import controllers


def post_init(env):
    """Odoo copies a module's menus into every website's own menu tree when they are created
    under the template menu, but it does not touch the copy of Odoo's default "Contact us"
    that each website already has. Point those at the club's contact page."""
    env['website.menu'].search([('url', '=', '/contactus')]).write({
        'name': 'Contact', 'url': '/contact', 'page_id': False})
