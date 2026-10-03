from werkzeug.urls import url_encode as urlencode

from odoo import http
from odoo.addons.club_management.controllers.main import ClubController
from odoo.addons.club_management.models.booking import club_today
from odoo.addons.club_management.models.crm_lead import ENQUIRY_TYPES, SPORTS
from odoo.exceptions import ValidationError
from odoo.http import request

# Stages a visitor sees on the status timeline (internal stage names are the same words)
TIMELINE = ['New', 'Contacted', 'Interested', 'Quote Sent', 'Negotiation', 'Won']


class ClubWebsite(http.Controller):
    """Public pages. They read from Club Management (via club.website.data) and write
    nothing except the enquiry, which becomes a CRM lead."""

    @property
    def site(self):
        return request.env['club.website.data']

    def _join_values(self, form=None, error=None):
        values = {'type': 'membership', 'plan': '', 'sport': '', 'name': '', 'email': '',
                  'phone': '', 'message': ''}
        values.update({key: (value or '') for key, value in (form or {}).items()})
        return {'plans': self.site.plans(), 'types': ENQUIRY_TYPES, 'sports': SPORTS,
                'form': values, 'error': error}

    @http.route('/membership', type='http', auth='public', website=True, sitemap=True)
    def membership(self, **kw):
        return request.render('club_website.membership_page', {'plans': self.site.plans()})

    @http.route('/courts', type='http', auth='public', website=True, sitemap=True)
    def courts(self, **kw):
        return request.render('club_website.courts_page', {
            'courts': self.site.courts(), 'sports': SPORTS, 'sport_labels': dict(SPORTS),
            'today': club_today().isoformat()})

    @http.route('/club-shop', type='http', auth='public', website=True, sitemap=True)
    def shop(self, q=None, category=None, **kw):
        categories = self.site.shop_categories()
        category = category if category in dict(categories) else ''
        return request.render('club_website.shop_page', {
            'products': self.site.shop_products(category or None, q),
            'categories': categories, 'category': category, 'query': q or '',
            'site': self.site, 'max_shop_discount': self.site.max_shop_discount()})

    @http.route('/club-shop/<int:product_id>', type='http', auth='public', website=True, sitemap=False)
    def shop_product(self, product_id, **kw):
        product = self.site.shop_product(product_id)
        if not product:
            return request.not_found()
        reserve_url = '/join?' + urlencode({
            'type': 'shop', 'message': 'I would like to reserve: %s' % product['name']})
        return request.render('club_website.shop_product_page', {
            'product': product, 'stock_label': self.site.stock_label(product['stock']),
            'reserve_url': reserve_url})

    @http.route('/join', type='http', auth='public', website=True, sitemap=True)
    def join(self, type=None, plan=None, sport=None, message=None, **kw):
        form = {'type': type if type in dict(ENQUIRY_TYPES) else 'membership',
                'plan': plan, 'sport': sport, 'message': message}
        return request.render('club_website.join_page', self._join_values(form))

    @http.route('/join/submit', type='http', auth='public', website=True, methods=['POST'], sitemap=False)
    def join_submit(self, name=None, email=None, phone=None, type='membership', plan=None,
                    sport=None, message=None, website_url=None, **kw):
        """The enquiry form: creates the CRM lead and shows its reference and status link."""
        form = {'name': name, 'email': email, 'phone': phone, 'type': type, 'plan': plan,
                'sport': sport, 'message': message}
        if website_url:     # honeypot: a bot filled the hidden field; look normal, create nothing
            return request.render('club_website.join_success_page', {'name': name or '', 'reference': None})
        try:
            lead = request.env['crm.lead'].create_club_enquiry(
                name, email=email, phone=phone, message=message, plan=plan or None,
                sport=sport or None, enquiry_type=type or 'membership')
        except ValidationError as error:
            response = request.render('club_website.join_page', self._join_values(form, error.args[0]))
            response.status_code = 400
            return response
        return request.render('club_website.join_success_page', {
            'name': lead.contact_name, 'reference': lead.enquiry_ref,
            'status_url': '/club/enquiry/status/%s' % lead.enquiry_token})

    @http.route('/about', type='http', auth='public', website=True, sitemap=True)
    def about(self, **kw):
        return request.render('club_website.about_page', {'courts': self.site.courts()})

    @http.route('/contact', type='http', auth='public', website=True, sitemap=True)
    def contact(self, **kw):
        return request.render('club_website.contact_page', self._join_values({'type': 'general'}))

    @http.route('/contactus', type='http', auth='public', website=True, sitemap=False)
    def contactus(self, **kw):
        """Odoo's stock contact page emails the company; ours feeds the CRM, so use that."""
        return request.redirect('/contact', code=301)


class ClubEnquiryStatus(ClubController):
    """Same link as the plain page in Club Management, now in the site's design."""

    @http.route('/club/enquiry/status/<string:token>', type='http', auth='public',
                methods=['GET'], website=True, sitemap=False)
    def enquiry_status_page(self, token, **kw):
        status = request.env['crm.lead'].club_enquiry_status(token)
        if not status:
            return request.not_found()
        return request.render('club_website.enquiry_status_page', {
            'status': status, 'timeline': TIMELINE,
            'current': TIMELINE.index(status['status']) if status['status'] in TIMELINE else -1,
            'closed': status['status'] == 'Closed'})
