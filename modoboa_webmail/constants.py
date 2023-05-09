"""Webmail constants."""

from django.utils.translation import gettext_lazy as _


SORT_ORDERS = [
    ("date", _("Date")),
    ("from", _("Sender")),
    ("size", _("Size")),
    ("subject", _("Subject")),
]
