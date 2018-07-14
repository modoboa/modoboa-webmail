# -*- coding: utf-8 -*-

"""DMARC related tools for Modoboa."""

from __future__ import unicode_literals

from pkg_resources import get_distribution, DistributionNotFound


try:
    __version__ = get_distribution(__name__).version
except DistributionNotFound:
    # package is not installed
    __version__ = '9.9.9'

default_app_config = "modoboa_webmail.apps.WebmailConfig"
