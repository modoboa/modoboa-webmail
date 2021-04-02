"""Webmail constants."""

import os

from django.conf import settings
from django.utils.translation import ugettext_lazy as _


SORT_ORDERS = [
    ("date", _("Date")),
    ("from", _("Sender")),
    ("size", _("Size")),
    ("subject", _("Subject")),
]

WEBMAIL_STORAGE_DIR = os.path.join(settings.MEDIA_ROOT, "webmail")
