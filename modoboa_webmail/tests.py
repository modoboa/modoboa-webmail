"""Webmail tests."""

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
            self.untagged_responses["CAPABILITY"] = [""]
        elif name == "LIST":
            self.untagged_responses["LIST"] = ["() \".\" \"INBOX\""]
        return "OK", None

    def append(self, *args, **kwargs):
        pass

    def create(self, name):
        return "OK", None

    def delete(self, name):
        return "OK", None

    def list(self):
        return "OK", ["() \".\" \"INBOX\""]

    def rename(self, oldname, newname):
        return "OK", None


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
            url, {"to": "test@example.test", "subject": "test", "body": "Test"}
        )
        self.assertEqual(len(mail.outbox), 1)

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
        self.assertContains(response, "Create a new mailbox")

        response = self.ajax_post(url, {"name": "Test"})
        self.assertIn("newmb", response)

    def test_edit_folder(self):
        """Test folder edition."""
        url = reverse("modoboa_webmail:folder_change")
        response = self.client.get(url)
        self.assertContains(response, "Invalid request")

        url = "{}?name=Test".format(url)
        response = self.client.get(url)
        self.assertContains(response, "Edit mailbox")

        session = self.client.session
        session["webmail_navparams"] = {"inbox": "Test"}
        session.save()
        response = self.ajax_post(url, {"oldname": "Test", "name": "Toto"})
        self.assertEqual(response["respmsg"], "Mailbox updated")

    def test_delete_folder(self):
        """Test folder removal."""
        url = reverse("modoboa_webmail:folder_delete")
        self.ajax_get(url, status=400)

        url = "{}?name=Test".format(url)
        session = self.client.session
        session["webmail_navparams"] = {"inbox": "Test"}
        session.save()
        self.ajax_get(url)
