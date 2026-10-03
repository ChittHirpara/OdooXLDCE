"""Server endpoints called by the OWL screens (static/src/components).

The screens call these models by name through ``orm.call``. They are thin: all rules live
in club.booking, club.order.service and the pricelists. Business errors are returned as
``{'success': False, 'message': ...}`` so the UI can show them.
"""
from odoo import api, models
from odoo.exceptions import AccessError, UserError, ValidationError

from .booking import to_club_time


def _message(error):
    if isinstance(error, AccessError):
        return "You do not have permission to do this."
    return error.args[0] if error.args else str(error)


class ClubPosProduct(models.AbstractModel):
    _name = 'club.pos.product'
    _description = 'Bar POS product feed'

    @api.model
    def get_products_data(self, category='all', search='', partner_id=None):
        return self.env['product.product'].get_bar_products(category, search, partner_id)


class ClubPosSession(models.AbstractModel):
    _name = 'club.pos.session'
    _description = 'Bar POS shift feed'

    @api.model
    def get_current_shift(self):
        return self.env['club.order.service'].current_shift()


class ClubPosOrder(models.AbstractModel):
    _name = 'club.pos.order'
    _description = 'Bar POS pricing and payment'

    @api.model
    def calculate_order_pricing(self, items, plan_code='none', partner_id=None):
        return self.env['club.order.service'].calculate_order_pricing(items, plan_code, partner_id)

    @api.model
    def get_recent_orders(self, limit=20):
        """Latest bar orders for the history tab."""
        orders = self.env['club.order'].search([('channel', '=', 'bar')], limit=int(limit))
        return [{
            'order_ref': o.name,
            'table': o.table_id.name or '-',
            'member': o.customer_name,
            'amount': "₹%s" % format(o.total, ',.2f'),
            'method': (o.payment_method or '').upper(),
            'status': 'Paid',
            'time': to_club_time(o.create_date).strftime('%d %b, %I:%M %p'),
        } for o in orders]

    @api.model
    def process_payment_api(self, vals):
        try:
            with self.env.cr.savepoint():
                return self.env['club.order.service'].process_pos_payment(vals)
        except (ValidationError, UserError, AccessError) as error:
            return {'success': False, 'message': _message(error)}


class ClubShopProduct(models.AbstractModel):
    _name = 'club.shop.product'
    _description = 'Pro-Shop catalog feed'

    @api.model
    def get_shop_catalog(self, category=None, search='', partner_id=None):
        return self.env['product.product'].get_shop_catalog(category, search, partner_id)


class ClubShopOrder(models.AbstractModel):
    _name = 'club.shop.order'
    _description = 'Pro-Shop checkout'

    @api.model
    def calculate_order_pricing(self, items, plan_code='none', partner_id=None):
        return self.env['club.order.service'].calculate_order_pricing(items, plan_code, partner_id)

    @api.model
    def place_order(self, vals):
        try:
            with self.env.cr.savepoint():
                return self.env['club.order.service'].process_shop_checkout(vals)
        except (ValidationError, UserError, AccessError) as error:
            return {'success': False, 'message': _message(error)}
