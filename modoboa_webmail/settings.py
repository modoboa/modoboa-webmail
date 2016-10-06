"""Webmail default settings."""

# Webmail datetime formats according to
# https://docs.djangoproject.com/en/1.10/ref/templates/builtins/
# modoboa-webmail is able to show the datetime of emails
# in two ways.
# If none is provided, default is RFC 5322 formatted date.
# For this, USE_L10N must be set to True!

# emails of the last week
# en-us style
WEBMAIL_SHORT_DATETIME_FORMAT = "l, P"
# european style
# WEBMAIL_SHORT_DATETIME_FORMAT = "l, H:i"

# emails older than a week
# en-us style
WEBMAIL_DATETIME_FORMAT = "N, j Y P"
# european style
# WEBMAIL_DATETIME_FORMAT = "d. N Y H:i"
