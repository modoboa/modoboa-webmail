# coding: utf-8

"""Webmail forms."""

from email.header import Header
from email.mime.image import MIMEImage
import os
import pkg_resources

from six.moves.urllib.parse import urlparse, unquote

import lxml.html

from django import forms
from django.conf import settings
from django.core.mail import EmailMessage, EmailMultiAlternatives
from django.core.validators import validate_email
from django.utils.translation import ugettext_lazy as _

from ckeditor_uploader.widgets import CKEditorUploadingWidget

from modoboa.lib import email_utils, form_utils
from modoboa.parameters import forms as param_forms

from .lib import (
    ImapEmail, create_mail_attachment, decode_payload
)
from .validators import validate_email_list


def html2plaintext(content):
    """HTML to plain text translation.

    :param content: some HTML content
    """
    if not content:
        return ""
    html = lxml.html.fromstring(content)
    plaintext = ""
    for ch in html.iter():
        p = None
        if ch.text is not None:
            p = ch.text.strip('\r\t\n')
        if ch.tag == "img":
            p = ch.get("alt")
        if p is None:
            continue
        plaintext += p + "\n"
    return plaintext


def make_body_images_inline(body):
    """Looks for images inside the body and make them inline.

    Before sending a message in HTML format, it is necessary to find
    all img tags contained in the body in order to rewrite them. For
    example, icons provided by CKeditor are stored on the server
    filesystem and not accessible from the outside. We must embark
    them as parts of the MIME message if we want recipients to
    display them correctly.

    :param body: the HTML body to parse
    """
    html = lxml.html.fromstring(body)
    parts = []
    for tag in html.iter("img"):
        src = tag.get("src")
        if src is None:
            continue
        o = urlparse(src)
        path = unquote(os.path.join(settings.BASE_DIR, o.path[1:]))
        if not os.path.exists(path):
            continue
        fname = os.path.basename(path)
        cid = "%s@modoboa" % os.path.splitext(fname)[0]
        tag.set("src", "cid:%s" % cid)
        with open(path, "rb") as fp:
            part = MIMEImage(fp.read())
        part["Content-ID"] = "<%s>" % cid
        part.replace_header(
            "Content-Type", '%s; name="%s"' % (part["Content-Type"], fname)
        )
        part["Content-Disposition"] = "inline"
        parts.append(part)
    return lxml.html.tostring(html, encoding="unicode"), parts


