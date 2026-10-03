from datetime import timedelta

from odoo.addons.club_management.models.booking import club_today
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install', 'club_management')
class TestMembershipCrons(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.today = club_today()
        cls.silver = cls.env.ref('club_management.plan_silver')
        cls.Partner = cls.env['res.partner']

    def _member(self, name, days_left, email='member@example.com'):
        partner = self.Partner.create({
            'name': name, 'email': email, 'is_member': True, 'plan_id': self.silver.id,
            'expiry_date': self.today + timedelta(days=days_left)})
        return partner

    def _make_stale(self, partner, days_ago):
        """Reproduce a membership whose date passed with no write since:
        expired in reality, still 'active' in the stored field."""
        self.env.flush_all()
        self.env.cr.execute(
            "UPDATE res_partner SET expiry_date = %s WHERE id = %s",
            (self.today - timedelta(days=days_ago), partner.id))
        self.env.invalidate_all()
        self.assertEqual(partner.member_state, 'active')

    def _reminders_for(self, partner):
        return self.env['mail.mail'].search([('recipient_ids', 'in', partner.ids)])

    # --- scheduled actions exist ---------------------------------------------
    def test_crons_are_installed_daily_and_active(self):
        for xmlid, method in (('ir_cron_lapse_memberships', '_cron_lapse_memberships'),
                              ('ir_cron_membership_expiry_reminders', '_cron_send_expiry_reminders')):
            cron = self.env.ref('club_management.' + xmlid)
            self.assertTrue(cron.active)
            self.assertEqual((cron.interval_number, cron.interval_type), (1, 'days'))
            self.assertIn(method, cron.code)

    # --- lapse -----------------------------------------------------------------
    def test_lapse_marks_overdue_member_expired(self):
        member = self._member('Overdue', 30)
        self._make_stale(member, 1)
        self.assertEqual(self.Partner._cron_lapse_memberships(), 1)
        self.assertEqual(member.member_state, 'expired')

    def test_lapse_removes_tier_pricelist(self):
        member = self._member('Overdue Priced', 30)
        self.assertEqual(member.property_product_pricelist, self.silver.pricelist_id)
        self._make_stale(member, 1)
        self.Partner._cron_lapse_memberships()
        self.assertNotEqual(member.property_product_pricelist, self.silver.pricelist_id)

    def test_lapse_posts_a_note(self):
        member = self._member('Overdue Note', 30)
        self._make_stale(member, 2)
        self.Partner._cron_lapse_memberships()
        self.assertIn('expired', member.message_ids[0].body)

    def test_lapse_leaves_valid_members_alone(self):
        today_member = self._member('Last Day', 0)           # still valid today
        future_member = self._member('Future', 40)
        self.Partner._cron_lapse_memberships()
        self.assertEqual(today_member.member_state, 'active')
        self.assertEqual(future_member.member_state, 'active')
        self.assertEqual(today_member.property_product_pricelist, self.silver.pricelist_id)

    def test_lapse_is_idempotent(self):
        member = self._member('Twice', 30)
        self._make_stale(member, 1)
        self.assertEqual(self.Partner._cron_lapse_memberships(), 1)
        self.assertEqual(self.Partner._cron_lapse_memberships(), 0)

    def test_renewal_after_lapse_reactivates(self):
        member = self._member('Comes Back', 30)
        self._make_stale(member, 1)
        self.Partner._cron_lapse_memberships()
        member.action_activate_membership()
        self.assertEqual(member.member_state, 'active')
        self.assertEqual(member.property_product_pricelist, self.silver.pricelist_id)

    # --- reminders -------------------------------------------------------------
    def test_reminder_sent_inside_window(self):
        member = self._member('Soon', 5)
        self.assertEqual(self.Partner._cron_send_expiry_reminders(), 1)
        mail = self._reminders_for(member)
        self.assertEqual(len(mail), 1)
        self.assertIn('Silver', mail.subject)
        self.assertIn('Soon', mail.body_html)
        self.assertEqual(member.expiry_reminder_for, member.expiry_date)

    def test_no_reminder_outside_window(self):
        member = self._member('Far Away', 60)
        self.Partner._cron_send_expiry_reminders()
        self.assertFalse(self._reminders_for(member))

    def test_reminder_sent_on_last_valid_day(self):
        member = self._member('Today', 0)
        self.Partner._cron_send_expiry_reminders()
        self.assertEqual(len(self._reminders_for(member)), 1)

    def test_reminder_only_once_per_expiry_date(self):
        member = self._member('Once', 5)
        self.Partner._cron_send_expiry_reminders()
        self.Partner._cron_send_expiry_reminders()
        self.assertEqual(len(self._reminders_for(member)), 1)

    def test_renewal_rearms_reminder(self):
        member = self._member('Renews', 5)
        self.Partner._cron_send_expiry_reminders()
        member.action_activate_membership()                  # expiry moves a year out
        member.expiry_date = self.today + timedelta(days=3)  # ...and later nears again
        self.Partner._cron_send_expiry_reminders()
        self.assertEqual(len(self._reminders_for(member)), 2)

    def test_no_reminder_without_email(self):
        member = self._member('No Mail', 5, email=False)
        self.assertEqual(self.Partner._cron_send_expiry_reminders(), 0)
        self.assertFalse(self._reminders_for(member))
        self.assertFalse(member.expiry_reminder_for)

    def test_no_reminder_for_already_expired(self):
        member = self._member('Gone', -3)
        self.Partner._cron_send_expiry_reminders()
        self.assertFalse(self._reminders_for(member))

    def test_no_reminder_for_non_members(self):
        partner = self.Partner.create({
            'name': 'Not A Member', 'email': 'x@example.com',
            'expiry_date': self.today + timedelta(days=2)})
        self.Partner._cron_send_expiry_reminders()
        self.assertFalse(self._reminders_for(partner))

    def test_reminder_window_is_configurable(self):
        member = self._member('Month Out', 25)
        self.Partner._cron_send_expiry_reminders()
        self.assertFalse(self._reminders_for(member))        # default 14 days
        self.env['ir.config_parameter'].sudo().set_param('club_management.reminder_days', '30')
        self.Partner._cron_send_expiry_reminders()
        self.assertEqual(len(self._reminders_for(member)), 1)
