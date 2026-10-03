from datetime import datetime

from odoo import fields, http
from odoo.exceptions import ValidationError
from odoo.http import request


class ClubController(http.Controller):

    @http.route('/club/availability', type='http', auth='public', methods=['GET'], cors='*')
    def availability(self, date=None, court_id=None, sport=None, **kw):
        """Slot availability as JSON: /club/availability?date=YYYY-MM-DD[&court_id=1][&sport=tennis]"""
        try:
            day = datetime.strptime(date, '%Y-%m-%d').date() if date else fields.Date.context_today(
                request.env['club.court'])
        except ValueError:
            return request.make_json_response({'error': "date must be YYYY-MM-DD"}, status=400)
        domain = [('active', '=', True)]
        if court_id:
            if not court_id.isdigit():
                return request.make_json_response({'error': "court_id must be a number"}, status=400)
            domain.append(('id', '=', int(court_id)))
        if sport:
            domain.append(('sport', '=', sport))
        courts = request.env['club.court'].sudo().search(domain)
        return request.make_json_response({'date': day.isoformat(), 'courts': courts.get_availability(day)})

    @http.route('/club/enquiry', type='http', auth='public', methods=['POST'])
    def enquiry(self, name=None, email=None, phone=None, message=None, plan=None,
                sport=None, redirect=None, **kw):
        """Membership enquiry form: creates a crm.lead.

        Returns JSON, or redirects to ``redirect`` (a local path) when given.
        """
        try:
            lead = request.env['crm.lead'].create_club_enquiry(
                name, email=email, phone=phone, message=message, plan=plan, sport=sport)
        except ValidationError as error:
            return request.make_json_response({'success': False, 'error': str(error)}, status=400)
        if redirect and redirect.startswith('/') and not redirect.startswith(('//', '/\\')):
            return request.redirect(redirect)
        return request.make_json_response({'success': True, 'lead_id': lead.id})
