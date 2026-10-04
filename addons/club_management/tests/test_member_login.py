from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install', 'club_management')
class TestMemberLogin(TransactionCase):
    """A member gets a website (portal) login when the membership starts."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Lead = cls.env['crm.lead']
        cls.Partner = cls.env['res.partner']
        cls.gold = cls.env.ref('club_management.plan_gold')

    def _member(self, email='login.member@example.com', name='Login Member'):
        partner = self.Partner.create({'name': name, 'email': email})
        partner.plan_id = self.gold
        partner.action_activate_membership()
        return partner

    def test_join_button_creates_a_portal_login_with_the_email(self):
        lead = self.Lead.create_club_enquiry(
            'Asha Verma', email='Asha.Verma@Example.com', plan='gold')
        lead.action_join_club()
        user = lead.partner_id.user_ids
        self.assertEqual(len(user), 1)
        self.assertEqual(user.login, 'asha.verma@example.com')
        self.assertTrue(user.share, "members get portal access, never staff access")
        self.assertTrue(user.has_group('base.group_portal'))
        self.assertFalse(user.has_group('base.group_user'))

    def test_login_is_created_once_and_not_for_a_second_activation(self):
        lead = self.Lead.create_club_enquiry('Asha Verma', email='asha.verma@example.com', plan='gold')
        lead.action_join_club()
        partner = lead.partner_id
        partner._club_ensure_portal_login()
        self.assertEqual(len(partner.user_ids), 1)

    def test_register_or_renew_member_gives_a_login(self):
        partner = self.Partner.create({'name': 'Renew Rita', 'email': 'rita@example.com'})
        self.Partner.register_or_renew_member(partner.id, 'gold')
        self.assertEqual(partner.user_ids.login, 'rita@example.com')

    def test_no_email_means_no_login_and_no_error(self):
        partner = self.Partner.create({'name': 'No Mail'})
        partner.plan_id = self.gold
        partner.action_activate_membership()
        partner._club_ensure_portal_login()
        self.assertFalse(partner.user_ids)

    def test_existing_staff_user_is_left_alone(self):
        admin = self.env.ref('base.user_admin')
        partner = admin.partner_id
        partner.email = partner.email or 'admin@example.com'
        partner.plan_id = self.gold
        partner.action_activate_membership()
        partner._club_ensure_portal_login()
        self.assertEqual(partner.user_ids, admin)
        self.assertTrue(admin.has_group('base.group_user'))

    def test_an_email_already_used_as_a_login_is_not_taken_twice(self):
        first = self._member('shared@example.com', 'First')
        first._club_grant_portal_access()
        second = self._member('shared@example.com', 'Second')
        self.assertFalse(second._club_grant_portal_access())
        self.assertFalse(second.user_ids)

    def test_only_members_get_a_login(self):
        outsider = self.Partner.create({'name': 'Outsider', 'email': 'outsider@example.com'})
        self.assertFalse(outsider._club_grant_portal_access())
        with self.assertRaises(UserError):
            outsider.action_send_portal_invitation()

    def test_invitation_button_creates_the_login_and_reports(self):
        partner = self._member('button@example.com', 'Button Bea')
        result = partner.action_send_portal_invitation()
        self.assertEqual(partner.user_ids.login, 'button@example.com')
        self.assertEqual(result['tag'], 'display_notification')

    def test_welcome_mail_mentions_the_login_only_when_there_is_one(self):
        template = self.env.ref('club_management.mail_template_member_welcome')
        with_login = self._member('mailed@example.com', 'Mailed Mo')
        with_login._club_ensure_portal_login()
        self.assertIn('sign in on our website', template._render_field('body_html', with_login.ids)[with_login.id])
        without = self.Partner.create({'name': 'Walk Wally', 'email': 'wally@example.com'})
        without.plan_id = self.gold
        without.action_activate_membership()
        self.assertNotIn('sign in on our website', template._render_field('body_html', without.ids)[without.id])


@tagged('post_install', '-at_install', 'club_management')
class TestProductImages(TransactionCase):

    def test_demo_products_get_a_picture_and_the_loader_is_repeatable(self):
        demo = self.env['club.demo']
        product = self.env.ref('club_management.product_bar_burger', raise_if_not_found=False)
        if not product:
            self.skipTest("club demo data is not loaded")
        product.image_1920 = False
        demo.load_product_images()
        self.assertTrue(product.image_1920)
        picture = product.image_1920
        demo.load_product_images()
        self.assertEqual(product.image_1920, picture, "an existing picture is never replaced")

    def test_catalog_gives_staff_screens_a_picture_url(self):
        product = self.env.ref('club_management.product_racket_tennis_1', raise_if_not_found=False)
        if not product:
            self.skipTest("club demo data is not loaded")
        self.env['club.demo'].load_product_images()
        item = next(p for p in self.env['product.product'].get_shop_catalog() if p['id'] == product.id)
        self.assertTrue(item['has_image'])
        self.assertIn('/web/image/product.product/%d/image_512' % product.id, item['image_url'])
        self.assertNotIn('image_icon', item)
