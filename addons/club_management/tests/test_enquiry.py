import json

from odoo import http
from odoo.exceptions import ValidationError
from odoo.tests import HttpCase, TransactionCase, tagged


@tagged('post_install', '-at_install', 'club_management')
class TestEnquiryModel(TransactionCase):

    def test_creates_lead_with_details(self):
        lead = self.env['crm.lead'].create_club_enquiry(
            'Asha Rao', email='Asha@Example.com', phone='+91 99999 00000',
            message='Do you have coaching?', plan='silver', sport='tennis')
        self.assertEqual(lead.contact_name, 'Asha Rao')
        self.assertEqual(lead.email_from, 'asha@example.com')
        self.assertIn('Club enquiry', lead.name)
        self.assertIn('Silver', lead.description)
        self.assertIn('coaching', lead.description)
        self.assertEqual(lead.tag_ids.name, 'Club Enquiry')

    def test_name_required(self):
        with self.assertRaises(ValidationError):
            self.env['crm.lead'].create_club_enquiry('  ', email='a@b.com')

    def test_contact_method_required(self):
        with self.assertRaises(ValidationError):
            self.env['crm.lead'].create_club_enquiry('Asha')

    def test_invalid_email_rejected(self):
        with self.assertRaises(ValidationError):
            self.env['crm.lead'].create_club_enquiry('Asha', email='not-an-email')

    def test_unknown_plan_rejected(self):
        with self.assertRaises(ValidationError):
            self.env['crm.lead'].create_club_enquiry('Asha', email='a@b.com', plan='platinum')

    def test_html_in_message_is_escaped(self):
        lead = self.env['crm.lead'].create_club_enquiry(
            'Asha', email='a@b.com', message='<script>alert(1)</script>')
        self.assertNotIn('<script>', lead.description)


@tagged('post_install', '-at_install', 'club_management')
class TestEnquiryHttp(HttpCase):

    def setUp(self):
        super().setUp()
        self.authenticate(None, None)   # anonymous session, needed for a CSRF token

    def _post(self, **data):
        data['csrf_token'] = http.Request.csrf_token(self)
        return self.url_open('/club/enquiry', data=data, allow_redirects=False)

    def test_public_post_creates_lead(self):
        before = self.env['crm.lead'].search_count([])
        response = self._post(name='Ravi', email='ravi@example.com', plan='gold')
        self.assertEqual(response.status_code, 200)
        body = json.loads(response.text)
        self.assertTrue(body['success'])
        lead = self.env['crm.lead'].browse(body['lead_id'])
        self.assertEqual(lead.contact_name, 'Ravi')
        self.assertEqual(self.env['crm.lead'].search_count([]), before + 1)

    def test_invalid_post_returns_400_and_no_lead(self):
        before = self.env['crm.lead'].search_count([])
        response = self._post(name='Ravi')
        self.assertEqual(response.status_code, 400)
        self.assertFalse(json.loads(response.text)['success'])
        self.assertEqual(self.env['crm.lead'].search_count([]), before)

    def test_redirect_only_to_local_paths(self):
        ok = self._post(name='Ravi', email='r@example.com', redirect='/thanks')
        self.assertIn(ok.status_code, (301, 302, 303))
        self.assertTrue(ok.headers['Location'].endswith('/thanks'))
        for target in ('//evil.example', 'https://evil.example', '/\\evil.example'):
            response = self._post(name='Ravi', email='r2@example.com', redirect=target)
            self.assertEqual(response.status_code, 200)
            self.assertTrue(json.loads(response.text)['success'])

    def test_post_without_csrf_token_rejected(self):
        response = self.url_open('/club/enquiry', data={'name': 'Ravi', 'email': 'r@example.com'})
        self.assertEqual(response.status_code, 400)
