"""Webmail tests."""

import os
import shutil
import tempfile

from six import BytesIO

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
