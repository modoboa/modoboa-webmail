"""Webmail handlers."""

from django.core.urlresolvers import reverse
from django.dispatch import receiver
from django.utils.translation import ugettext as _

from modoboa.core import signals as core_signals

from . import exceptions
from . import lib


@receiver(core_signals.extra_user_menu_entries)
def menu(sender, location, user, **kwargs):
    """Return extra menu entry."""
    if location != "top_menu" or not hasattr(user, "mailbox"):
        return []
    return [
        {"name": "webmail",
         "label": _("Webmail"),
         "url": reverse("modoboa_webmail:index")},
    ]


@receiver(core_signals.user_logout)
def userlogout(sender, request, **kwargs):
    """Close IMAP connection."""
    if not hasattr(request.user, "mailbox"):
        return
    try:
        m = lib.IMAPconnector(user=request.user.username,
                              password=request.session["password"])
    except Exception:
        # TODO silent exception are bad : we should at least log it
        return

    # The following statement may fail under Python 2.6...
    try:
        m.logout()
    except exceptions.ImapError:
        pass
