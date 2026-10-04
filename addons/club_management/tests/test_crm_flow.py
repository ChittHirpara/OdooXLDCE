import json
from datetime import timedelta

from odoo import Command
from odoo.addons.club_management.models.booking import club_today
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import HttpCase, TransactionCase, tagged

from .common import MON, club_dt


class CrmCommon(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        cls.Lead = env['crm.lead']
        cls.gold = env.ref('club_management.plan_gold')
        cls.silver = env.ref('club_management.plan_silver')
        cls.junior = env.ref('club_management.plan_junior')
        cls.today = club_today()

    def enquire(self, name='Rahul Patel', email='rahul.patel@example.com', **kw):
        kw.setdefault('plan', 'gold')
        return self.Lead.create_club_enquiry(name, email=email, **kw)

    def stage(self, xmlid):
        return self.env.ref(xmlid)

    def confirm_quote(self, lead):
        lead.action_create_membership_quote()
        order = lead.order_ids.filtered(lambda o: o.state in ('draft', 'sent'))
        order.action_confirm()
        return order


@tagged('post_install', '-at_install', 'club_management')
class TestPipeline(CrmCommon):

    def test_stages_follow_the_club_workflow(self):
        names = ['New', 'Contacted', 'Interested', 'Quote Sent', 'Negotiation', 'Won']
        stages = self.env['crm.stage'].search([('name', 'in', names)], order='sequence')
        self.assertEqual(stages.mapped('name'), names)
        self.assertEqual([s.name for s in stages if s.is_won], ['Won'])

    def test_lost_reasons_exist(self):
        self.assertTrue(self.env.ref('club_management.lost_not_interested'))
        self.assertGreaterEqual(self.env['crm.lost.reason'].search_count([]), 4)

    def test_new_enquiry_enters_the_pipeline_as_new(self):
        lead = self.enquire()
        self.assertEqual(lead.type, 'opportunity')
        self.assertEqual(lead.stage_id.name, 'New')


@tagged('post_install', '-at_install', 'club_management')
class TestEnquiryIntake(CrmCommon):

    def test_lead_carries_the_club_fields(self):
        lead = self.enquire(phone='+91 99999 00000', sport='Padel', message='Evening slots?')
        self.assertEqual(lead.interested_plan_id, self.gold)
        self.assertEqual((lead.enquiry_type, lead.enquiry_source, lead.sport_interest),
                         ('membership', 'website', 'padel'))
        self.assertEqual(lead.source_id, self.env.ref('club_management.utm_source_website'))
        self.assertEqual(lead.tag_ids.name, 'Club Enquiry')
        self.assertIn('Evening slots?', lead.description)
        self.assertEqual(lead.contact_name, 'Rahul Patel')

    def test_pipeline_revenue_is_the_plan_fee(self):
        self.assertEqual(self.enquire(plan='gold').expected_revenue, 5000.0)
        self.assertEqual(self.enquire('S', 's@example.com', plan='silver').expected_revenue, 3000.0)
        self.assertEqual(self.enquire('G', 'g@example.com', plan=None, enquiry_type='general').expected_revenue, 0.0)

    def test_reference_and_secret_token(self):
        first, second = self.enquire(), self.enquire('Priya N', 'priya.n@example.com')
        self.assertRegex(first.enquiry_ref, r'^ENQ-\d{5}$')
        self.assertNotEqual(first.enquiry_ref, second.enquiry_ref)
        self.assertGreaterEqual(len(first.enquiry_token), 32)
        self.assertNotEqual(first.enquiry_token, second.enquiry_token)

    def test_assigned_to_a_club_manager_with_a_follow_up_call(self):
        lead = self.enquire()
        manager_group = self.env.ref('club_management.group_club_manager')
        self.assertIn(manager_group, lead.user_id.groups_id)
        self.assertNotEqual(lead.user_id.id, 1)                # never the OdooBot superuser
        activity = lead.activity_ids
        self.assertEqual(len(activity), 1)
        self.assertEqual(activity.activity_type_id, self.env.ref('mail.mail_activity_data_call'))
        self.assertEqual(activity.user_id, lead.user_id)
        self.assertEqual(activity.date_deadline, self.today + timedelta(days=1))
        self.assertEqual(lead.follow_up_date, self.today + timedelta(days=1))

    def test_assignee_can_be_configured(self):
        user = self.env['res.users'].create({
            'name': 'Front Desk', 'login': 'front_desk@example.com',
            'groups_id': [Command.set([self.env.ref('base.group_user').id])]})
        self.env['ir.config_parameter'].sudo().set_param('club_management.enquiry_assignee_id', user.id)
        self.assertEqual(self.enquire().user_id, user)

    def test_acknowledgment_email_with_reference_and_status_link(self):
        lead = self.enquire()
        mail = self.env['mail.mail'].search([('email_to', '=', 'rahul.patel@example.com')])
        self.assertEqual(len(mail), 1)
        self.assertIn(lead.enquiry_ref, mail.subject)
        self.assertIn('/club/enquiry/status/%s' % lead.enquiry_token, mail.body_html)
        self.assertIn('Gold', mail.body_html)

    def test_phone_only_enquiry_sends_no_email(self):
        before = self.env['mail.mail'].search_count([])
        self.Lead.create_club_enquiry('Phone Person', phone='+91 90000 11111', plan='silver')
        self.assertEqual(self.env['mail.mail'].search_count([]), before)

    def test_same_visitor_twice_in_a_day_extends_the_same_lead(self):
        first = self.enquire(message='First message')
        count = self.Lead.search_count([])
        second = self.enquire(message='Second message, also about Gold')
        self.assertEqual(second, first)
        self.assertEqual(self.Lead.search_count([]), count)
        self.assertIn('Second message', ' '.join(first.message_ids.mapped('body')))

    def test_a_different_email_is_a_new_lead(self):
        first = self.enquire()
        other = self.enquire('Someone Else', 'someone.else@example.com')
        self.assertNotEqual(other, first)

    def test_a_returning_visitor_after_a_day_is_a_new_lead(self):
        first = self.enquire()
        self.env.cr.execute("UPDATE crm_lead SET create_date = create_date - interval '30 hours' WHERE id = %s",
                            (first.id,))
        first.invalidate_recordset()
        self.assertNotEqual(self.enquire(), first)

    def test_validation(self):
        with self.assertRaises(ValidationError):
            self.enquire(sport='quidditch')
        with self.assertRaises(ValidationError):
            self.enquire(enquiry_type='gossip')
        with self.assertRaises(ValidationError):
            self.enquire(source='carrier pigeon')
        with self.assertRaises(ValidationError):
            self.enquire(plan='platinum')

    def test_other_enquiry_types_are_kept(self):
        lead = self.enquire(plan=None, enquiry_type='court', sport='tennis')
        self.assertEqual((lead.enquiry_type, lead.interested_plan_id), ('court', self.env['club.membership.plan']))
        self.assertNotIn('(', lead.name)


@tagged('post_install', '-at_install', 'club_management')
class TestVisitorStatus(CrmCommon):

    def test_status_shows_progress_and_nothing_internal(self):
        lead = self.enquire()
        status = self.Lead.club_enquiry_status(lead.enquiry_token)
        self.assertEqual(set(status), {'reference', 'status', 'message', 'plan', 'received', 'is_member'})
        self.assertEqual((status['reference'], status['status'], status['plan']),
                         (lead.enquiry_ref, 'New', 'Gold'))
        lead.stage_id = self.stage('crm.stage_lead2')
        self.assertEqual(self.Lead.club_enquiry_status(lead.enquiry_token)['status'], 'Contacted')

    def test_unknown_or_short_tokens_find_nothing(self):
        self.enquire()
        self.assertIsNone(self.Lead.club_enquiry_status('nope'))
        self.assertIsNone(self.Lead.club_enquiry_status(''))
        self.assertIsNone(self.Lead.club_enquiry_status('a' * 40))

    def test_lost_enquiry_reads_as_closed(self):
        lead = self.enquire()
        lead.action_set_lost()
        status = self.Lead.club_enquiry_status(lead.enquiry_token)
        self.assertEqual(status['status'], 'Closed')

    def test_won_enquiry_welcomes_the_member(self):
        lead = self.enquire()
        self.confirm_quote(lead)
        status = self.Lead.club_enquiry_status(lead.enquiry_token)
        self.assertEqual(status['status'], 'Won')
        self.assertTrue(status['is_member'])


@tagged('post_install', '-at_install', 'club_management')
class TestQuotation(CrmCommon):

    def test_quote_for_the_plan_the_lead_asked_about(self):
        lead = self.enquire(plan='silver')
        action = lead.action_create_membership_quote()
        order = self.env['sale.order'].browse(action['res_id'])
        self.assertEqual((action['res_model'], action['view_mode']), ('sale.order', 'form'))
        self.assertEqual(order.opportunity_id, lead)
        self.assertEqual(order.state, 'draft')
        self.assertEqual(order.order_line.product_id, self.silver.product_id)
        self.assertEqual((order.order_line.product_uom_qty, order.order_line.price_unit), (1.0, 3000.0))
        self.assertEqual(order.validity_date, self.today + timedelta(days=14))
        self.assertEqual(order.origin, lead.enquiry_ref)

    def test_quote_creates_the_customer_and_moves_the_lead(self):
        lead = self.enquire()
        self.assertFalse(lead.partner_id)
        lead.action_create_membership_quote()
        self.assertEqual(lead.partner_id.name, 'Rahul Patel')
        self.assertEqual(lead.partner_id.email, 'rahul.patel@example.com')
        self.assertEqual(lead.stage_id.name, 'Quote Sent')

    def test_quote_reuses_an_existing_contact_with_the_same_email(self):
        existing = self.env['res.partner'].create({'name': 'Rahul P.', 'email': 'rahul.patel@example.com'})
        lead = self.enquire()
        lead.action_create_membership_quote()
        self.assertEqual(lead.partner_id, existing)

    def test_asking_twice_opens_the_same_quote(self):
        lead = self.enquire()
        first = lead.action_create_membership_quote()['res_id']
        self.assertEqual(lead.action_create_membership_quote()['res_id'], first)
        self.assertEqual(len(lead.order_ids), 1)

    def test_quote_needs_a_plan(self):
        lead = self.enquire(plan=None, enquiry_type='general')
        with self.assertRaises(UserError):
            lead.action_create_membership_quote()

    def test_quote_never_moves_a_lead_backwards(self):
        lead = self.enquire()
        lead.stage_id = self.stage('club_management.stage_negotiation')
        lead.action_create_membership_quote()
        self.assertEqual(lead.stage_id.name, 'Negotiation')

    def test_sending_the_quote_keeps_the_lead_at_quote_sent(self):
        lead = self.enquire()
        order = self.env['sale.order'].browse(lead.action_create_membership_quote()['res_id'])
        lead.stage_id = self.stage('crm.stage_lead3')
        order.action_quotation_sent()
        self.assertEqual(lead.stage_id.name, 'Quote Sent')

    def test_membership_products_are_service_products_outside_the_shop(self):
        for plan in (self.gold, self.silver, self.junior):
            product = plan.product_id
            self.assertEqual((product.detailed_type, product.list_price), ('service', plan.price))
            self.assertFalse(product.available_in_pos)
            shop = self.env.ref('club_management.product_category_shop')
            bar = self.env.ref('club_management.product_category_bar')
            self.assertNotIn(product.categ_id, shop | bar)
        names = [p['name'] for p in self.env['product.product'].get_shop_catalog('all', '')]
        self.assertFalse([n for n in names if 'Membership' in n])

    def test_changing_the_annual_fee_reprices_the_product_and_new_quotes(self):
        self.silver.price = 3500.0
        self.assertEqual(self.silver.product_id.list_price, 3500.0)
        lead = self.enquire(plan='silver')
        order = self.env['sale.order'].browse(lead.action_create_membership_quote()['res_id'])
        self.assertEqual(order.amount_total, 3500.0)


@tagged('post_install', '-at_install', 'club_management')
class TestLeadToMember(CrmCommon):

    def test_accepting_the_quote_wins_the_lead_and_creates_the_member(self):
        lead = self.enquire(plan='gold')
        order = self.confirm_quote(lead)
        self.assertEqual(order.state, 'sale')
        self.assertTrue(lead.stage_id.is_won)
        self.assertEqual(lead.probability, 100)
        member = lead.partner_id
        self.assertTrue(lead.member_activated)
        self.assertEqual((member.is_member, member.plan_id, member.member_state), (True, self.gold, 'active'))
        self.assertTrue(member.member_id.startswith('CC-'))
        self.assertEqual(member.expiry_date, self.today + timedelta(days=self.gold.validity_days))
        self.assertEqual(lead.member_ref, member.member_id)

    def test_the_new_member_gets_their_tier_benefits_everywhere(self):
        lead = self.enquire(plan='gold')
        self.confirm_quote(lead)
        member = lead.partner_id
        self.assertEqual(member.property_product_pricelist, self.gold.pricelist_id)      # shop + bar
        court = self.env['club.court'].create({'name': 'Flow Court', 'sport': 'tennis', 'list_price': 800.0})
        booking = self.env['club.booking'].create({
            'court_id': court.id, 'partner_id': member.id, 'start_datetime': club_dt(MON, 10)})
        self.assertEqual((booking.tier, booking.price), ('gold', 0.0))                    # court

    def test_welcome_email_and_chatter_note(self):
        lead = self.enquire(plan='silver')
        self.confirm_quote(lead)
        member = lead.partner_id
        mail = self.env['mail.mail'].search([('recipient_ids', 'in', member.ids)])
        self.assertEqual(len(mail), 1)
        self.assertIn(member.member_id, mail.body_html)
        self.assertIn('Silver', mail.body_html)
        notes = ' '.join(lead.message_ids.mapped('body'))
        self.assertIn(member.member_id, notes)

    def test_dragging_the_lead_to_won_also_creates_the_member(self):
        lead = self.enquire(plan='silver')
        lead.stage_id = self.env['crm.stage'].search([('is_won', '=', True)], limit=1)
        self.assertTrue(lead.member_activated)
        self.assertEqual(lead.partner_id.plan_id, self.silver)

    def test_mark_won_button_also_creates_the_member(self):
        lead = self.enquire()
        lead.action_set_won()
        self.assertTrue(lead.member_activated)

    def test_join_button_makes_the_member_in_one_click(self):
        lead = self.enquire(plan='silver')
        self.assertFalse(lead.member_activated)
        action = lead.action_join_club()
        self.assertEqual(action['tag'], 'display_notification')
        self.assertTrue(lead.member_activated)
        self.assertTrue(lead.stage_id.is_won)
        member = lead.partner_id
        self.assertEqual((member.plan_id, member.member_state), (self.silver, 'active'))
        self.assertTrue(member.member_id)
        # a second press is not offered, and does nothing harmful
        lead.action_join_club()
        self.assertEqual(self.env['res.partner'].search_count([('email', '=', lead.email_from)]), 1)

    def test_join_button_needs_a_plan_and_says_so(self):
        lead = self.enquire(plan=None, enquiry_type='court')
        with self.assertRaisesRegex(UserError, 'membership plan'):
            lead.action_join_club()
        self.assertFalse(lead.member_activated)
        lead.interested_plan_id = self.gold
        lead.action_join_club()
        self.assertTrue(lead.member_activated)

    def test_join_button_refuses_a_junior_without_a_birth_date(self):
        lead = self.enquire('Kid Parent', 'kid.parent2@example.com', plan='junior')
        with self.assertRaises(ValidationError):
            lead.action_join_club()
        self.assertFalse(lead.member_activated)
        lead.member_date_of_birth = self.today.replace(year=self.today.year - 10)
        lead.action_join_club()
        self.assertTrue(lead.partner_id.is_junior)

    def test_join_button_is_on_the_lead_form_and_list(self):
        for xml in ('crm.crm_lead_view_form', 'crm.crm_case_tree_view_oppor'):
            arch = self.env['crm.lead'].get_view(self.env.ref(xml).id)['arch']
            self.assertIn('action_join_club', arch)

    def test_won_without_a_plan_creates_no_member_and_says_so(self):
        lead = self.enquire(plan=None, enquiry_type='general')
        lead.action_set_won()
        self.assertFalse(lead.member_activated)
        self.assertIn('no membership plan', ' '.join(lead.message_ids.mapped('body')))
        lead.interested_plan_id = self.silver
        lead.action_activate_membership()
        self.assertTrue(lead.member_activated)
        self.assertEqual(lead.partner_id.plan_id, self.silver)

    def test_junior_needs_a_birth_date_and_a_task_is_raised(self):
        lead = self.enquire('Kid Parent', 'kid.parent@example.com', plan='junior')
        lead.action_set_won()
        self.assertFalse(lead.member_activated)
        self.assertIn('date of birth', ' '.join(lead.message_ids.mapped('body')))
        self.assertTrue(lead.activity_ids.filtered(lambda a: a.summary == 'Complete member details'))
        lead.member_date_of_birth = self.today.replace(year=self.today.year - 10)
        lead.action_activate_membership()
        self.assertTrue(lead.member_activated)
        self.assertTrue(lead.partner_id.is_junior)

    def test_junior_plan_for_an_adult_is_refused(self):
        lead = self.enquire('Adult', 'adult@example.com', plan='junior')
        lead.action_set_won()
        lead.member_date_of_birth = self.today.replace(year=self.today.year - 30)
        with self.assertRaises(ValidationError):
            lead.action_activate_membership()
        self.assertFalse(lead.member_activated)

    def test_existing_active_member_is_not_reset(self):
        member = self.env['res.partner'].create({
            'name': 'Already In', 'email': 'already.in@example.com', 'plan_id': self.gold.id})
        member.action_activate_membership()
        member.expiry_date = self.today + timedelta(days=40)
        lead = self.enquire('Already In', 'already.in@example.com', plan='gold')
        lead.action_set_won()
        self.assertEqual(member.expiry_date, self.today + timedelta(days=40))       # not shortened
        self.assertTrue(lead.member_activated)
        self.assertIn('already an active', ' '.join(lead.message_ids.mapped('body')))

    def test_upgrade_changes_the_plan(self):
        member = self.env['res.partner'].create({
            'name': 'Upgrader', 'email': 'upgrader@example.com', 'plan_id': self.silver.id})
        member.action_activate_membership()
        lead = self.enquire('Upgrader', 'upgrader@example.com', plan='gold')
        lead.action_set_won()
        self.assertEqual(member.plan_id, self.gold)
        self.assertEqual(member.property_product_pricelist, self.gold.pricelist_id)

    def test_a_quote_for_something_else_does_not_win_the_lead(self):
        lead = self.enquire()
        partner = lead._club_ensure_customer()
        other = self.env['product.product'].create({'name': 'Coaching hour', 'detailed_type': 'service',
                                                   'list_price': 900.0})
        order = self.env['sale.order'].create({
            'partner_id': partner.id, 'opportunity_id': lead.id,
            'order_line': [Command.create({'product_id': other.id, 'product_uom_qty': 1})]})
        order.action_confirm()
        self.assertFalse(lead.stage_id.is_won)
        self.assertFalse(lead.member_activated)

    def test_confirming_the_quote_twice_never_creates_two_members(self):
        lead = self.enquire()
        order = self.confirm_quote(lead)
        members = self.env['res.partner'].search_count([('email', '=', 'rahul.patel@example.com')])
        order.opportunity_id.action_set_won()
        self.assertEqual(self.env['res.partner'].search_count([('email', '=', 'rahul.patel@example.com')]), members)

    def test_lost_lead_creates_nothing(self):
        lead = self.enquire()
        lead.action_set_lost(lost_reason_id=self.env.ref('club_management.lost_no_response').id)
        self.assertFalse(lead.active)
        self.assertFalse(lead.member_activated)
        self.assertFalse(lead.partner_id.is_member)

    def test_member_then_books_shops_and_orders(self):
        """The same person flows through the whole platform."""
        lead = self.enquire('Full Flow', 'full.flow@example.com', plan='gold')
        self.confirm_quote(lead)
        member = lead.partner_id
        bar = self.env['product.product'].create({
            'name': 'Flow Latte', 'list_price': 200.0, 'detailed_type': 'consu',
            'categ_id': self.env.ref('club_management.product_category_bar').id})
        shop = self.env['product.product'].create({
            'name': 'Flow Grip', 'list_price': 300.0, 'detailed_type': 'consu',
            'categ_id': self.env.ref('club_management.product_category_shop').id})
        service = self.env['club.order.service']
        self.assertEqual(service.calculate_order_pricing([{'product_id': bar.id, 'qty': 1}],
                                                         partner_id=member.id)['total'], 170.0)   # 15% bar
        self.assertEqual(service.calculate_order_pricing([{'product_id': shop.id, 'qty': 1}],
                                                         partner_id=member.id)['total'], 240.0)   # 20% shop
        paid = self.env['club.pos.order'].process_payment_api({
            'member_id': member.id, 'payment_method': 'upi', 'items': [{'product_id': bar.id, 'qty': 1}]})
        self.assertTrue(paid['success'])
        self.assertEqual(self.env['club.order'].browse(paid['order_id']).partner_id, member)


@tagged('post_install', '-at_install', 'club_management')
class TestCrmSecurityAndViews(CrmCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Users = cls.env['res.users'].with_context(no_reset_password=True)
        base_user = cls.env.ref('base.group_user')
        cls.staff = Users.create({
            'name': 'CRM Staff', 'login': 'crm_staff@example.com', 'email': 'crm_staff@example.com',
            'groups_id': [Command.set([base_user.id, cls.env.ref('club_management.group_club_staff').id])]})
        cls.plain = Users.create({
            'name': 'Plain Employee', 'login': 'crm_plain@example.com', 'email': 'crm_plain@example.com',
            'groups_id': [Command.set([base_user.id])]})

    def test_staff_work_every_lead_from_quote_to_member(self):
        lead = self.enquire()                       # owned by the manager, not by this staff user
        as_staff = lead.with_user(self.staff)
        order = self.env['sale.order'].browse(as_staff.action_create_membership_quote()['res_id'])
        order.with_user(self.staff).action_confirm()
        self.assertTrue(lead.member_activated)
        self.assertEqual(lead.partner_id.plan_id, self.gold)

    def test_staff_can_log_a_follow_up(self):
        lead = self.enquire()
        activity = lead.with_user(self.staff).activity_schedule(
            'mail.mail_activity_data_todo', summary='Call back Friday',
            date_deadline=self.today + timedelta(days=3))
        self.assertEqual(activity.res_id, lead.id)

    def test_the_public_cannot_read_leads(self):
        public = self.env.ref('base.public_user')
        self.enquire()
        with self.assertRaises(AccessError):
            self.Lead.with_user(public).search([])

    def test_employees_without_a_club_role_cannot_work_the_leads(self):
        lead = self.enquire()
        with self.assertRaises(AccessError):
            lead.with_user(self.plain).read(['name'])

    def test_lead_form_has_the_club_controls(self):
        form = self.Lead.get_view(self.env.ref('crm.crm_lead_view_form').id)['arch']
        for needle in ('action_create_membership_quote', 'action_activate_membership',
                       'interested_plan_id', 'enquiry_source', 'follow_up_date', 'member_date_of_birth'):
            self.assertIn(needle, form)

    def test_pipeline_menu_and_funnel_report_open(self):
        lead = self.enquire()
        action = self.env.ref('club_management.action_club_enquiries')
        self.assertIn(lead, self.Lead.search(eval(action.domain)))             # noqa: S307 (trusted data file)
        groups = self.Lead._read_group(eval(action.domain), ['stage_id', 'interested_plan_id'], ['__count'])
        self.assertTrue(groups)
        for xmlid in ('view_crm_lead_pivot_club', 'view_crm_lead_graph_club'):
            view = self.env.ref('club_management.' + xmlid)
            self.assertTrue(self.Lead.get_view(view.id, view.type)['arch'])


@tagged('post_install', '-at_install', 'club_management')
class TestEnquiryEndpoints(HttpCase):

    def setUp(self):
        super().setUp()
        self.authenticate(None, None)

    def post(self, **data):
        from odoo import http
        data['csrf_token'] = http.Request.csrf_token(self)
        return self.url_open('/club/enquiry', data=data)

    def test_form_post_returns_reference_and_status_link(self):
        reply = self.post(name='Web Visitor', email='web.visitor@example.com', plan='gold', type='membership')
        body = reply.json()
        self.assertTrue(body['success'])
        self.assertRegex(body['reference'], r'^ENQ-\d{5}$')
        lead = self.env['crm.lead'].search([('enquiry_ref', '=', body['reference'])])
        self.assertEqual(body['status_url'], '/club/enquiry/status/%s' % lead.enquiry_token)
        self.assertEqual(lead.enquiry_source, 'website')

    def test_honeypot_creates_nothing(self):
        before = self.env['crm.lead'].search_count([])
        reply = self.post(name='Bot', email='bot@example.com', plan='gold', website_url='http://spam.example')
        self.assertTrue(reply.json()['success'])
        self.assertEqual(self.env['crm.lead'].search_count([]), before)

    def test_bad_input_is_a_400(self):
        self.assertEqual(self.post(name='X', email='nope', plan='gold').status_code, 400)
        self.assertEqual(self.post(name='X', email='x@example.com', plan='gold', type='gossip').status_code, 400)

    def test_status_json_by_token(self):
        lead = self.env['crm.lead'].create_club_enquiry('Status Visitor', email='status.v@example.com', plan='silver')
        reply = self.url_open('/club/api/enquiry/status?token=%s' % lead.enquiry_token)
        self.assertEqual(reply.status_code, 200)
        self.assertEqual(reply.json()['reference'], lead.enquiry_ref)
        self.assertNotIn('email', json.dumps(reply.json()).lower().replace('"reference"', ''))
        self.assertEqual(self.url_open('/club/api/enquiry/status?token=bogus').status_code, 404)
        self.assertEqual(self.url_open('/club/api/enquiry/status').status_code, 404)

    def test_status_page_for_the_email_link(self):
        lead = self.env['crm.lead'].create_club_enquiry('Page Visitor', email='page.v@example.com', plan='gold')
        page = self.url_open('/club/enquiry/status/%s' % lead.enquiry_token)
        self.assertEqual(page.status_code, 200)
        self.assertIn(lead.enquiry_ref, page.text)
        self.assertEqual(self.url_open('/club/enquiry/status/' + 'z' * 40).status_code, 404)

    def test_the_status_link_does_not_expose_other_leads(self):
        first = self.env['crm.lead'].create_club_enquiry('One', email='one@example.com', plan='gold')
        second = self.env['crm.lead'].create_club_enquiry('Two', email='two@example.com', plan='gold')
        page = self.url_open('/club/enquiry/status/%s' % first.enquiry_token).text
        self.assertIn(first.enquiry_ref, page)
        self.assertNotIn(second.enquiry_ref, page)
