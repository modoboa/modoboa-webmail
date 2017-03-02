"""AppConfig for webmail."""

from django.apps import AppConfig


class WebmailConfig(AppConfig):
    """App configuration."""

    name = "modoboa_webmail"
    verbose_name = "Simple webmail for Modoboa"

    def ready(self):
        from . import handlers
