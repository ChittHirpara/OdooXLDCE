"""Front-desk member lookup: type or scan a member ID (the QR on the card holds it), or search by
name, e-mail or phone, and see who they are, what their plan gives them and their history with the club."""
from datetime import timedelta

from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError

from .booking import club_today, to_club_time

MAX_MATCHES = 8
EXPIRY_WARNING_DAYS = 14


class ResPartner(models.Model):
    _inherit = 'res.partner'

    last_check_in = fields.Datetime(string='Last Check-in', copy=False, readonly=True)
    check_in_count = fields.Integer(string='Check-ins', copy=False, readonly=True)


class ClubMemberLookup(models.AbstractModel):
    _name = 'club.member.lookup'
    _description = 'Front-desk member lookup'

    @api.model
    def _require_staff(self):
        if not self.env.user.has_group('club_management.group_club_staff'):
            raise AccessError("Only club staff can look members up.")

    @api.model
    def find(self, query):
        """A scanned/typed member ID gives that member; anything else lists the people who match."""
        self._require_staff()
        query = (query or '').strip()
        if len(query) < 2:
            return {'member': None, 'matches': []}
        Partner = self.env['res.partner'].sudo()
        exact = Partner.search([('is_member', '=', True), ('member_id', '=ilike', query)], limit=1)
        if exact:
            return {'member': self.profile(exact.id), 'matches': []}
        matches = Partner.search([
            ('is_member', '=', True), '|', '|', '|',
            ('name', 'ilike', query), ('email', 'ilike', query), ('phone', 'ilike', query),
            ('member_id', 'ilike', query)], limit=MAX_MATCHES)
        if len(matches) == 1:
            return {'member': self.profile(matches.id), 'matches': []}
        return {'member': None, 'matches': [{
            'id': m.id, 'name': m.name, 'member_id': m.member_id,
            'plan': (m._get_active_plan().name if m._get_active_plan() else 'Guest'), 'status': m.member_state,
        } for m in matches]}

    @api.model
    def profile(self, partner_id):
        self._require_staff()
        partner = self.env['res.partner'].sudo().browse(int(partner_id)).exists()
        if not partner or not partner.is_member:
            raise UserError("That person is not a member.")
        today = club_today()
        plan = partner._get_active_plan()
        days_left = (partner.expiry_date - today).days if partner.expiry_date else None
        Booking = self.env['club.booking'].sudo()
        bookings = Booking.search([('partner_id', '=', partner.id), ('state', '!=', 'cancelled')],
                                  order='start_datetime desc')
        now = fields.Datetime.now()
        upcoming = bookings.filtered(lambda b: b.start_datetime >= now).sorted('start_datetime')[:5]
        past = bookings.filtered(lambda b: b.start_datetime < now)[:5]
        orders = self.env['club.order'].sudo().search([('partner_id', '=', partner.id)], order='create_date desc')
        invoices = self.env['account.move'].sudo().search([
            ('partner_id', '=', partner.id), ('move_type', '=', 'out_invoice'), ('state', '=', 'posted')])
        unpaid = invoices.filtered(lambda m: m.payment_state in ('not_paid', 'partial'))

        alerts = []
        if partner.member_state == 'expired':
            alerts.append({'level': 'danger', 'text': "Membership ended on %s. Offer a renewal at the desk." % partner.expiry_date})
        elif days_left is not None and days_left <= EXPIRY_WARNING_DAYS:
            alerts.append({'level': 'warning', 'text': "Membership ends in %d days (%s)." % (days_left, partner.expiry_date)})
        if unpaid:
            alerts.append({'level': 'warning', 'text': "%d unpaid invoice(s), %s outstanding." % (
                len(unpaid), '{:,.0f}'.format(sum(unpaid.mapped('amount_residual'))))})

        def booking_row(b):
            local = to_club_time(b.start_datetime)
            return {'id': b.id, 'name': b.name, 'court': b.court_id.name, 'state': b.state,
                    'when': local.strftime('%a %d %b, %H:%M'), 'price': b.price}

        return {
            'id': partner.id, 'name': partner.name, 'member_id': partner.member_id,
            'email': partner.email or '', 'phone': partner.phone or '',
            'plan': plan.name if plan else 'Guest', 'plan_code': plan.code if plan else 'none',
            'status': partner.member_state, 'joined': partner.join_date and partner.join_date.isoformat(),
            'expiry': partner.expiry_date and partner.expiry_date.isoformat(), 'days_left': days_left,
            'is_junior': bool(partner.date_of_birth and plan and plan.code == 'junior'),
            'court_rate': plan.court_rate if plan else None,
            'shop_discount': plan.shop_discount if plan else 0, 'bar_discount': plan.bar_discount if plan else 0,
            'alerts': alerts,
            'upcoming': [booking_row(b) for b in upcoming],
            'recent': [booking_row(b) for b in past],
            'visits': len(bookings.filtered(lambda b: b.state == 'done')),
            'orders': [{'name': o.name, 'channel': o.channel, 'total': o.total,
                        'when': fields.Datetime.context_timestamp(self, o.create_date).strftime('%d %b %Y')}
                       for o in orders[:5]],
            'order_count': len(orders),
            'lifetime_spend': sum(invoices.mapped('amount_total_signed')) - sum(unpaid.mapped('amount_residual')),
            'last_check_in': partner.last_check_in and fields.Datetime.to_string(partner.last_check_in),
            'check_in_count': partner.check_in_count,
        }

    @api.model
    def check_in(self, partner_id):
        """Record that the member turned up. Expired members are let through with a warning on screen."""
        self._require_staff()
        partner = self.env['res.partner'].sudo().browse(int(partner_id)).exists()
        if not partner or not partner.is_member:
            raise UserError("That person is not a member.")
        partner.write({'last_check_in': fields.Datetime.now(), 'check_in_count': partner.check_in_count + 1})
        partner.message_post(body="Checked in at the front desk by %s." % self.env.user.name,
                             subtype_xmlid='mail.mt_note')
        return self.profile(partner.id)
