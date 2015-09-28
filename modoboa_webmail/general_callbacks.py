"""General event callbacks."""

from django.utils.translation import ugettext as _
from django.core.urlresolvers import reverse

from modoboa.lib import events


@events.observe("UserMenuDisplay")
def menu(target, user):
    if target != "top_menu":
        return []
    if not hasattr(user, "mailbox"):
        return []
    return [
        {"name": "webmail",
         "label": _("Webmail"),
         "url": reverse("modoboa_webmail:index")},
    ]


@events.observe("UserLogout")
def userlogout(request):
    from .lib import IMAPconnector
    from .exceptions import ImapError

    if not hasattr(request.user, "mailbox"):
        return
    try:
        m = IMAPconnector(user=request.user.username,
                          password=request.session["password"])
    except Exception:
        # TODO silent exception are bad : we should at least log it
        return

    # The following statement may fail under Python 2.6...
    try:
        m.logout()
    except ImapError:
        pass
