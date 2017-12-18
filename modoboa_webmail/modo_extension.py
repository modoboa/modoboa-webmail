# coding: utf-8
"""Declare and register the webmail extension."""

from django.urls import reverse_lazy
from django.utils.translation import ugettext_lazy

from modoboa.core.extensions import ModoExtension, exts_pool
from modoboa.parameters import tools as param_tools

from . import __version__
from . import forms


class Webmail(ModoExtension):
    name = "modoboa_webmail"
    label = "Webmail"
    version = __version__
    description = ugettext_lazy("Simple IMAP webmail")
    needs_media = True
    url = "webmail"
    topredirection_url = reverse_lazy("modoboa_webmail:index")

    def load(self):
        param_tools.registry.add("global", forms.ParametersForm, "Webmail")
        param_tools.registry.add("user", forms.UserSettings, "Webmail")


exts_pool.register_extension(Webmail)
