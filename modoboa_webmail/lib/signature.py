"""Tools to deal with message signatures."""

from django.utils.encoding import python_2_unicode_compatible


@python_2_unicode_compatible
class EmailSignature(object):
    """User signature.

    :param user: User object
    """

    def __init__(self, user):
        self._sig = u""
        dformat = user.parameters.get_value("editor")
        content = user.parameters.get_value("signature")
        if len(content):
            getattr(self, "_format_sig_%s" % dformat)(content)

    def _format_sig_plain(self, content):
        self._sig = u"""
---
%s""" % content

    def _format_sig_html(self, content):
        content = "---<br>{}".format(content)
        self._sig = content
        return

    def __str__(self):
        return self._sig