class ComposeMailForm(forms.Form):
    """Compose mail form."""

    from_ = forms.ChoiceField(
        label=_("From"), choices=[],
        widget=forms.Select(attrs={"class": "selectize"})
    )
    to = forms.CharField(
        label=_("To"), validators=[validate_email_list])
    cc = forms.CharField(
        label=_("Cc"), required=False, validators=[validate_email_list],
        widget=forms.TextInput(
            attrs={"placeholder": _("Enter one or more addresses."),
                   "class": "selectize-contact"})
    )
    bcc = forms.CharField(
        label=_("Bcc"), required=False, validators=[validate_email_list],
        widget=forms.TextInput(
            attrs={"placeholder": _("Enter one or more addresses."),
                   "class": "selectize-contact"})
    )

    subject = forms.CharField(
        label=_("Subject"),
        max_length=255,
        required=False
    )
    origmsgid = forms.CharField(
        label="", required=False, widget=forms.HiddenInput())
    body = forms.CharField(
        required=False, widget=CKEditorUploadingWidget(
            attrs={"class": "editor form-control"})
    )

    def __init__(self, user, *args, **kwargs):
        """Custom constructor."""
        super(ComposeMailForm, self).__init__(*args, **kwargs)
        from_addresses = [(user.email, user.email)]
        for address in user.mailbox.alias_addresses:
            try:
                validate_email(address)
                from_addresses += [(address, address)]
            except forms.ValidationError:
                pass
        additional_sender_addresses = (
            user.mailbox.senderaddress_set.values_list("address", flat=True))
        from_addresses += [
            (address, address) for address in additional_sender_addresses]
        self.fields["from_"].choices = from_addresses
        self.fields["from_"].initial = user.email
        self.field_widths = {
            "cc": "11",
            "bcc": "11",
            "subject": "11"
        }

    def clean_to(self):
        """Convert to a list."""
        to = self.cleaned_data["to"]
        return email_utils.prepare_addresses(to, "envelope")

    def clean_cc(self):
        """Convert to a list."""
        cc = self.cleaned_data["cc"]
        return email_utils.prepare_addresses(cc, "envelope")

    def clean_bcc(self):
        """Convert to a list."""
        bcc = self.cleaned_data["bcc"]
        return email_utils.prepare_addresses(bcc, "envelope")

    def _html_msg(self, sender, headers):
        """Create a multipart message.

        We attach two alternatives:
        * text/html
        * text/plain
        """
        body = self.cleaned_data["body"]
        if body:
            tbody = html2plaintext(body)
            body, images = make_body_images_inline(body)
        else:
            tbody = ""
            images = []
        msg = EmailMultiAlternatives(
            self.cleaned_data["subject"],
            tbody,
            sender, self.cleaned_data["to"],
            cc=self.cleaned_data["cc"],
            bcc=self.cleaned_data["bcc"],
            headers=headers
        )
        msg.attach_alternative(body, "text/html")
        for img in images:
            msg.attach(img)
        return msg

    def _plain_msg(self, sender, headers):
        """Create a simple text message."""
        msg = EmailMessage(
            self.cleaned_data["subject"],
            self.cleaned_data["body"],
            sender,
            self.cleaned_data["to"],
            cc=self.cleaned_data["cc"],
            bcc=self.cleaned_data["bcc"],
            headers=headers
        )
        return msg

    def _format_sender_address(self, user, address):
        """Format address before message is sent."""
        if user.first_name != "" or user.last_name != "":
            return '"{}" <{}>'.format(
                Header(user.fullname, "utf8"), address)
        return address

    def _build_msg(self, request):
        """Build message to send.

        Can be overidden by children.
        """
        headers = {
            "User-Agent": "Modoboa {}".format(
                pkg_resources.get_distribution("modoboa").version)
        }
        origmsgid = self.cleaned_data.get("origmsgid")
        if origmsgid:
            headers.update({
                "References": origmsgid,
                "In-Reply-To": origmsgid
            })
        mode = request.user.parameters.get_value("editor")
        sender = self._format_sender_address(
            request.user, self.cleaned_data["from_"])
        return getattr(self, "_{}_msg".format(mode))(sender, headers)

    def to_msg(self, request):
        """Convert form's content to an object ready to send."""
        msg = self._build_msg(request)
        if request.session["compose_mail"]["attachments"]:
            for attdef in request.session["compose_mail"]["attachments"]:
                msg.attach(create_mail_attachment(attdef))
        return msg


class ForwardMailForm(ComposeMailForm):
    """Forward mail form."""

    def _build_msg(self, request):
        """Convert form's content to a MIME message.

        We also add original attachments (if any) to the new message.
        """
        mbox = request.GET.get("mbox", None)
        mailid = request.GET.get("mailid", None)
        msg = super(ForwardMailForm, self)._build_msg(request)
        origmsg = ImapEmail(request, "%s:%s" % (mbox, mailid))
        if origmsg.attachments:
            for attpart, fname in origmsg.attachments.items():
                attdef, payload = origmsg.fetch_attachment(attpart)
                attdef["fname"] = fname
                msg.attach(create_mail_attachment(
                    attdef, decode_payload(attdef["encoding"], payload)
                ))
        return msg


class FolderForm(forms.Form):
    oldname = forms.CharField(
        label="",
        widget=forms.HiddenInput(attrs={"class": "form-control"}),
        required=False
    )
    name = forms.CharField(
        widget=forms.TextInput(attrs={"class": "form-control"}))


class AttachmentForm(forms.Form):
    attachment = forms.FileField(label=_("Select a file"), allow_empty_file=True)


