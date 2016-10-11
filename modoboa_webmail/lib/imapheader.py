"""
Set of functions used to parse and transform email headers.
"""

import datetime
import email

import chardet

from django.utils import timezone
from django.utils.formats import date_format

from modoboa.lib.email_utils import EmailAddress
from modoboa.lib.signals import get_request


__all__ = [
    'parse_from', 'parse_to', 'parse_message_id', 'parse_date',
    'parse_reply_to', 'parse_cc', 'parse_subject'
]

# date and time formats for email list
# according to https://en.wikipedia.org/wiki/Date_format_by_country
# and https://en.wikipedia.org/wiki/Date_and_time_representation_by_country
DATETIME_FORMATS = {
    "cs": {'SHORT': 'l, H:i', 'LONG': 'd. N Y H:i'},
    "de": {'SHORT': 'l, H:i', 'LONG': 'd. N Y H:i'},
    "en": {'SHORT': 'l, P', 'LONG': 'N j, Y P'},
    "es": {'SHORT': 'l, H:i', 'LONG': 'd. N Y H:i'},
    "fr": {'SHORT': 'l, H:i', 'LONG': 'd. N Y H:i'},
    "it": {'SHORT': 'l, H:i', 'LONG': 'd. N Y H:i'},
    "ja_JP": {'SHORT': 'l, P', 'LONG': 'N j, Y P'},
    "nl": {'SHORT': 'l, H:i', 'LONG': 'd. N Y H:i'},
    "pt_PT": {'SHORT': 'l, H:i', 'LONG': 'd. N Y H:i'},
    "pt_BR": {'SHORT': 'l, H:i', 'LONG': 'd. N Y H:i'},
    "ru": {'SHORT': 'l, H:i', 'LONG': 'd. N Y H:i'},
    "sv": {'SHORT': 'l, H:i', 'LONG': 'd. N Y H:i'},
}


def to_unicode(value):
    """Try to convert a string to unicode.
    """
    if value is None or isinstance(value, unicode):
        return value
    try:
        value = value.decode('utf-8')
    except UnicodeDecodeError:
        pass
    else:
        return value
    try:
        res = chardet.detect(value)
    except UnicodeDecodeError:
        return value
    if res["encoding"] == "ascii":
        return value
    return value.decode(res["encoding"])


def parse_address(value, **kwargs):
    """Parse an email address.
    """
    addr = EmailAddress(value)
    if "full" in kwargs.keys() and kwargs["full"]:
        return to_unicode(addr.fulladdress)
    result = addr.name and addr.name or addr.fulladdress
    return to_unicode(result)


def parse_address_list(values, **kwargs):
    """Parse a list of email addresses.
    """
    lst = values.split(",")
    result = ""
    for addr in lst:
        if result != "":
            result += ", "
        result += parse_address(addr, **kwargs)
    return result


def parse_from(value, **kwargs):
    """Parse a From: header.
    """
    return parse_address(value, **kwargs)


def parse_to(value, **kwargs):
    """Parse a To: header.
    """
    return parse_address_list(value, **kwargs)


def parse_cc(value, **kwargs):
    """Parse a Cc: header.
    """
    return parse_address_list(value, **kwargs)


def parse_reply_to(value, **kwargs):
    """Parse a Reply-To: header.
    """
    return parse_address_list(value, **kwargs)


def parse_date(value, **kwargs):
    """Parse a Date: header."""
    tmp = email.utils.parsedate_tz(value)
    if not tmp:
        return value
    ndate = datetime.datetime.fromtimestamp(email.utils.mktime_tz(tmp))
    if ndate.tzinfo is not None:
        tz = timezone.get_current_timezone()
        ndate = tz.localize(datetime.datetime.fromtimestamp(ndate))
    current_language = get_request().user.language
    if datetime.datetime.now() - ndate > datetime.timedelta(7):
        return date_format(ndate, DATETIME_FORMATS[current_language]['LONG'])
    return date_format(ndate, DATETIME_FORMATS[current_language]['SHORT'])


def parse_message_id(value, **kwargs):
    """Parse a Message-ID: header."""
    return value.strip('\n')


def parse_subject(value, **kwargs):
    """Parse a Subject: header.
    """
    from modoboa.lib import u2u_decode

    try:
        subject = u2u_decode.u2u_decode(value)
    except UnicodeDecodeError:
        subject = value
    return to_unicode(subject)
