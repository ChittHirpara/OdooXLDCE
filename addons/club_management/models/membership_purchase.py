"""Buy or renew a membership online, from choosing the plan to an active member.

New customers go through the club's own chain, so the CRM shows what happened:
enquiry -> quotation -> accepted (invoice raised) -> lead won -> member created -> payment.
An existing member renewing skips the enquiry: quotation -> invoice -> payment -> new expiry.

The card step is a TEST MODE gateway: nothing is charged and nothing but the last four digits
is kept. A real provider (Odoo's payment module) can replace `check_card` without touching the rest.
"""
import logging
import re
from datetime import date, timedelta

from odoo import Command, api, fields, models
from odoo.exceptions import ValidationError

from .booking import club_today
from .res_partner import JUNIOR_AGE_LIMIT

_logger = logging.getLogger(__name__)

DECLINED_TEST_CARD = '4000000000000002'     # always declined in test mode, like the big gateways' test cards


def luhn_ok(digits):
    total = 0
    for index, char in enumerate(reversed(digits)):
        value = int(char)
        if index % 2:
            value = value * 2 - 9 if value > 4 else value * 2
        total += value
    return total % 10 == 0


class ClubMembershipPurchase(models.AbstractModel):
    _name = 'club.membership.purchase'
    _description = 'Online membership purchase'

    # ------------------------------------------------------------------
    # the (test mode) card
    # ------------------------------------------------------------------
    @api.model
    def check_card(self, holder, number, expiry, cvc, today=None):
        """Validate the card fields and 'charge' it. Returns the last four digits.

        Raises ValidationError with a message the customer can act on. Nothing is stored here.
        """
        today = today or club_today()
        if not (holder or '').strip():
            raise ValidationError("Enter the name on the card.")
        digits = re.sub(r'\D', '', number or '')
        if digits == DECLINED_TEST_CARD:
            raise ValidationError("Your card was declined. Try another card. "
                                  "(Test mode: 4000 0000 0000 0002 is always declined.)")
        if not 13 <= len(digits) <= 19 or not luhn_ok(digits):
            raise ValidationError("The card number is not valid.")
        match = re.fullmatch(r'\s*(\d{1,2})\s*/\s*(\d{2}|\d{4})\s*', expiry or '')
        if not match or not 1 <= int(match.group(1)) <= 12:
            raise ValidationError("Enter the expiry date as MM/YY.")
        year = int(match.group(2))
        year += 2000 if year < 100 else 0
        month = int(match.group(1))
        last_day = date(year + (month == 12), month % 12 + 1, 1) - timedelta(days=1)
        if last_day < today:
            raise ValidationError("This card has expired.")
        if not re.fullmatch(r'\d{3,4}', (cvc or '').strip()):
            raise ValidationError("Enter the 3 or 4 digit security code.")
        return digits[-4:]

    # ------------------------------------------------------------------
    # the purchase
    # ------------------------------------------------------------------
    @api.model
    def purchase(self, plan_code, card, partner=None, name=None, email=None, phone=None,
                 date_of_birth=None, password=None, password_confirm=None):
        """Buy (or renew) ``plan_code``. ``card`` is a dict: holder, number, expiry, cvc.

        ``partner`` is a signed-in customer (their identity comes from the session). Otherwise
        a new customer is created with a website login (their e-mail and chosen password).
        Everything is done or nothing: a refused card or a rule such as "Junior needs a birth
        date" leaves no enquiry, order, invoice or login behind. Returns a dict with the
        partner, the invoice and whether this was a renewal.
        """
        Plan = self.env['club.membership.plan'].sudo()
        plan = Plan.search([('code', '=', plan_code)], limit=1)
        if not plan:
            raise ValidationError("Unknown membership plan.")
        date_of_birth = fields.Date.to_date(date_of_birth) if date_of_birth else False
        if plan.code == 'junior':
            born = date_of_birth or (partner and partner.date_of_birth)
            if not born:
                raise ValidationError("A Junior membership needs the child's date of birth.")
            today = club_today()
            if today.year - born.year - ((today.month, today.day) < (born.month, born.day)) >= JUNIOR_AGE_LIMIT:
                raise ValidationError("Junior memberships are for children under %d. Please choose another plan." % JUNIOR_AGE_LIMIT)
        if not partner:      # check the details first: a refused login must not cost anyone money
            self.env['res.partner']._club_validate_signup(email, password, password_confirm)
            if not (name or '').strip():
                raise ValidationError("Please tell us your name.")
        last4 = self.check_card(card.get('holder'), card.get('number'), card.get('expiry'), card.get('cvc'))

        with self.env.cr.savepoint():       # all or nothing
            created = False
            if not partner:
                partner = self.env['res.partner'].sudo().create({
                    'name': name.strip()[:100], 'email': email.strip(), 'phone': (phone or '').strip()[:30] or False,
                    'date_of_birth': date_of_birth or False})
                partner._club_create_login(password)
                created = True
            partner = partner.sudo()
            renewal = bool(partner.is_member)
            if date_of_birth and not partner.date_of_birth:
                partner.date_of_birth = date_of_birth
            if renewal:
                invoice = self._renew(partner, plan)
            else:
                invoice = self._join(partner, plan, phone)
            self._pay(invoice, last4)
        return {'partner': partner, 'invoice': invoice, 'renewal': renewal, 'created': created, 'plan': plan}

    def _plan_order(self, partner, plan, lead=None):
        if not plan.product_id:
            plan._sync_product()
        vals = {'partner_id': partner.id, 'origin': 'Website membership',
                'order_line': [Command.create({'product_id': plan.product_id.id, 'product_uom_qty': 1,
                                               'price_unit': plan.price})]}
        if lead:
            vals['opportunity_id'] = lead.id
        return self.env['sale.order'].sudo().create(vals)

    def _join(self, partner, plan, phone):
        """New member: through the CRM, so the pipeline shows enquiry, quote, won."""
        lead = self.env['crm.lead'].sudo().create_club_enquiry(
            partner.name, email=partner.email, phone=phone or partner.phone, plan=plan.code,
            message="Bought the %s membership online." % plan.name, notify=False)
        lead.partner_id = partner
        if partner.date_of_birth:
            lead.member_date_of_birth = partner.date_of_birth
        lead.action_create_membership_quote()
        order = lead.order_ids.filtered(lambda o: o.state in ('draft', 'sent'))[:1]
        order.action_confirm()      # raises the invoice, marks the lead won and creates the member
        if not partner.is_member or partner.member_state != 'active':
            raise ValidationError("Your membership could not be started. You have not been charged.")
        return order.invoice_ids[:1]

    def _renew(self, partner, plan):
        """Existing member: a new quotation and invoice, and the expiry moves on (never back)."""
        order = self._plan_order(partner, plan)
        order.action_confirm()
        invoices = order._create_invoices()
        invoices.write({'club_source': 'membership'})
        invoices.action_post()
        today = club_today()
        start = max(today, partner.expiry_date) if partner.member_state == 'active' and partner.expiry_date else today
        partner.write({'plan_id': plan.id, 'is_member': True, 'join_date': partner.join_date or today,
                       'expiry_date': start + timedelta(days=plan.validity_days)})
        partner.message_post(body="Membership renewed online: %s, valid until %s." % (plan.name, partner.expiry_date),
                             subtype_xmlid='mail.mt_note')
        return invoices[:1]

    def _pay(self, invoice, last4):
        """Record the payment against the posted invoice. Accounting problems are logged, not fatal:
        the customer has paid and is a member either way."""
        if not invoice or invoice.state != 'posted':
            _logger.warning("Membership purchase without a posted invoice: no payment recorded")
            return
        journal = self.env['account.journal'].sudo().search(
            [('company_id', '=', invoice.company_id.id), ('type', '=', 'bank')], limit=1)
        if not journal:
            _logger.warning("No bank journal: payment of %s not recorded", invoice.name)
            return
        try:
            with self.env.cr.savepoint():
                self.env['account.payment.register'].sudo().with_context(
                    active_model='account.move', active_ids=invoice.ids).create({
                        'journal_id': journal.id, 'communication': "Online card payment ****%s (test mode)" % last4,
                }).action_create_payments()
        except Exception:    # noqa: BLE001
            _logger.exception("Could not record the payment of %s", invoice.name)
