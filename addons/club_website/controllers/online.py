"""Booking a court and ordering from the shop on the website, with no staff in the loop.

The rules live in Club Management (create_public_booking, place_public_order); these routes
only collect the form, call them, and show the result. Nothing is calculated here.
"""
from datetime import datetime, timedelta

from odoo import http
from odoo.addons.club_management.models.booking import to_club_time
from odoo.addons.club_website.controllers.member import signed_in_defaults
from odoo.exceptions import ValidationError
from odoo.http import request

CART = 'club_cart'


class ClubOnline(http.Controller):

    @property
    def site(self):
        return request.env['club.website.data']

    # ------------------------------------------------------------------
    # small helpers
    # ------------------------------------------------------------------
    def _flash(self, message):
        request.session['club_flash'] = message

    def _take_flash(self):
        return request.session.pop('club_flash', None)

    def _cart(self):
        return dict(request.session.get(CART) or {})

    # ------------------------------------------------------------------
    # court booking
    # ------------------------------------------------------------------
    def _book_values(self, court_id, date, time, form=None, error=None):
        court = request.env['club.court'].sudo().browse(int(court_id or 0)).exists() if str(court_id or '').isdigit() \
            else request.env['club.court']
        Booking = request.env['club.booking']
        start = None
        window_error = None
        if court:
            try:
                start = Booking._club_start_utc(date, time)
                Booking._check_public_window(start)
            except ValidationError as exc:
                window_error = exc.args[0]
        local = to_club_time(start) if start else None
        values = {'name': '', 'phone': '', 'email': '', 'players': '1', 'member_ref': '', 'member_email': ''}
        values.update(signed_in_defaults())
        values.update({key: (value or '') for key, value in (form or {}).items()})
        return {
            'court': court, 'book_date': date or '', 'book_time': time or '', 'form': values,
            'error': error or window_error, 'can_book': bool(court and not window_error),
            'when': local.strftime('%A %d %B %Y') if local else '',
            'start_label': local.strftime('%H:%M') if local else '',
            'end_label': (local + timedelta(hours=1)).strftime('%H:%M') if local else '',
            'is_social': bool(local and local.weekday() == 4),
        }

    @http.route('/book', type='http', auth='public', website=True, sitemap=False)
    def book(self, court_id=None, date=None, time=None, **kw):
        values = self._book_values(court_id, date, time)
        if not values['court']:
            return request.redirect('/courts')
        return request.render('club_website.book_page', values)

    @http.route('/book/submit', type='http', auth='public', website=True, methods=['POST'], sitemap=False)
    def book_submit(self, court_id=None, date=None, time=None, name=None, phone=None, email=None,
                    players=None, member_ref=None, member_email=None, website_url=None, **kw):
        form = {'name': name, 'phone': phone, 'email': email, 'players': players,
                'member_ref': member_ref, 'member_email': member_email}
        if website_url:         # honeypot: a bot filled the hidden field; no booking is made
            return request.redirect('/courts')
        try:
            booking = request.env['club.booking'].create_public_booking(
                int(court_id or 0), date, time, name, phone=phone, email=email,
                players=players, member_ref=member_ref, member_email=member_email)
        except ValidationError as error:
            response = request.render('club_website.book_page',
                                      self._book_values(court_id, date, time, form, error.args[0]))
            response.status_code = 400
            return response
        return request.redirect('/booking/%s?new=1' % booking.access_token)

    def _booking_values(self, booking, new=False):
        local = to_club_time(booking.start_datetime)
        return {
            'booking': booking, 'new': new, 'flash': self._take_flash(),
            'when': local.strftime('%A %d %B %Y'),
            'start_label': local.strftime('%H:%M'),
            'end_label': to_club_time(booking.end_datetime).strftime('%H:%M'),
            'can_cancel': booking.state in ('draft', 'confirmed') and not booking.invoice_id
                          and booking.start_datetime > datetime.utcnow(),
            'customer': booking.partner_id.name or booking.walkin_name,
        }

    @http.route('/booking/<string:token>', type='http', auth='public', website=True, sitemap=False)
    def booking(self, token, new=None, **kw):
        booking = request.env['club.booking'].get_by_token(token)
        if not booking:
            return request.not_found()
        return request.render('club_website.booking_page', self._booking_values(booking, bool(new)))

    @http.route('/booking/<string:token>/cancel', type='http', auth='public', website=True,
                methods=['POST'], sitemap=False)
    def booking_cancel(self, token, **kw):
        booking = request.env['club.booking'].get_by_token(token)
        if not booking:
            return request.not_found()
        try:
            booking.cancel_by_visitor()
            self._flash("Your booking has been cancelled. The slot is free for someone else.")
        except ValidationError as error:
            self._flash(error.args[0])
        return request.redirect('/booking/%s' % token)

    # ------------------------------------------------------------------
    # shop cart and checkout
    # ------------------------------------------------------------------
    def _cart_values(self, **extra):
        lines = self.site.cart_lines(self._cart())
        values = {
            'lines': lines, 'count': sum(line['qty'] for line in lines),
            'subtotal': sum(line['total'] for line in lines), 'flash': self._take_flash(),
            'site': self.site,
        }
        values.update(extra)
        return values

    @http.route('/club-shop/cart/add', type='http', auth='public', website=True, methods=['POST'], sitemap=False)
    def cart_add(self, product_id=None, qty=1, **kw):
        product = self.site.shop_product(int(product_id)) if str(product_id or '').isdigit() else None
        if not product:
            self._flash("That product is not available.")
            return request.redirect('/club-shop')
        if product['stock'] <= 0:
            self._flash("%s is out of stock." % product['name'])
            return request.redirect('/club-shop/%s' % product['id'])
        cart = self._cart()
        key = str(product['id'])
        try:
            wanted = max(1, int(qty))
        except (TypeError, ValueError):
            wanted = 1
        total = min(cart.get(key, 0) + wanted, product['stock'], 20)
        if cart.get(key, 0) + wanted > total:
            self._flash("Only %d of %s can be ordered (that is all we have, or the online limit)." % (
                total, product['name']))
        cart[key] = total
        request.session[CART] = cart
        return request.redirect('/club-shop/cart')

    @http.route('/club-shop/cart', type='http', auth='public', website=True, sitemap=False)
    def cart(self, **kw):
        return request.render('club_website.cart_page', self._cart_values())

    @http.route('/club-shop/cart/update', type='http', auth='public', website=True, methods=['POST'], sitemap=False)
    def cart_update(self, **post):
        cart = self._cart()
        for key, value in post.items():
            if key.startswith('qty_') and key[4:].isdigit() and key[4:] in cart:
                try:
                    qty = int(value)
                except (TypeError, ValueError):
                    continue
                if qty <= 0:
                    cart.pop(key[4:], None)
                else:
                    cart[key[4:]] = min(qty, 20)
        request.session[CART] = cart
        return request.redirect('/club-shop/cart')

    def _checkout_form(self, **overrides):
        form = {'name': '', 'phone': '', 'email': '', 'fulfillment': 'collect', 'address': '',
                'member_ref': '', 'member_email': ''}
        form.update(signed_in_defaults())
        form.update({key: (value or '') for key, value in overrides.items()})
        return form

    @http.route('/club-shop/checkout', type='http', auth='public', website=True, sitemap=False)
    def checkout(self, **kw):
        values = self._cart_values(form=self._checkout_form(), error=None)
        if not values['lines']:
            return request.redirect('/club-shop/cart')
        return request.render('club_website.checkout_page', values)

    @http.route('/club-shop/checkout/submit', type='http', auth='public', website=True, methods=['POST'], sitemap=False)
    def checkout_submit(self, name=None, phone=None, email=None, fulfillment='collect', address=None,
                        member_ref=None, member_email=None, website_url=None, **kw):
        if website_url:         # honeypot
            return request.redirect('/club-shop')
        form = self._checkout_form(name=name, phone=phone, email=email, fulfillment=fulfillment,
                                   address=address, member_ref=member_ref, member_email=member_email)
        items = [{'product_id': int(pid), 'qty': qty} for pid, qty in self._cart().items()]
        try:
            order = request.env['club.order.service'].place_public_order(
                items, name, phone=phone, email=email, fulfillment=fulfillment, address=address,
                member_ref=member_ref, member_email=member_email)
        except ValidationError as error:
            response = request.render('club_website.checkout_page', self._cart_values(
                form=form, error=error.args[0]))
            response.status_code = 400
            return response
        request.session.pop(CART, None)
        return request.redirect('/club-shop/order/%s' % order.access_token)

    @http.route('/club-shop/order/<string:token>', type='http', auth='public', website=True, sitemap=False)
    def order(self, token, **kw):
        order = request.env['club.order'].get_by_token(token)
        if not order:
            return request.not_found()
        return request.render('club_website.order_page', {'order': order})
