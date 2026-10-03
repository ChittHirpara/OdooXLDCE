from odoo import api, fields, models


class ClubOrder(models.Model):
    """A completed Bar & Cafeteria tab or Pro-Shop order taken through the club screens."""
    _name = 'club.order'
    _description = 'Club Bar / Shop Order'
    _order = 'id desc'

    name = fields.Char(default='New', copy=False, readonly=True)
    channel = fields.Selection(
        [('bar', 'Bar & Cafeteria'), ('shop', 'Pro-Shop')], required=True, readonly=True)
    partner_id = fields.Many2one('res.partner', string='Member / Customer', readonly=True)
    customer_name = fields.Char(readonly=True)
    plan_id = fields.Many2one('club.membership.plan', string='Tier Applied', readonly=True,
                              help="Membership plan whose discount was applied, if any.")
    table_id = fields.Many2one('club.pos.table', readonly=True)
    payment_method = fields.Selection(
        [('cash', 'Cash'), ('card', 'Card'), ('upi', 'UPI')], readonly=True)
    fulfillment = fields.Char(readonly=True)
    delivery_address = fields.Char(readonly=True)
    state = fields.Selection([('paid', 'Paid')], default='paid', readonly=True)
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company, required=True)
    currency_id = fields.Many2one(related='company_id.currency_id')
    line_ids = fields.One2many('club.order.line', 'order_id', readonly=True)
    subtotal = fields.Monetary(compute='_compute_totals', store=True)
    discount = fields.Monetary(compute='_compute_totals', store=True)
    total = fields.Monetary(compute='_compute_totals', store=True)

    @api.depends('line_ids.list_price', 'line_ids.unit_price', 'line_ids.qty')
    def _compute_totals(self):
        for order in self:
            order.subtotal = sum(line.list_price * line.qty for line in order.line_ids)
            order.total = sum(line.unit_price * line.qty for line in order.line_ids)
            order.discount = order.subtotal - order.total

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('club.order') or 'New'
        return super().create(vals_list)


class ClubOrderLine(models.Model):
    _name = 'club.order.line'
    _description = 'Club Order Line'

    order_id = fields.Many2one('club.order', required=True, ondelete='cascade')
    product_id = fields.Many2one('product.product', required=True)
    qty = fields.Integer(required=True, default=1)
    currency_id = fields.Many2one(related='order_id.currency_id')
    list_price = fields.Monetary(help="Unit price before any member discount.")
    unit_price = fields.Monetary(help="Unit price actually charged.")
    line_total = fields.Monetary(compute='_compute_line_total', store=True)

    _sql_constraints = [
        ('qty_positive', 'CHECK(qty > 0)', 'Order quantity must be at least 1.'),
    ]

    @api.depends('unit_price', 'qty')
    def _compute_line_total(self):
        for line in self:
            line.line_total = line.unit_price * line.qty
