"""Buy or renew a membership online. The rules (card check, enquiry -> quote -> invoice -> payment,
member and login creation) live in Club Management (club.membership.purchase); these routes
collect the form and show the result."""
from odoo import http
from odoo.exceptions import ValidationError
from odoo.http import request


class ClubBuy(http.Controller):

    def _plan(self, code):
        return request.env['club.membership.plan'].sudo().search([('code', '=', code)], limit=1)

    def _customer(self):
        """The signed-in customer (any portal user), or an empty recordset."""
        user = request.env.user
        if user.share and not user._is_public():
            return user.partner_id.sudo()
        return request.env['res.partner']

    def _values(self, plan, form=None, error=None):
        customer = self._customer()
        values = {'name': '', 'email': '', 'phone': '', 'dob': '', 'holder': ''}
        values.update({key: (value or '') for key, value in (form or {}).items()})
        return {
            'plan': plan, 'customer': customer, 'renewal': bool(customer.is_member),
            'needs_dob': plan.code == 'junior' and not customer.date_of_birth,
            'form': values, 'error': error,
        }

    @http.route('/membership/buy/<string:code>', type='http', auth='public', website=True, sitemap=False)
    def buy(self, code, **kw):
        plan = self._plan(code)
        if not plan:
            return request.not_found()
        return request.render('club_website.buy_page', self._values(plan))

    @http.route('/membership/buy/<string:code>/submit', type='http', auth='public', website=True,
                methods=['POST'], sitemap=False)
    def buy_submit(self, code, name=None, email=None, phone=None, dob=None, password=None,
                   password_confirm=None, holder=None, number=None, expiry=None, cvc=None,
                   website_url=None, **kw):
        plan = self._plan(code)
        if not plan:
            return request.not_found()
        if website_url:     # honeypot: look normal, buy nothing
            return request.redirect('/membership')
        form = {'name': name, 'email': email, 'phone': phone, 'dob': dob, 'holder': holder}
        customer = self._customer()
        try:
            result = request.env['club.membership.purchase'].purchase(
                code, {'holder': holder, 'number': number, 'expiry': expiry, 'cvc': cvc},
                partner=customer or None, name=name, email=email, phone=phone,
                date_of_birth=dob or None, password=password, password_confirm=password_confirm)
        except ValidationError as error:
            response = request.render('club_website.buy_page', self._values(plan, form, error.args[0]))
            response.status_code = 400
            return response
        if result['created']:       # a new customer is signed in straight away
            try:
                request.env.cr.commit()     # the login must exist before the session can use it
                request.session.authenticate(request.db, result['partner'].email, password)
            except Exception:    # noqa: BLE001 - the account exists; they can sign in by hand
                return request.redirect('/web/login?redirect=/my/club%3Fpaid%3D1')
        return request.redirect('/my/club?paid=%s' % ('renewed' if result['renewal'] else 'joined'))
