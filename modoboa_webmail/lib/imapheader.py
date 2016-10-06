"""
Set of functions used to parse and transform email headers.
"""

import datetime
import email

import chardet
from django.conf import settings

from django.utils import timezone
from django.utils.formats import date_format

from modoboa.lib.email_utils import EmailAddress

__all__ = [
    'parse_from', 'parse_to', 'parse_message_id', 'parse_date',
    'parse_reply_to', 'parse_cc', 'parse_subject'
]


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
    # No datetime formatting if USE_L10N is False
    if not getattr(settings, "USE_L10N", False):
        return ndate
    if datetime.datetime.now() - ndate > datetime.timedelta(7):
        return date_format(ndate, getattr(settings, "WEBMAIL_DATETIME_FORMAT", 'r'))
    return date_format(ndate, getattr(settings, "WEBMAIL_SHORT_DATETIME_FORMAT", 'r'))



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
