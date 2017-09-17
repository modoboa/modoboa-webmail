# coding: utf-8

"""Webmail tests."""

from __future__ import unicode_literals

import os
import shutil
import tempfile

import mock
from six import BytesIO

from django.core import mail
from django.core.urlresolvers import reverse

from modoboa.admin import factories as admin_factories
from modoboa.core import models as core_models
from modoboa.lib.tests import ModoTestCase


BODYSTRUCTURE_SAMPLE_WITH_FLAGS = [
    (b'19 (UID 19 FLAGS (\\Seen) BODYSTRUCTURE (("text" "plain" ("charset" "ISO-8859-1" "format" "flowed") NIL NIL "7bit" 2 1 NIL NIL NIL NIL)("message" "rfc822" ("name*" "ISO-8859-1\'\'%5B%49%4E%53%43%52%49%50%54%49%4F%4E%5D%20%52%E9%63%E9%70%74%69%6F%6E%20%64%65%20%76%6F%74%72%65%20%64%6F%73%73%69%65%72%20%64%27%69%6E%73%63%72%69%70%74%69%6F%6E%20%46%72%65%65%20%48%61%75%74%20%44%E9%62%69%74") NIL NIL "8bit" 3632 ("Wed, 13 Dec 2006 20:30:02 +0100" {70}',  # noqa
     b"[INSCRIPTION] R\xe9c\xe9ption de votre dossier d'inscription Free Haut D\xe9bit"),  # noqa
    (b' (("Free Haut Debit" NIL "inscription" "freetelecom.fr")) (("Free Haut Debit" NIL "inscription" "freetelecom.fr")) ((NIL NIL "hautdebit" "freetelecom.fr")) ((NIL NIL "nguyen.antoine" "wanadoo.fr")) NIL NIL NIL "<20061213193125.9DA0919AC@dgroup2-2.proxad.net>") ("text" "plain" ("charset" "iso-8859-1") NIL NIL "8bit" 1428 38 NIL ("inline" NIL) NIL NIL) 76 NIL ("inline" ("filename*" "ISO-8859-1\'\'%5B%49%4E%53%43%52%49%50%54%49%4F%4E%5D%20%52%E9%63%E9%70%74%69%6F%6E%20%64%65%20%76%6F%74%72%65%20%64%6F%73%73%69%65%72%20%64%27%69%6E%73%63%72%69%70%74%69%6F%6E%20%46%72%65%65%20%48%61%75%74%20%44%E9%62%69%74")) NIL NIL) "mixed" ("boundary" "------------040706080908000209030901") NIL NIL NIL) BODY[HEADER.FIELDS (DATE FROM TO CC SUBJECT)] {266}',  # noqa
     b'Date: Tue, 19 Dec 2006 19:50:13 +0100\r\nFrom: Antoine Nguyen <nguyen.antoine@wanadoo.fr>\r\nTo: Antoine Nguyen <tonio@koalabs.org>\r\nSubject: [Fwd: [INSCRIPTION] =?ISO-8859-1?Q?R=E9c=E9ption_de_votre_?=\r\n =?ISO-8859-1?Q?dossier_d=27inscription_Free_Haut_D=E9bit=5D?=\r\n\r\n'
    ),
    b')'
]


def get_gif():
    """Return gif."""
    gif = BytesIO(
        b"GIF87a\x01\x00\x01\x00\x80\x01\x00\x00\x00\x00ccc,\x00"
        b"\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;")
    gif.name = "image.gif"
    return gif


class IMAP4Mock(object):
    """Fake IMAP4 client."""

    def __init__(self, *args, **kwargs):
        self.untagged_responses = {}

    def _quote(self, data):
        return data

    def _simple_command(self, name, *args, **kwargs):
        if name == "CAPABILITY":
            self.untagged_responses["CAPABILITY"] = [b""]
        elif name == "LIST":
            self.untagged_responses["LIST"] = [b"() \".\" \"INBOX\""]
        return "OK", None

    def append(self, *args, **kwargs):
        pass

    def create(self, name):
        return "OK", None

    def delete(self, name):
        return "OK", None

    def list(self):
        return "OK", [b"() \".\" \"INBOX\""]

    def rename(self, oldname, newname):
        return "OK", None

    def uid(self, command, *args):
        if command == "SORT":
            return "OK", [b"19"]
        elif command == "FETCH":
            return "OK", BODYSTRUCTURE_SAMPLE_WITH_FLAGS


