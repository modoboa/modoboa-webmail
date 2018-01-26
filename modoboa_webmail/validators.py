"""Custom form validators."""

from email.utils import getaddresses

from django.utils.encoding import force_text
from django.core.validators import validate_email


class EmailListValidator(object):

    """Validate a list of email."""

    def __call__(self, value):
        value = force_text(value)
        addresses = getaddresses([value])
        [validate_email(email) for name, email in addresses if email]


validate_email_list = EmailListValidator()