class ParametersForm(param_forms.AdminParametersForm):
    app = "modoboa_webmail"

    sep3 = form_utils.SeparatorField(label=_("General"))

    max_attachment_size = forms.CharField(
        label=_("Maximum attachment size"),
        initial="2048",
        help_text=_(
            "Maximum attachment size in bytes (or KB, MB, GB if specified)")
    )

    sep1 = form_utils.SeparatorField(label=_("IMAP settings"))

    imap_server = forms.CharField(
        label=_("Server address"),
        initial="127.0.0.1",
        help_text=_("Address of your IMAP server")
    )

    imap_secured = form_utils.YesNoField(
        label=_("Use a secured connection"),
        initial=False,
        help_text=_("Use a secured connection to access IMAP server")
    )

    imap_port = forms.IntegerField(
        label=_("Server port"),
        initial=143,
        help_text=_("Listening port of your IMAP server")
    )

    sep2 = form_utils.SeparatorField(label=_("SMTP settings"))

    smtp_server = forms.CharField(
        label=_("Server address"),
        initial="127.0.0.1",
        help_text=_("Address of your SMTP server")
    )

    smtp_secured_mode = forms.ChoiceField(
        label=_("Secured connection mode"),
        choices=[("none", _("None")),
                 ("starttls", "STARTTLS"),
                 ("ssl", "SSL/TLS")],
        initial="none",
        help_text=_("Use a secured connection to access SMTP server"),
        widget=form_utils.HorizontalRadioSelect()
    )

    smtp_port = forms.IntegerField(
        label=_("Server port"),
        initial=25,
        help_text=_("Listening port of your SMTP server")
    )

    smtp_authentication = form_utils.YesNoField(
        label=_("Authentication required"),
        initial=False,
        help_text=_("Server needs authentication")
    )


class UserSettings(param_forms.UserParametersForm):
    app = "modoboa_webmail"

    sep1 = form_utils.SeparatorField(label=_("Display"))

    displaymode = forms.ChoiceField(
        initial="plain",
        label=_("Default message display mode"),
        choices=[("html", "html"), ("plain", "text")],
        help_text=_("The default mode used when displaying a message"),
        widget=form_utils.HorizontalRadioSelect()
    )

    enable_links = form_utils.YesNoField(
        initial=False,
        label=_("Enable HTML links display"),
        help_text=_("Enable/Disable HTML links display")
    )

    messages_per_page = forms.IntegerField(
        initial=40,
        label=_("Number of displayed emails per page"),
        help_text=_("Sets the maximum number of messages displayed in a page")
    )

    refresh_interval = forms.IntegerField(
        initial=300,
        label=_("Listing refresh rate"),
        help_text=_("Automatic folder refresh rate (in seconds)")
    )

    mboxes_col_width = forms.IntegerField(
        initial=200,
        label=_("Folder container's width"),
        help_text=_("The width of the folder list container")
    )

    sep2 = form_utils.SeparatorField(label=_("Folders"))

    trash_folder = forms.CharField(
        initial="Trash",
        label=_("Trash folder"),
        help_text=_("Folder where deleted messages go")
    )

    sent_folder = forms.CharField(
        initial="Sent",
        label=_("Sent folder"),
        help_text=_("Folder where copies of sent messages go")
    )

    drafts_folder = forms.CharField(
        initial="Drafts",
        label=_("Drafts folder"),
        help_text=_("Folder where drafts go")
    )
    junk_folder = forms.CharField(
        initial="Junk",
        label=_("Junk folder"),
        help_text=_("Folder where junk messages should go")
    )

    sep3 = form_utils.SeparatorField(label=_("Composing messages"))

    editor = forms.ChoiceField(
        initial="plain",
        label=_("Default editor"),
        choices=[("html", "html"), ("plain", "text")],
        help_text=_("The default editor to use when composing a message"),
        widget=form_utils.HorizontalRadioSelect()
    )

    signature = forms.CharField(
        initial="",
        label=_("Signature text"),
        help_text=_("User defined email signature"),
        required=False,
        widget=CKEditorUploadingWidget()
    )

    visibility_rules = {
        "enable_links": "displaymode=html"
    }

    @staticmethod
    def has_access(**kwargs):
        return hasattr(kwargs.get("user"), "mailbox")

    def clean_mboxes_col_width(self):
        """Check if the entered value is a positive integer.

        It must also be different from 0.
        """
        if self.cleaned_data['mboxes_col_width'] <= 0:
            raise forms.ValidationError(
                _('Value must be a positive integer (> 0)')
            )
        return self.cleaned_data['mboxes_col_width']