class WebmailTestCase(ModoTestCase):
    """Check webmail backend."""

    @classmethod
    def setUpTestData(cls):
        """Create some users."""
        super(WebmailTestCase, cls).setUpTestData()
        admin_factories.populate_database()
        cls.user = core_models.User.objects.get(username="user@test.com")

    def setUp(self):
        """Connect with a simpler user."""
        patcher = mock.patch("imaplib.IMAP4")
        self.mock_imap4 = patcher.start()
        self.mock_imap4.return_value = IMAP4Mock()
        self.addCleanup(patcher.stop)
        self.set_global_parameter("imap_port", 1435)
        self.workdir = tempfile.mkdtemp()
        os.mkdir("{}/webmail".format(self.workdir))
        url = reverse("core:login")
        data = {
            "username": self.user.username, "password": "toto"
        }
        self.client.post(url, data)

    def tearDown(self):
        """Cleanup."""
        shutil.rmtree(self.workdir)

    def test_listmailbox(self):
        """Check listmailbox action."""
        url = reverse("modoboa_webmail:index")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        response = self.client.get(
            "{}?action=listmailbox".format(url),
            HTTP_X_REQUESTED_WITH="XMLHttpRequest"
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(
            "nguyen.antoine@wanadoo.fr", response.json()["listing"])

        response = self.client.get(
            "{}?action=listmailbox&pattern=Réception&criteria=Subject"
            .format(url),
            HTTP_X_REQUESTED_WITH="XMLHttpRequest"
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(
            "nguyen.antoine@wanadoo.fr", response.json()["listing"])

    def test_attachments(self):
        """Check attachments."""
        url = reverse("modoboa_webmail:index")
        response = self.client.get("{}?action=compose".format(url))
        self.assertEqual(response.status_code, 200)
        self.assertIn("compose_mail", self.client.session)
        url = reverse("modoboa_webmail:attachment_list")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        with self.settings(MEDIA_ROOT=self.workdir):
            response = self.client.post(url, {"attachment": get_gif()})
        self.assertContains(response, "Attachment is too big")

        self.set_global_parameters({"max_attachment_size": "10K"})
        with self.settings(MEDIA_ROOT=self.workdir):
            response = self.client.post(url, {"attachment": get_gif()})
        self.assertContains(response, "upload_success")
        self.assertEqual(
            len(self.client.session["compose_mail"]["attachments"]), 1)
        name = self.client.session["compose_mail"]["attachments"][0]["tmpname"]
        path = "{}/webmail/{}".format(self.workdir, name)
        self.assertTrue(os.path.exists(path))

        url = reverse("modoboa_webmail:attachment_delete")
        with self.settings(MEDIA_ROOT=self.workdir):
            self.ajax_get("{}?name={}".format(url, name))
        self.assertFalse(os.path.exists(path))

    def test_delattachment_errors(self):
        """Check error cases."""
        url = reverse("modoboa_webmail:index")
        response = self.client.get("{}?action=compose".format(url))
        self.assertEqual(response.status_code, 200)
        self.assertIn("compose_mail", self.client.session)

        url = reverse("modoboa_webmail:attachment_delete")
        with self.settings(MEDIA_ROOT=self.workdir):
            response = self.ajax_get("{}?name=".format(url))
        self.assertEqual(response["status"], "ko")
        self.assertEqual(response["respmsg"], "Bad query")

        with self.settings(MEDIA_ROOT=self.workdir):
            response = self.ajax_get("{}?name=test".format(url))
        self.assertEqual(response["status"], "ko")
        self.assertEqual(response["respmsg"], "Unknown attachment")

    def test_send_mail(self):
        """Check compose form."""
        url = "{}?action=compose".format(reverse("modoboa_webmail:index"))
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        response = self.client.post(
            url, {
                "from_": self.user.email, "to": "test@example.test",
                "subject": "test", "body": "Test"
            }
        )
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(
            mail.outbox[0].from_email, "user@test.com")

        # Try to send an email using HTML format
        self.user.first_name = "Antoine"
        self.user.last_name = "Nguyen"
        self.user.parameters.set_value("editor", "html")
        self.user.save()
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        mail.outbox = []
        response = self.client.post(
            url, {
                "from_": self.user.email,
                "to": "test@example.test", "subject": "test",
                "body": "<p>Test</p>"
            }
        )
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(
            mail.outbox[0].from_email, '"Antoine Nguyen" <user@test.com>')

    def test_signature(self):
        """Check signature in different formats."""
        signature = "Antoine Nguyen"
        self.user.parameters.set_value("signature", signature)
        self.user.save()

        response = self.client.get(reverse("modoboa_webmail:index"))
        self.assertEqual(response.status_code, 200)

        url = "{}?action=compose".format(reverse("modoboa_webmail:index"))
        response = self.ajax_get(url)
        self.assertIn(signature, response["listing"])

    def test_custom_js_in_preferences(self):
        """Check that custom js is included."""
        url = reverse("core:user_index")
        response = self.client.get(url)
        self.assertContains(response, "function toggleSignatureEditor()")

    def test_send_mail_errors(self):
        """Check error cases."""
        url = "{}?action=compose".format(reverse("modoboa_webmail:index"))
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        response = self.ajax_post(
            url, {"to": "", "subject": "test", "body": "Test"}, 400
        )
        self.assertEqual(len(mail.outbox), 0)

    def test_new_folder(self):
        """Test folder creation."""
        url = reverse("modoboa_webmail:folder_add")
        response = self.client.get(url)
        self.assertContains(response, "Create a new folder")

        response = self.ajax_post(url, {"name": "Test"})
        self.assertIn("newmb", response)

    def test_edit_folder(self):
        """Test folder edition."""
        url = reverse("modoboa_webmail:folder_change")
        response = self.client.get(url)
        self.assertContains(response, "Invalid request")

        url = "{}?name=Test".format(url)
        response = self.client.get(url)
        self.assertContains(response, "Edit folder")

        session = self.client.session
        session["webmail_navparams"] = {"inbox": "Test"}
        session.save()
        response = self.ajax_post(url, {"oldname": "Test", "name": "Toto"})
        self.assertEqual(response["respmsg"], "Folder updated")

    def test_delete_folder(self):
        """Test folder removal."""
        url = reverse("modoboa_webmail:folder_delete")
        self.ajax_get(url, status=400)

        url = "{}?name=Test".format(url)
        session = self.client.session
        session["webmail_navparams"] = {"inbox": "Test"}
        session.save()
        self.ajax_get(url)
