import uuid
from datetime import timedelta

from odoo import SUPERUSER_ID, Command, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools import email_normalize, plaintext2html

from .booking import club_today

ENQUIRY_TYPES = [
    ('membership', 'Membership'),
    ('court', 'Court Booking'),
    ('shop', 'Pro-Shop'),
    ('bar', 'Bar & Events'),
    ('general', 'General'),
]
ENQUIRY_SOURCES = [
    ('website', 'Website'),
    ('phone', 'Phone'),
    ('walk_in', 'Walk-in'),
    ('referral', 'Referral'),
    ('social', 'Social Media'),
    ('other', 'Other'),
]
SPORTS = [('tennis', 'Tennis'), ('padel', 'Padel'), ('badminton', 'Badminton'), ('cricket', 'Cricket')]

FOLLOW_UP_DAYS = 1           # first follow-up is due the day after an enquiry
QUOTE_VALID_DAYS = 14
# What a visitor sees on the status page, by pipeline stage (internal names stay internal)
PUBLIC_STATUS = {
    'New': "Received: we will contact you shortly.",
    'Contacted': "We have been in touch with you.",
    'Interested': "Your enquiry is being processed.",
    'Quote Sent': "We have sent you a membership quote.",
    'Negotiation': "We are finalising the details with you.",
    'Won': "Welcome to the club! Your membership is active.",
}


