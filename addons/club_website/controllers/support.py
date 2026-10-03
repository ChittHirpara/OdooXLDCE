"""Feedback and support on the website. The rules live in Club Management
(club.feedback.create_public, club.ticket.create_public); these routes collect the form."""
from odoo import http
from odoo.addons.club_management.models.club_support import FEEDBACK_AREAS, TICKET_CATEGORIES
from odoo.addons.club_website.controllers.member import signed_in_defaults
from odoo.exceptions import ValidationError
from odoo.http import request

TICKET_STEPS = [('new', 'Received'), ('progress', 'In progress'), ('resolved', 'Resolved')]


def signed_in_partner_id():
    user = request.env.user
    return user.partner_id.id if user.share and not user._is_public() else None


class ClubSupport(http.Controller):

    # ------------------------------------------------------------------
    # feedback
    # ------------------------------------------------------------------
    def _feedback_values(self, form=None, error=None):
        values = {'area': 'club', 'rating': '', 'comment': '', 'name': '', 'email': '',
                  'booking': '', 'order': ''}
        values.update({k: v for k, v in signed_in_defaults().items() if k in ('name', 'email')})
        values.update({key: (value or '') for key, value in (form or {}).items()})
        return {'areas': FEEDBACK_AREAS, 'form': values, 'error': error}

    @http.route('/feedback', type='http', auth='public', website=True, sitemap=True)
    def feedback(self, area=None, booking=None, order=None, **kw):
        form = {'area': area if area in dict(FEEDBACK_AREAS) else 'club', 'booking': booking, 'order': order}
        return request.render('club_website.feedback_page', self._feedback_values(form))

    @http.route('/feedback/submit', type='http', auth='public', website=True, methods=['POST'], sitemap=False)
    def feedback_submit(self, area=None, rating=None, comment=None, name=None, email=None,
                        booking=None, order=None, website_url=None, **kw):
        form = {'area': area, 'rating': rating, 'comment': comment, 'name': name, 'email': email,
                'booking': booking, 'order': order}
        if website_url:     # honeypot
            return request.render('club_website.feedback_thanks_page', {'rating': 0})
        try:
            feedback = request.env['club.feedback'].create_public(
                area, rating, comment=comment, name=name, email=email, partner_id=signed_in_partner_id(),
                booking_token=booking, order_token=order)
        except ValidationError as error:
            response = request.render('club_website.feedback_page', self._feedback_values(form, error.args[0]))
            response.status_code = 400
            return response
        return request.render('club_website.feedback_thanks_page', {'rating': feedback.rating})

    # ------------------------------------------------------------------
    # support
    # ------------------------------------------------------------------
    def _support_values(self, form=None, error=None):
        values = {'category': 'complaint', 'subject': '', 'description': '', 'name': '', 'email': '',
                  'phone': '', 'booking': '', 'order': ''}
        values.update({k: v for k, v in signed_in_defaults().items() if k in ('name', 'email', 'phone')})
        values.update({key: (value or '') for key, value in (form or {}).items()})
        return {'categories': TICKET_CATEGORIES, 'form': values, 'error': error}

    @http.route('/support', type='http', auth='public', website=True, sitemap=True)
    def support(self, category=None, booking=None, order=None, **kw):
        form = {'category': category if category in dict(TICKET_CATEGORIES) else 'complaint',
                'booking': booking, 'order': order}
        return request.render('club_website.support_page', self._support_values(form))

    @http.route('/support/submit', type='http', auth='public', website=True, methods=['POST'], sitemap=False)
    def support_submit(self, name=None, email=None, phone=None, category=None, subject=None,
                       description=None, booking=None, order=None, website_url=None, **kw):
        form = {'name': name, 'email': email, 'phone': phone, 'category': category, 'subject': subject,
                'description': description, 'booking': booking, 'order': order}
        if website_url:     # honeypot: look normal, create nothing
            return request.redirect('/support')
        try:
            ticket = request.env['club.ticket'].create_public(
                name, category, subject, description=description, email=email, phone=phone,
                partner_id=signed_in_partner_id(), booking_token=booking, order_token=order)
        except ValidationError as error:
            response = request.render('club_website.support_page', self._support_values(form, error.args[0]))
            response.status_code = 400
            return response
        return request.redirect('/support/ticket/%s?new=1' % ticket.access_token)

    @http.route('/support/ticket/<string:token>', type='http', auth='public', website=True, sitemap=False)
    def support_ticket(self, token, new=None, **kw):
        ticket = request.env['club.ticket'].get_by_token(token)
        if not ticket:
            return request.not_found()
        status = ticket._public_status()
        steps = [key for key, _label in TICKET_STEPS]
        current = steps.index(status['state_key']) if status['state_key'] in steps else len(steps) - 1
        return request.render('club_website.ticket_page', {
            'status': status, 'new': bool(new), 'steps': TICKET_STEPS, 'current': current})
