from odoo import api, models
from odoo.exceptions import ValidationError
from odoo.tools import email_normalize, plaintext2html


class CrmLead(models.Model):
    _inherit = 'crm.lead'

    @api.model
    def create_club_enquiry(self, name, email=None, phone=None, message=None,
                            plan=None, sport=None):
        """Create a CRM lead from a public membership enquiry.

        Runs with elevated rights because website visitors are anonymous.
        Raises ValidationError with a user-presentable message on bad input.
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
        plan_name = ''
        if plan:
            plan_rec = self.env['club.membership.plan'].sudo().search([('code', '=', plan)], limit=1)
            if not plan_rec:
                raise ValidationError("Unknown membership plan.")
            plan_name = plan_rec.name

        lines = []
        if plan_name:
            lines.append("Interested plan: %s" % plan_name)
        if sport:
            lines.append("Sport: %s" % sport.strip()[:50])
        if message:
            lines.append(message.strip()[:2000])
        tag = self.env.ref('club_management.crm_tag_club_enquiry', raise_if_not_found=False)
        return self.sudo().create({
            'name': "Club enquiry: %s" % name[:100],
            'contact_name': name[:100],
            'email_from': email_normalize(email) or False,
            'phone': phone[:30] or False,
            'description': plaintext2html("\n".join(lines)) if lines else False,
            'tag_ids': [(4, tag.id)] if tag else [],
        })
