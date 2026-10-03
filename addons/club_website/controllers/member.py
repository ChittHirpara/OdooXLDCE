"""My Club: what a signed-in member sees about their membership, bookings and orders.

The login is a portal user created when the membership starts (res.partner
_club_grant_portal_access). Everything shown is read for that user's own contact only.
"""
from odoo import fields, http
from odoo.addons.club_management.models.booking import club_today, to_club_time
from odoo.http import request
from odoo.tools.image import image_data_uri

EXPIRY_WARNING_DAYS = 30
STATE_LABELS = {'draft': 'Pending', 'confirmed': 'Confirmed', 'cancelled': 'Cancelled', 'done': 'Played'}


def signed_in_defaults():
    """Name, contact and member ID of a signed-in member, so forms start filled in."""
    user = request.env.user
    if not user.share or user._is_public():
        return {}
    partner = user.partner_id.sudo()
    values = {'name': partner.name or '', 'phone': partner.phone or '', 'email': partner.email or ''}
    if partner.is_member and partner.member_id:
        values.update(member_ref=partner.member_id, member_email=partner.email or '')
    return values


class ClubMember(http.Controller):

    def _booking_row(self, booking):
        local = to_club_time(booking.start_datetime)
        return {
            'name': booking.name, 'court': booking.court_id.name,
            'when': local.strftime('%a %d %b %Y'),
            'time': '%s to %s' % (local.strftime('%H:%M'), to_club_time(booking.end_datetime).strftime('%H:%M')),
            'state': STATE_LABELS.get(booking.state, booking.state),
            'price': booking.price, 'url': '/booking/%s' % booking.access_token,
        }

    @http.route('/my/club', type='http', auth='user', website=True, sitemap=False)
    def my_club(self, **kw):
        partner = request.env.user.partner_id.sudo()
        plan = partner._get_active_plan()
        today = club_today()
        days_left = (partner.expiry_date - today).days if partner.expiry_date else None
        Booking = request.env['club.booking'].sudo()
        now = fields.Datetime.now()
        mine = [('partner_id', '=', partner.id)]
        upcoming = Booking.search(mine + [('state', 'in', ('draft', 'confirmed')), ('start_datetime', '>=', now)],
                                  order='start_datetime', limit=10)
        recent = Booking.search(mine + [('start_datetime', '<', now)], order='start_datetime desc', limit=5)
        orders = request.env['club.order'].sudo().search(mine, order='create_date desc', limit=5)
        enquiry = request.env['crm.lead'].sudo().search(
            [('partner_id', '=', partner.id), ('enquiry_ref', '!=', False)], order='id desc', limit=1)
        return request.render('club_website.my_club_page', {
            'enquiry': enquiry and {
                'reference': enquiry.enquiry_ref, 'plan': enquiry.interested_plan_id.name,
                'url': '/club/enquiry/status/%s' % enquiry.enquiry_token},
            'partner': partner, 'is_member': partner.is_member, 'plan': plan or partner.plan_id,
            'active': partner.member_state == 'active', 'days_left': days_left,
            'expiring': days_left is not None and days_left <= EXPIRY_WARNING_DAYS,
            'qr': image_data_uri(partner.qr_code) if partner.qr_code else None,
            'upcoming': [self._booking_row(b) for b in upcoming],
            'recent': [self._booking_row(b) for b in recent],
            'orders': [{'name': o.name, 'when': fields.Datetime.to_string(o.create_date)[:10],
                        'total': o.total, 'url': '/club-shop/order/%s' % o.access_token} for o in orders],
        })
