from datetime import timedelta

from werkzeug.urls import url_encode as urlencode

from odoo import http
from odoo.addons.club_management.controllers.main import ClubController
from odoo.addons.club_management.models.booking import WEBSITE_BOOKING_DAYS, club_today
from odoo.addons.club_management.models.crm_lead import ENQUIRY_TYPES, SPORTS
from odoo.addons.club_website.controllers.member import signed_in_defaults
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
        values.update({k: v for k, v in signed_in_defaults().items() if k in values})
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
            'today': club_today().isoformat(),
            'max_date': (club_today() + timedelta(days=WEBSITE_BOOKING_DAYS)).isoformat()})

    def _cart_count(self):
        lines = self.site.cart_lines(request.session.get('club_cart') or {})
        return sum(line['qty'] for line in lines)

    @http.route('/club-shop', type='http', auth='public', website=True, sitemap=True)
    def shop(self, q=None, category=None, **kw):
        categories = self.site.shop_categories()
        category = category if category in dict(categories) else ''
        return request.render('club_website.shop_page', {
            'products': self.site.shop_products(category or None, q),
            'categories': categories, 'category': category, 'query': q or '',
            'site': self.site, 'max_shop_discount': self.site.max_shop_discount(),
            'cart_count': self._cart_count(), 'flash': request.session.pop('club_flash', None)})

    @http.route('/club-shop/<int:product_id>', type='http', auth='public', website=True, sitemap=False)
    def shop_product(self, product_id, **kw):
        product = self.site.shop_product(product_id)
        if not product:
            return request.not_found()
        reserve_url = '/join?' + urlencode({
            'type': 'shop', 'message': 'I would like to reserve: %s' % product['name']})
        return request.render('club_website.shop_product_page', {
            'product': product, 'stock_label': self.site.stock_label(product['stock']),
            'reserve_url': reserve_url, 'cart_count': self._cart_count(),
            'flash': request.session.pop('club_flash', None)})

    @http.route('/club-shop/image/<int:product_id>', type='http', auth='public', website=True, sitemap=False)
    def shop_image(self, product_id, **kw):
        """A shop product's picture. Visitors cannot read products, so this serves the image
        of products that are publicly for sale, and nothing else."""
        product = self.site.shop_product(product_id)
        if not product or not product['has_image']:
            return request.not_found()
        record = request.env['product.product'].sudo().browse(product_id)
        stream = request.env['ir.binary']._get_image_stream_from(record, 'image_512')
        return stream.get_response(max_age=http.STATIC_CACHE)

    @http.route('/join', type='http', auth='public', website=True, sitemap=True)
    def join(self, type=None, plan=None, sport=None, message=None, **kw):
        form = {'type': type if type in dict(ENQUIRY_TYPES) else 'membership',
                'plan': plan, 'sport': sport, 'message': message}
        return request.render('club_website.join_page', self._join_values(form))

    @http.route('/join/submit', type='http', auth='public', website=True, methods=['POST'], sitemap=False)
    def join_submit(self, name=None, email=None, phone=None, type='membership', plan=None,
                    sport=None, message=None, website_url=None, password=None, password_confirm=None, **kw):
        """The enquiry form: creates the CRM lead and shows its reference and status link.

        With a password the visitor also gets a website login (their e-mail), and is signed in
        straight away. Their membership still starts only when the club confirms it.
        """
        form = {'name': name, 'email': email, 'phone': phone, 'type': type, 'plan': plan,
                'sport': sport, 'message': message}
        if website_url:     # honeypot: a bot filled the hidden field; look normal, create nothing
            return request.render('club_website.join_success_page', {'name': name or '', 'reference': None})
        wants_login = bool(password or password_confirm) and request.env.user._is_public()
        try:
            if wants_login:     # checked first, so a refused login does not leave an enquiry behind
                login = request.env['res.partner']._club_validate_signup(email, password, password_confirm)
            lead = request.env['crm.lead'].create_club_enquiry(
                name, email=email, phone=phone, message=message, plan=plan or None,
                sport=sport or None, enquiry_type=type or 'membership')
            if wants_login:
                lead.sudo()._club_ensure_customer()._club_create_login(password)
        except ValidationError as error:
            response = request.render('club_website.join_page', self._join_values(form, error.args[0]))
            response.status_code = 400
            return response
        signed_in = False
        if wants_login:
            try:
                request.env.cr.commit()     # the login must exist before the session can use it
                request.session.authenticate(request.db, login, password)
                signed_in = True
            except Exception:    # noqa: BLE001 - the account exists; they can sign in by hand
                signed_in = False
        return request.render('club_website.join_success_page', {
            'name': lead.contact_name, 'reference': lead.enquiry_ref,
            'status_url': '/club/enquiry/status/%s' % lead.enquiry_token,
            'account': wants_login, 'signed_in': signed_in})

    @http.route('/about', type='http', auth='public', website=True, sitemap=True)
    def about(self, **kw):
        return request.render('club_website.about_page', {
            'courts': self.site.courts(), 'site': self.site, 'sport_labels': dict(SPORTS)})

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
