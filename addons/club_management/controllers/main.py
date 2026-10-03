from datetime import datetime

from markupsafe import escape

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
                sport=None, type=None, redirect=None, website_url=None, **kw):
        """Enquiry form (website "Join the club"): creates a crm.lead.

        Returns JSON with the enquiry reference and a private status link, or redirects to
        ``redirect`` (a local path) when given. ``website_url`` is a honeypot: real visitors
        never see or fill it, so a bot that does gets a normal-looking reply and no lead.
        """
        if website_url:
            return request.make_json_response({'success': True, 'reference': 'ENQ-00000'})
        try:
            lead = request.env['crm.lead'].create_club_enquiry(
                name, email=email, phone=phone, message=message, plan=plan, sport=sport,
                enquiry_type=type or 'membership')
        except ValidationError as error:
            return request.make_json_response({'success': False, 'error': str(error)}, status=400)
        status_url = '/club/enquiry/status/%s' % lead.enquiry_token
        if redirect and redirect.startswith('/') and not redirect.startswith(('//', '/\\')):
            return request.redirect(redirect)
        return request.make_json_response({
            'success': True, 'lead_id': lead.id, 'reference': lead.enquiry_ref,
            'status_url': status_url})

    @http.route('/club/api/enquiry/status', type='http', auth='public', methods=['GET'], cors='*')
    def api_enquiry_status(self, token=None, **kw):
        """Progress of an enquiry, by the secret token in the visitor's status link."""
        status = request.env['crm.lead'].club_enquiry_status(token)
        if not status:
            return request.make_json_response({'error': "Enquiry not found."}, status=404)
        return request.make_json_response(status)

    @http.route('/club/enquiry/status/<string:token>', type='http', auth='public', methods=['GET'])
    def enquiry_status_page(self, token, **kw):
        """Plain status page for the link in the acknowledgment email."""
        status = request.env['crm.lead'].club_enquiry_status(token)
        if not status:
            return request.not_found()
        body = (
            "<h2>Enquiry %(reference)s</h2><p><strong>%(status)s</strong></p><p>%(message)s</p>"
            % {key: escape(value or '') for key, value in status.items() if key != 'is_member'})
        return request.make_response(
            "<!doctype html><meta charset='utf-8'><title>Enquiry status</title>"
            "<body style='font-family:sans-serif;max-width:32rem;margin:3rem auto'>%s</body>" % body,
            headers=[('Content-Type', 'text/html; charset=utf-8')])

    @http.route('/club/api/plans', type='http', auth='public', methods=['GET'], cors='*')
    def api_plans(self, **kw):
        """Return all membership plans."""
        plans = request.env['club.membership.plan'].sudo().get_frontend_plans()
        return request.make_json_response({'plans': plans})

    @http.route('/club/api/courts', type='http', auth='public', methods=['GET'], cors='*')
    def api_courts(self, **kw):
        """Return all courts."""
        courts = request.env['club.court'].sudo().get_courts_list()
        return request.make_json_response({'courts': courts})

    @http.route('/club/api/booking/create', type='json', auth='user', methods=['POST'])
    def api_create_booking(self, court_id=None, date=None, time=None, partner_id=None, walkin_name=None, **kw):
        """Create and confirm a booking for the logged-in user.

        Club staff may book for any member or walk-in; everyone else can only book for
        themselves, whatever ``partner_id`` they send.
        """
        user = request.env.user
        is_staff = user.has_group('club_management.group_club_staff')
        if not is_staff:
            partner_id, walkin_name = user.partner_id.id, None
        result = request.env['club.booking'].sudo(not is_staff).create_booking_api(
            court_id, date, time, partner_id, walkin_name)
        if not result['success']:
            result['error'] = result['message']
        return result

    @http.route('/club/api/shop/catalog', type='http', auth='public', methods=['GET'], cors='*')
    def api_shop_catalog(self, category=None, search=None, partner_id=None, **kw):
        """Return Pro-Shop catalog with live inventory."""
        products = request.env['product.product'].sudo().get_shop_catalog(
            category=category,
            search_query=search or '',
            partner_id=partner_id
        )
        return request.make_json_response({'products': products})

    @http.route('/club/api/pos/catalog', type='http', auth='user', methods=['GET'])
    def api_pos_catalog(self, category=None, search=None, partner_id=None, **kw):
        """Return Bar & Cafeteria products and floor tables (staff screen: login required,
        since tables show who is seated and their tab)."""
        if not request.env.user.has_group('club_management.group_club_staff'):
            return request.make_json_response({'error': "Club staff only."}, status=403)
        products = request.env['product.product'].get_bar_products(
            category=category,
            search_query=search or '',
            partner_id=partner_id
        )
        tables = request.env['club.pos.table'].get_tables_data()
        return request.make_json_response({'products': products, 'tables': tables})

