"""
Set of classes to manipulate/display emails inside the webmail.
"""
import os
import re
import email

import chardet
import six

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.urls import reverse
from django.utils.encoding import smart_text
from django.utils.html import conditional_escape
from django.utils.translation import ugettext as _

from modoboa.core.extensions import exts_pool
from modoboa.lib import u2u_decode
from modoboa.lib.email_utils import Email, EmailAddress

from . import imapheader
from .attachments import get_storage_path
from .imaputils import (
    get_imapconnector, BodyStructure
)
from .utils import decode_payload


class ImapEmail(Email):

    """
    A class to represent an email fetched from an IMAP server.
    """

    headernames = [
        ('From', True),
        ('To', True),
        ('Cc', True),
        ('Date', True),
        ('Subject', True),
    ]

    def __init__(self, request, *args, **kwargs):
        super(ImapEmail, self).__init__(*args, **kwargs)
        self.request = request
        self.imapc = get_imapconnector(request)
        self.mbox, self.mailid = self.mailid.split(":")

    def _insert_contact_links(self, addresses):
        """Insert 'add to address book' links."""
        result = []
        title = _("Add to contacts")
        url = reverse("api:contact-list")
        link_tpl = (
            u" <a class='addcontact' href='{}' title='{}'>"
            u"<span class='fa fa-vcard'></span></a>"
        )
        for address in addresses:
            address += link_tpl.format(url, title)
            result.append(address)
        return result

    def fetch_headers(self, raw_addresses=False):
        """Fetch message headers from server."""
        msg = self.imapc.fetchmail(
            self.mbox, self.mailid, readonly=False,
            what=" ".join(self.headers_as_list)
        )
        headers = msg["BODY[HEADER.FIELDS ({})]".format(self.headers_as_text)]
        self.fetch_body_structure(msg)
        msg = email.message_from_string(headers)
        contacts_plugin_installed = exts_pool.get_extension("modoboa_contacts")
        headers_with_address = ("From", "To", "Cc", "Reply-To")
        for hdr in self.headernames:
            label = hdr[0]
            hdrvalue = self.get_header(msg, label, raw=raw_addresses)
            if not hdrvalue:
                continue
            safe = False
            if hdr[1]:
                if label in headers_with_address:
                    if contacts_plugin_installed and not raw_addresses:
                        hdrvalue = self._insert_contact_links(hdrvalue)
                    hdrvalue = ", ".join(hdrvalue)
                    safe = True
                self.headers += [
                    {"name": label, "value": hdrvalue, "safe": safe}]
            label = re.sub("-", "_", label)
            setattr(self, label, hdrvalue)

    def get_header(self, msg, hdrname, **kwargs):
        """Look for a particular header.

        We also try to decode the default value.
        """
        hdrvalue = super().get_header(msg, hdrname)
        if hdrname in ["From", "Reply-To"]:
            # Store a raw copy for further use
            setattr(self, "original_{}".format(hdrname.replace("-", "")),
                    hdrvalue)
        if not hdrvalue:
            return ""
        try:
            key = re.sub("-", "_", hdrname).lower()
            hdrvalue = getattr(imapheader, "parse_%s" % key)(
                hdrvalue, **kwargs)
        except AttributeError:
            pass
        return hdrvalue

    def fetch_body_structure(self, msg=None):
        """Fetch BODYSTRUCTURE for email."""
        if msg is None:
            msg = self.imapc.fetchmail(
                self.mbox, self.mailid, readonly=False
            )
        self.bs = BodyStructure(msg["BODYSTRUCTURE"])
        self._find_attachments()
        if self.dformat not in ["plain", "html"]:
            self.dformat = self.request.user.parameters.get_value(
                self.dformat)
        fallback_fmt = "html" if self.dformat == "plain" else "plain"
        self.mformat = (
            self.dformat if self.dformat in self.bs.contents else fallback_fmt)

    @property
    def headers_as_list(self):
        return [hdr[0].upper() for hdr in self.headernames]

    @property
    def headers_as_text(self):
        return " ".join(self.headers_as_list)

    @property
    def body(self):
        """Load email's body.

        This operation has to be made "on demand" because it requires
        a communication with the IMAP server.
        """
        if self._body is None:
            self.fetch_body_structure()
            bodyc = u""
            parts = self.bs.contents.get(self.mformat, [])
            for part in parts:
                pnum = part["pnum"]
                data = self.imapc._cmd(
                    "FETCH", self.mailid, "(BODY.PEEK[%s])" % pnum
                )
                if not data or not int(self.mailid) in data:
                    continue
                content = decode_payload(
                    part["encoding"], data[int(self.mailid)]["BODY[%s]" % pnum]
                )
                if not isinstance(content, six.text_type):
                    charset = self._find_content_charset(part)
                    if charset is not None:
                        try:
                            content = content.decode(charset)
                        except (UnicodeDecodeError, LookupError):
                            result = chardet.detect(content)
                            content = content.decode(result["encoding"])
                bodyc += content
            self._fetch_inlines()
            bodyc = getattr(self, "_post_process_%s" % self.mformat)(bodyc)
            self._body = getattr(self, "viewmail_%s" % self.mformat)(
                bodyc, links=self.links
            )
        return self._body

    @body.setter
    def body(self, value):
        self._body = value

    @property
    def source(self):
        """Retrieve email source."""
        return self.imapc.fetchmail(
            self.mbox, self.mailid, what="source")['BODY[]']

    def _find_content_charset(self, part):
        for pos, elem in enumerate(part["params"]):
            if elem == "charset":
                return part["params"][pos + 1]
        return None

    def _find_attachments(self):
        """Retrieve attachments from the parsed body structure.

        We try to find and decode a file name for each attachment. If
        we failed, a generic name will be used (ie. part_1, part_2, ...).
        """
        for att in self.bs.attachments:
            attname = "part_{}".format(att["pnum"])
            if "params" in att and att["params"] != "NIL":
                for pos, value in enumerate(att["params"]):
                    if not value.startswith("name"):
                        continue
                    attname = (
                        u2u_decode.u2u_decode(att["params"][pos + 1])
                        .strip("\r\t\n")
                    )
                    break
            elif "disposition" in att and len(att["disposition"]) > 1:
                for pos, value in enumerate(att["disposition"][1]):
                    if not value.startswith("filename"):
                        continue
                    attname = u2u_decode.u2u_decode(
                        att["disposition"][1][pos + 1]
                    ).strip("\r\t\n")
                    break
            self.attachments[att["pnum"]] = smart_text(attname)

    def _fetch_inlines(self):
        """Store inline images on filesystem to display them."""
        for cid, params in list(self.bs.inlines.items()):
            if re.search(r"\.\.", cid):
                continue
            fname = "{}_{}".format(self.mailid, cid)
            path = get_storage_path(fname)
            params["fname"] = os.path.join(
                settings.MEDIA_URL,
                os.path.basename(get_storage_path("")),
                fname
            )
            if default_storage.exists(path):
                continue
            pdef, content = self.imapc.fetchpart(
                self.mailid, self.mbox, params["pnum"]
            )
            default_storage.save(
                path, ContentFile(decode_payload(params["encoding"], content)))

    def _map_cid(self, url):
        m = re.match(".*cid:(.+)", url)
        if m:
            if m.group(1) in self.bs.inlines:
                return self.bs.inlines[m.group(1)]["fname"]
        return url

    def fetch_attachment(self, pnum):
        """Fetch an attachment from the IMAP server."""
        return self.imapc.fetchpart(self.mailid, self.mbox, pnum)