class CrmLead(models.Model):
    _inherit = 'crm.lead'

    enquiry_ref = fields.Char(string='Enquiry Ref', copy=False, readonly=True, index=True)
    enquiry_token = fields.Char(copy=False, readonly=True, index=True,
                                help="Secret in the visitor's status link.")
    interested_plan_id = fields.Many2one('club.membership.plan', string='Interested Plan', tracking=True)
    enquiry_type = fields.Selection(ENQUIRY_TYPES, string='Enquiry Type', tracking=True)
    enquiry_source = fields.Selection(ENQUIRY_SOURCES, string='How They Reached Us', tracking=True)
    sport_interest = fields.Selection(SPORTS, string='Sport')
    follow_up_date = fields.Date(related='activity_date_deadline', string='Next Follow-up')
    member_date_of_birth = fields.Date(
        string='Date of Birth', help="Needed for a Junior membership (under 18).")
    member_activated = fields.Boolean(copy=False, readonly=True)
    member_ref = fields.Char(related='partner_id.member_id', string='Member ID')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            vals.setdefault('enquiry_token', uuid.uuid4().hex)
            if not vals.get('enquiry_ref'):
                vals['enquiry_ref'] = self.env['ir.sequence'].sudo().next_by_code('club.enquiry')
        return super().create(vals_list)

    # ------------------------------------------------------------------
    # Public intake (website form, API)
    # ------------------------------------------------------------------
    @api.model
    def _club_default_assignee(self):
        """Who follows up new enquiries: the configured user, else the first club manager."""
        params = self.env['ir.config_parameter'].sudo()
        configured = int(params.get_param('club_management.enquiry_assignee_id', 0) or 0)
        user = self.env['res.users'].sudo().browse(configured).exists() if configured else None
        if user and user.active:
            return user
        manager = self.env.ref('club_management.group_club_manager')
        return self.env['res.users'].sudo().search([
            ('groups_id', 'in', manager.id), ('id', '!=', SUPERUSER_ID), ('share', '=', False),
        ], order='id', limit=1)

    @api.model
    def create_club_enquiry(self, name, email=None, phone=None, message=None, plan=None,
                            sport=None, enquiry_type='membership', source='website'):
        """Create (or extend) the CRM lead for a public enquiry.

        Runs with elevated rights because website visitors are anonymous. Raises
        ValidationError with a user-presentable message on bad input. A visitor who
        enquires twice within a day gets a note on the same lead, not a duplicate.
        """
        name = (name or '').strip()
        phone = (phone or '').strip()
        email = (email or '').strip()
        if not name:
            raise ValidationError("Please tell us your name.")
        if not email and not phone:
            raise ValidationError("Please give an email address or a phone number.")
        if email and not email_normalize(email):
            raise ValidationError("The email address is not valid.")
        plan_rec = self.env['club.membership.plan']
        if plan:
            plan_rec = plan_rec.sudo().search([('code', '=', plan)], limit=1)
            if not plan_rec:
                raise ValidationError("Unknown membership plan.")
        sport = (sport or '').strip().lower() or False
        if sport and sport not in dict(SPORTS):
            raise ValidationError("Unknown sport.")
        if enquiry_type not in dict(ENQUIRY_TYPES):
            raise ValidationError("Unknown enquiry type.")
        if source not in dict(ENQUIRY_SOURCES):
            raise ValidationError("Unknown enquiry source.")
        message = (message or '').strip()[:2000]

        existing = self._club_recent_open_enquiry(email)
        if existing:
            existing.message_post(
                body=plaintext2html("The same person enquired again%s." % (
                    ": " + message if message else "")),
                subtype_xmlid='mail.mt_note')
            return existing

        lines = []
        if plan_rec:
            lines.append("Interested plan: %s" % plan_rec.name)
        if sport:
            lines.append("Sport: %s" % dict(SPORTS)[sport])
        if message:
            lines.append(message)
        tag = self.env.ref('club_management.crm_tag_club_enquiry', raise_if_not_found=False)
        source_utm = self.env.ref('club_management.utm_source_website', raise_if_not_found=False)
        assignee = self._club_default_assignee()
        title = "Club enquiry: %s" % name[:100]
        if plan_rec:
            title += " (%s)" % plan_rec.name
        lead = self.sudo().create({
            'name': title,
            'type': 'opportunity',
            'contact_name': name[:100],
            'email_from': email_normalize(email) or False,
            'phone': phone[:30] or False,
            'description': plaintext2html("\n".join(lines)) if lines else False,
            'tag_ids': [Command.link(tag.id)] if tag else [],
            'interested_plan_id': plan_rec.id,
            'expected_revenue': plan_rec.price,       # the annual fee: feeds the pipeline forecast
            'enquiry_type': enquiry_type,
            'enquiry_source': source,
            'sport_interest': sport,
            'source_id': source_utm.id if source_utm and source == 'website' else False,
            'user_id': assignee.id or False,
        })
        if assignee:
            lead.activity_schedule(
                'mail.mail_activity_data_call',
                date_deadline=club_today() + timedelta(days=FOLLOW_UP_DAYS),
                summary="Contact new enquiry",
                note="Call or email %s about %s." % (name, plan_rec.name if plan_rec else "their enquiry"),
                user_id=assignee.id)
        if lead.email_from:
            template = self.env.ref('club_management.mail_template_enquiry_received', raise_if_not_found=False)
            if template:
                template.sudo().send_mail(lead.id)
        return lead

    @api.model
    def _club_recent_open_enquiry(self, email, hours=24):
        normalized = email_normalize(email or '')
        if not normalized:
            return self.browse()
        since = fields.Datetime.now() - timedelta(hours=hours)
        return self.sudo().search([
            ('email_normalized', '=', normalized),
            ('enquiry_source', '!=', False),
            ('create_date', '>=', since),
            ('probability', '<', 100),
        ], limit=1)

    def _club_public_status(self):
        """What a visitor may see about their enquiry (nothing internal)."""
        self.ensure_one()
        if not self.active:
            message = "This enquiry is closed. Contact us any time to start again."
        else:
            message = PUBLIC_STATUS.get(self.stage_id.name, "Your enquiry is being processed.")
        return {
            'reference': self.enquiry_ref,
            'status': "Closed" if not self.active else self.stage_id.name,
            'message': message,
            'plan': self.interested_plan_id.name or None,
            'received': fields.Datetime.to_string(self.create_date),
            'is_member': self.member_activated,
        }

    @api.model
    def club_enquiry_status(self, token):
        """Public status lookup by secret token."""
        token = (token or '').strip()
        lead = self.sudo().with_context(active_test=False).search(
            [('enquiry_token', '=', token)], limit=1) if len(token) >= 16 else None
        return lead._club_public_status() if lead else None

    # ------------------------------------------------------------------
    # Lead -> quotation -> won -> member
    # ------------------------------------------------------------------
    def _club_ensure_customer(self):
        """The contact for this lead: the linked one, one with the same email, or a new one."""
        self.ensure_one()
        if not self.partner_id:
            self.partner_id = self._find_matching_partner(email_only=True) or self._create_customer()
        return self.partner_id

    def action_create_membership_quote(self):
        """Quotation for the plan the lead is interested in (reuses an open one)."""
        self.ensure_one()
        plan = self.interested_plan_id
        if not plan:
            raise UserError("Choose the membership plan the enquirer is interested in first.")
        if not plan.product_id:
            plan._sync_product()
        partner = self._club_ensure_customer()
        order = self.env['sale.order'].search([
            ('opportunity_id', '=', self.id), ('state', 'in', ('draft', 'sent')),
            ('order_line.product_id', '=', plan.product_id.id)], limit=1)
        if not order:
            order = self.env['sale.order'].create({
                'partner_id': partner.id,
                'opportunity_id': self.id,
                'origin': self.enquiry_ref or self.name,
                'user_id': self.user_id.id or self.env.uid,
                'team_id': self.team_id.id,
                'validity_date': club_today() + timedelta(days=QUOTE_VALID_DAYS),
                'order_line': [Command.create({
                    'product_id': plan.product_id.id,
                    'product_uom_qty': 1,
                    'price_unit': plan.price,
                })],
            })
            self.message_post(body="Quotation %s created: %s membership, %s." % (
                order.name, plan.name, order.currency_id.format(order.amount_total)))
        self._club_advance_to('club_management.stage_quote_sent')
        return {
            'type': 'ir.actions.act_window',
            'name': 'Membership Quotation',
            'res_model': 'sale.order',
            'res_id': order.id,
            'view_mode': 'form',
        }

    def _club_advance_to(self, stage_xmlid):
        """Move leads forward to a stage, never backwards or out of a closed state."""
        stage = self.env.ref(stage_xmlid)
        for lead in self.filtered(lambda l: l.active and not l.stage_id.is_won
                                  and l.stage_id.sequence < stage.sequence):
            lead.stage_id = stage

    def write(self, vals):
        newly_won = self.browse()
        if 'stage_id' in vals or 'probability' in vals:
            newly_won = self.filtered(lambda lead: not lead.stage_id.is_won)
        res = super().write(vals)
        if newly_won:
            newly_won.filtered(lambda lead: lead.stage_id.is_won)._club_activate_member()
        return res

    def action_activate_membership(self):
        """Create the member now (for won leads that needed a plan or birth date first)."""
        for lead in self:
            if not lead.interested_plan_id:
                raise UserError("Choose a membership plan first.")
        self._club_activate_member(raise_errors=True)
        return True

    def _club_activate_member(self, raise_errors=False):
        """Won lead -> customer -> member with the chosen plan, activated."""
        for lead in self.filtered(lambda l: not l.member_activated):
            plan = lead.interested_plan_id
            if not plan:
                lead.message_post(body=(
                    "Lead won, but no membership plan was chosen, so no member was created. "
                    "Choose a plan, then press Activate Membership."))
                continue
            partner = lead._club_ensure_customer()
            if lead.member_date_of_birth and not partner.date_of_birth:
                partner.date_of_birth = lead.member_date_of_birth
            if partner.member_state == 'active' and partner.plan_id == plan:
                lead.member_activated = True
                lead.message_post(body="%s is already an active %s member (%s)." % (
                    partner.name, plan.name, partner.member_id))
                continue
            try:
                with self.env.cr.savepoint():
                    partner.plan_id = plan
                    partner.action_activate_membership()
            except ValidationError as error:
                if raise_errors:
                    raise
                lead.message_post(body="Lead won, but the membership could not be activated: %s" % error.args[0])
                lead.activity_schedule(
                    'mail.mail_activity_data_todo', summary="Complete member details",
                    note=error.args[0], user_id=(lead.user_id or self.env.user).id)
                continue
            lead.member_activated = True
            lead.message_post(body="Member created: %s, %s plan, ID %s, valid until %s." % (
                partner.name, plan.name, partner.member_id, partner.expiry_date))
            template = self.env.ref('club_management.mail_template_member_welcome', raise_if_not_found=False)
            if template and partner.email:
                template.sudo().send_mail(partner.id)

    def action_open_member(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'res.partner',
            'res_id': self.partner_id.id,
            'view_mode': 'form',
        }
