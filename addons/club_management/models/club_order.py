import logging

from odoo import Command, api, fields, models

_logger = logging.getLogger(__name__)


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
    customer_phone = fields.Char(readonly=True)
    customer_email = fields.Char(readonly=True)
    source = fields.Selection(
        [('staff', 'Front desk / screens'), ('website', 'Website')], default='staff', readonly=True)
    access_token = fields.Char(copy=False, readonly=True, index=True,
                               help="Secret in the visitor's order link.")
    state = fields.Selection([('paid', 'Paid')], default='paid', readonly=True)
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company, required=True)
    currency_id = fields.Many2one(related='company_id.currency_id')
    line_ids = fields.One2many('club.order.line', 'order_id', readonly=True)
    invoice_id = fields.Many2one('account.move', string='Invoice', copy=False, readonly=True)
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

    @api.model
    def get_by_token(self, token):
        token = (token or '').strip()
        return self.sudo().search([('access_token', '=', token)], limit=1) if len(token) >= 16 else self.browse()

    def _create_invoice(self):
        """Post a customer invoice for the order and register the payment already taken.

        Accounting must never block a sale at the till, so a failure (for example a company
        without a chart of accounts) is logged and the order simply stays without an invoice.
        """
        walkin = self.env.ref('club_management.partner_walkin', raise_if_not_found=False)
        for order in self.filtered(lambda o: not o.invoice_id and o.line_ids):
            try:
                with self.env.cr.savepoint():
                    move = self.env['account.move'].with_company(order.company_id).create({
                        'move_type': 'out_invoice',
                        'club_source': order.channel,
                        'partner_id': (order.partner_id or walkin).id,
                        'invoice_origin': order.name,
                        'invoice_line_ids': [Command.create({
                            'product_id': line.product_id.id,
                            'quantity': line.qty,
                            'price_unit': line.unit_price,
                        }) for line in order.line_ids],
                    })
                    move.action_post()
                    order.invoice_id = move
                    order._register_payment(move)
            except Exception:  # noqa: BLE001 - see docstring
                _logger.exception("Could not invoice club order %s", order.name)

    def _register_payment(self, move):
        journal_type = 'cash' if self.payment_method == 'cash' else 'bank'
        journal = self.env['account.journal'].search(
            [('company_id', '=', self.company_id.id), ('type', '=', journal_type)], limit=1)
        if journal and move.state == 'posted':
            self.env['account.payment.register'].with_context(
                active_model='account.move', active_ids=move.ids,
            ).create({'journal_id': journal.id})._create_payments()

    def _send_confirmation(self):
        template = self.env.ref('club_management.mail_template_order_confirmed', raise_if_not_found=False)
        for order in self:
            if template and (order.partner_id.email or order.customer_email):
                template.sudo().send_mail(order.id)


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
