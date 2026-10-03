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

    @http.route('/club/api/booking/create', type='json', auth='public', methods=['POST'], cors='*')
    def api_create_booking(self, court_id=None, date=None, time=None, partner_id=None, walkin_name=None, **kw):
        """Create and confirm a booking."""
        try:
            booking = request.env['club.booking'].sudo().create_member_booking(
                court_id=court_id,
                date_str=date,
                time_str=time,
                partner_id=partner_id,
                walkin_name=walkin_name
            )
            return {'success': True, 'booking': booking}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    @http.route('/club/api/shop/catalog', type='http', auth='public', methods=['GET'], cors='*')
    def api_shop_catalog(self, category=None, search=None, partner_id=None, **kw):
        """Return Pro-Shop catalog with live inventory."""
        products = request.env['product.product'].sudo().get_shop_catalog(
            category=category,
            search_query=search or '',
            partner_id=partner_id
        )
        return request.make_json_response({'products': products})

    @http.route('/club/api/pos/catalog', type='http', auth='public', methods=['GET'], cors='*')
    def api_pos_catalog(self, category=None, search=None, partner_id=None, **kw):
        """Return Bar & Cafeteria products and floor tables."""
        products = request.env['product.product'].sudo().get_bar_products(
            category=category,
            search_query=search or '',
            partner_id=partner_id
        )
        tables = request.env['club.pos.table'].sudo().get_tables_data()
        return request.make_json_response({'products': products, 'tables': tables})

