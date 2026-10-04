import logging

from odoo import models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class ResUsers(models.Model):
    _inherit = 'res.users'

    def _club_send_invitation(self):
        """E-mail each user the link to choose a password. A mail problem is logged and
        left for staff to retry (the message stays queued); it never undoes the account.
        Returns True when every e-mail was sent."""
        sent = True
        for user in self:
            try:
                with self.env.cr.savepoint():
                    user.with_context(create_user=True).action_reset_password()
            except UserError as error:
                # Typically "could not contact the mail server": expected until SMTP is configured.
                _logger.warning("Sign-in invitation to %s not sent: %s", user.login, error.args[0])
                sent = False
            except Exception:    # noqa: BLE001
                _logger.exception("Could not e-mail the sign-in invitation to %s", user.login)
                sent = False
        return sent