class Modifier(ImapEmail):
    """Message modifier."""

    def __init__(self, form, request, *args, **kwargs):
        kwargs["dformat"] = request.user.parameters.get_value("editor")
        super(Modifier, self).__init__(request, *args, **kwargs)
        self.form = form
        self.fetch_headers(raw_addresses=True)
        getattr(self, "_modify_%s" % self.dformat)()

    def _modify_plain(self):
        self.body = re.sub("</?pre>", "", self.body)

    def _modify_html(self):
        if self.dformat == "html" and self.mformat != self.dformat:
            self.body = re.sub("</?pre>", "", self.body)
            self.body = re.sub("\n", "<br>", self.body)

    @property
    def subject(self):
        """Just a shortcut to return a subject in any case."""
        return self.Subject if hasattr(self, "Subject") else ""


class ReplyModifier(Modifier):
    """Modify a message to reply to it."""

    headernames = ImapEmail.headernames + [
        ("Reply-To", True),
        ("Message-ID", False)
    ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.textheader = u"%s %s" % (self.From, _("wrote:"))
        if self.dformat == "html":
            self.textheader = u"<p>{}</p>".format(self.textheader)
        if hasattr(self, "Message_ID"):
            self.form.fields["origmsgid"].initial = self.Message_ID
        if not hasattr(self, "Reply_To"):
            self.form.fields["to"].initial = self.original_From
        else:
            self.form.fields["to"].initial = self.original_ReplyTo
        if self.request.GET.get("all", "0") == "1":  # reply-all
            self.form.fields["cc"].initial = ""
            toparse = self.To.split(",")
            if hasattr(self, 'Cc'):
                toparse += self.Cc.split(",")
            for addr in toparse:
                tmp = EmailAddress(addr)
                if tmp.address and tmp.address == self.request.user.username:
                    continue
                if self.form.fields["cc"].initial != "":
                    self.form.fields["cc"].initial += ", "
                self.form.fields["cc"].initial += tmp.fulladdress
        m = re.match(r"re\s*:\s*.+", self.subject.lower())
        if m:
            self.form.fields["subject"].initial = self.subject
        else:
            self.form.fields["subject"].initial = "Re: %s" % self.subject

    def _modify_plain(self):
        super(ReplyModifier, self)._modify_plain()
        lines = self.body.split('\n')
        body = ""
        for l in lines:
            if body != "":
                body += "\n"
            body += ">%s" % l
        self.body = body


class ForwardModifier(Modifier):

    """Modify a message so it can be forwarded."""

    def __init__(self, *args, **kwargs):
        super(ForwardModifier, self).__init__(*args, **kwargs)
        self._header()
        self.form.fields["subject"].initial = u"Fwd: %s" % self.subject

    def __getfunc(self, name):
        return getattr(self, "%s_%s" % (name, self.dformat))

    def _header(self):
        self.textheader = u"{}\n".format(self.__getfunc("_header_begin")())
        self.textheader += (
            self.__getfunc("_header_line")(_("Subject"), self.subject))
        self.textheader += (
            self.__getfunc("_header_line")(_("Date"), self.Date))
        for hdr in ["From", "To", "Reply-To"]:
            try:
                key = re.sub("-", "_", hdr)
                value = getattr(self, key)
                self.textheader += (
                    self.__getfunc("_header_line")(_(hdr), value))
            except AttributeError:
                pass
        self.textheader += self.__getfunc("_header_end")()

    def _header_begin_plain(self):
        return u"----- %s -----" % _("Original message")

    def _header_begin_html(self):
        return u"----- %s -----" % _("Original message")

    def _header_line_plain(self, key, value):
        return u"%s: %s\n" % (key, value)

    def _header_line_html(self, key, value):
        return u"<p>%s: %s</p>" % (key, conditional_escape(value))

    def _header_end_plain(self):
        return u"\n"

    def _header_end_html(self):
        return u""
