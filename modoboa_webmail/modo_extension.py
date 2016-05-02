# coding: utf-8
"""Declare and register the webmail extension."""

from django.utils.translation import ugettext_lazy

from modoboa.core.extensions import ModoExtension, exts_pool
from modoboa.lib import parameters

from . import __version__


class Webmail(ModoExtension):
    name = "modoboa_webmail"
    label = "Webmail"
    version = __version__
    description = ugettext_lazy("Simple IMAP webmail")
    needs_media = True
    available_for_topredirection = True
    url = "webmail"

    def load(self):
        from .app_settings import ParametersForm, UserSettings

        parameters.register(ParametersForm, "Webmail")
        parameters.register(UserSettings, "Webmail")
        from . import general_callbacks

exts_pool.register_extension(Webmail)
