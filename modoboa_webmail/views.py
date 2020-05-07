# coding: utf-8

"""Webmail extension views."""

import base64
import os

from django.conf import settings
from django.urls import reverse
from django.http import HttpResponse
from django.shortcuts import render
from django.template.loader import render_to_string
from django.utils.translation import ugettext as _, ungettext
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.gzip import gzip_page

from django.contrib.auth.decorators import login_required

from modoboa.admin.lib import needs_mailbox
from modoboa.core.extensions import exts_pool
from modoboa.lib.exceptions import ModoboaException, BadRequest
from modoboa.lib.paginator import Paginator
from modoboa.lib.web_utils import (
    ajax_response, render_to_json_response
)
from modoboa.parameters import tools as param_tools

from .exceptions import UnknownAction
from .forms import (
    FolderForm, AttachmentForm, ComposeMailForm, ForwardMailForm
)
from .lib import (
    decode_payload, AttachmentUploadHandler,
    save_attachment, EmailSignature,
    clean_attachments, set_compose_session, send_mail,
    ImapEmail, WebmailNavigationParameters, ReplyModifier, ForwardModifier,
    get_imapconnector, IMAPconnector, separate_mailbox, rfc6266
)
from .templatetags import webmail_tags


@login_required
@needs_mailbox()
@gzip_page
def getattachment(request):
    """Fetch a message attachment

    FIXME: par manque de caching, le bodystructure du message est
    redemandé pour accéder aux headers de cette pièce jointe.

    :param request: a ``Request`` object
    """
    mbox = request.GET.get("mbox", None)
    mailid = request.GET.get("mailid", None)
    pnum = request.GET.get("partnumber", None)
    fname = request.GET.get("fname", None)
    if not mbox or not mailid or not pnum or not fname:
        raise BadRequest(_("Invalid request"))

    imapc = get_imapconnector(request)
    partdef, payload = imapc.fetchpart(mailid, mbox, pnum)
    resp = HttpResponse(decode_payload(partdef["encoding"], payload))
    resp["Content-Type"] = partdef["Content-Type"]
    resp["Content-Transfer-Encoding"] = partdef["encoding"]
    resp["Content-Disposition"] = rfc6266.build_header(fname)
    if int(partdef["size"]) < 200:
        resp["Content-Length"] = partdef["size"]
    return resp


@login_required
@needs_mailbox()
def move(request):
    for arg in ["msgset", "to"]:
        if arg not in request.GET:
            raise BadRequest(_("Invalid request"))
    mbc = get_imapconnector(request)
    navparams = WebmailNavigationParameters(request)
    mbc.move(request.GET["msgset"], navparams.get('mbox'), request.GET["to"])
    resp = listmailbox(request, navparams.get('mbox'), update_session=False)
    return render_to_json_response(resp)


@login_required
@needs_mailbox()
def delete(request):
    mbox = request.GET.get("mbox", None)
    selection = request.GET.getlist("selection[]", None)
    if mbox is None or selection is None:
        raise BadRequest(_("Invalid request"))
    selection = [item for item in selection if item.isdigit()]
    mbc = get_imapconnector(request)
    mbc.move(",".join(selection), mbox,
             request.user.parameters.get_value("trash_folder"))
    count = len(selection)
    message = ungettext("%(count)d message deleted",
                        "%(count)d messages deleted",
                        count) % {"count": count}
    return render_to_json_response(message)


@login_required
@needs_mailbox()
def mark(request, name):
    status = request.GET.get("status", None)
    ids = request.GET.get("ids", None)
    if status is None or ids is None:
        raise BadRequest(_("Invalid request"))
    imapc = get_imapconnector(request)
    try:
        getattr(imapc, "mark_messages_%s" % status)(name, ids)
    except AttributeError:
        raise UnknownAction

    return render_to_json_response({
        'action': status, 'mbox': name,
        'unseen': imapc.unseen_messages(name)
    })


def _move_selection_to_folder(request, folder):
    """Move selected messages to the given folder."""
    mbox = request.GET.get("mbox")
    selection = request.GET.getlist("selection[]")
    if mbox is None or selection is None:
        raise BadRequest(_("Invalid request"))
    selection = [item for item in selection if item.isdigit()]
    mbc = get_imapconnector(request)
    mbc.move(",".join(selection), mbox, folder)
    return len(selection)


@login_required
@needs_mailbox()
def mark_as_junk(request):
    """Mark a message as SPAM."""
    count = _move_selection_to_folder(
        request, request.user.parameters.get_value("junk_folder"))
    message = ungettext("%(count)d message marked",
                        "%(count)d messages marked",
                        count) % {"count": count}
    return render_to_json_response(message)


@login_required
@needs_mailbox()
def mark_as_not_junk(request):
    """Mark a message as not SPAM."""
    count = _move_selection_to_folder(request, "INBOX")
    message = ungettext("%(count)d message marked",
                        "%(count)d messages marked",
                        count) % {"count": count}
    return render_to_json_response(message)


@login_required
@needs_mailbox()
def empty(request):
    """Empty the trash folder."""
    name = request.GET.get("name", None)
    if name != request.user.parameters.get_value("trash_folder"):
        raise BadRequest(_("Invalid request"))
    get_imapconnector(request).empty(name)
    content = u"<div class='alert alert-info'>%s</div>" % _("Empty folder")
    return render_to_json_response({
        'listing': content, 'mailbox': name, 'pages': [1]
    })


@login_required
@needs_mailbox()
def folder_compress(request):
    """Compress a mailbox."""
    name = request.GET.get("name", None)
    if name is None:
        raise BadRequest(_("Invalid request"))
    imapc = get_imapconnector(request)
    imapc.compact(name)
    return render_to_json_response({})


@login_required
@needs_mailbox()
def newfolder(request, tplname="modoboa_webmail/folder.html"):
    mbc = IMAPconnector(user=request.user.username,
                        password=request.session["password"])

    if request.method == "POST":
        form = FolderForm(request.POST)
        if form.is_valid():
            pf = request.POST.get("parent_folder", None)
            mbc.create_folder(form.cleaned_data["name"], pf)
            return render_to_json_response({
                'respmsg': _("Folder created"),
                'newmb': form.cleaned_data["name"], 'parent': pf
            })

        return render_to_json_response(
            {'form_errors': form.errors}, status=400)

    ctx = {"title": _("Create a new folder"),
           "formid": "mboxform",
           "action": reverse("modoboa_webmail:folder_add"),
           "action_label": _("Create"),
           "action_classes": "submit",
           "withunseen": False,
           "selectonly": True,
           "mboxes": mbc.getmboxes(request.user),
           "hdelimiter": mbc.hdelimiter,
           "form": FolderForm(),
           "selected": None}
    return render(request, tplname, ctx)


@login_required
@needs_mailbox()
def editfolder(request, tplname="modoboa_webmail/folder.html"):
    mbc = IMAPconnector(user=request.user.username,
                        password=request.session["password"])
    ctx = {"title": _("Edit folder"),
           "formid": "mboxform",
           "action": reverse("modoboa_webmail:folder_change"),
           "action_label": _("Update"),
           "action_classes": "submit",
           "withunseen": False,
           "selectonly": True,
           "hdelimiter": mbc.hdelimiter}

    if request.method == "POST":
        form = FolderForm(request.POST)
        if form.is_valid():
            pf = request.POST.get("parent_folder", None)
            oldname, oldparent = separate_mailbox(
                request.POST["oldname"], sep=mbc.hdelimiter
            )
            res = {'respmsg': _("Folder updated")}
            if form.cleaned_data["name"] != oldname \
                    or (pf != oldparent):
                newname = form.cleaned_data["name"] if pf is None \
                    else mbc.hdelimiter.join([pf, form.cleaned_data["name"]])
                mbc.rename_folder(request.POST["oldname"], newname)
                res["oldmb"] = oldname
                res["newmb"] = form.cleaned_data["name"]
                res["oldparent"] = oldparent
                res["newparent"] = pf
                WebmailNavigationParameters(request).remove('mbox')
            return render_to_json_response(res)

        return render_to_json_response(
            {'form_errors': form.errors}, status=400)

    name = request.GET.get("name")
    if name is None:
        raise BadRequest(_("Invalid request"))
    shortname, parent = separate_mailbox(name, sep=mbc.hdelimiter)
    ctx = {"title": _("Edit folder"),
           "formid": "mboxform",
           "action": reverse("modoboa_webmail:folder_change"),
           "action_label": _("Update"),
           "action_classes": "submit",
           "withunseen": False,
           "selectonly": True,
           "hdelimiter": mbc.hdelimiter,
           "mboxes": mbc.getmboxes(request.user, until_mailbox=parent),
           "form": FolderForm(),
           "selected": parent}
    ctx["form"].fields["oldname"].initial = name
    ctx["form"].fields["name"].initial = shortname
    return render(request, tplname, ctx)


@login_required
@needs_mailbox()
def delfolder(request):
    name = request.GET.get("name", None)
    if name is None:
        raise BadRequest(_("Invalid request"))
    mbc = IMAPconnector(user=request.user.username,
                        password=request.session["password"])
    mbc.delete_folder(name)
    WebmailNavigationParameters(request).remove('mbox')
    return ajax_response(request)


@login_required
@csrf_exempt
@needs_mailbox()
def attachments(request, tplname="modoboa_webmail/attachments.html"):
    if request.method == "POST":
        csuploader = AttachmentUploadHandler()
        request.upload_handlers.insert(0, csuploader)
        error = None
        form = AttachmentForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                fobj = request.FILES["attachment"]
                tmpname = save_attachment(fobj)
                request.session["compose_mail"]["attachments"] \
                    += [{"fname": str(fobj),
                         "content-type": fobj.content_type,
                         "size": fobj.size,
                         "tmpname": os.path.basename(tmpname)}]
                request.session.modified = True
                return render(request, "modoboa_webmail/upload_done.html", {
                    "status": "ok", "fname": request.FILES["attachment"],
                    "tmpname": os.path.basename(tmpname)
                })
            except ModoboaException as inst:
                error = _("Failed to save attachment: ") + str(inst)

        if csuploader.toobig:
            error = (
                _("Attachment is too big (limit: %s)") %
                param_tools.get_global_parameter("max_attachment_size"))
        return render(request, "modoboa_webmail/upload_done.html", {
            "status": "ko", "error": error
        })
    ctx = {
        "title": _("Attachments"),
        "formid": "uploadfile",
        "target": "upload_target",
        "enctype": "multipart/form-data",
        "form": AttachmentForm(),
        "action": reverse("modoboa_webmail:attachment_list"),
        "attachments": request.session["compose_mail"]["attachments"]
    }
    return render(request, tplname, ctx)


@login_required
@needs_mailbox()
def delattachment(request):
    """Delete an attachment."""
    name = request.GET.get("name")
    if not name or "compose_mail" not in request.session:
        return ajax_response(request, "ko", respmsg=_("Bad query"))

    error = None
    for att in request.session["compose_mail"]["attachments"]:
        if att["tmpname"] == name:
            request.session["compose_mail"]["attachments"].remove(att)
            fullpath = os.path.join(
                settings.MEDIA_ROOT, "webmail", att["tmpname"]
            )
            try:
                os.remove(fullpath)
            except OSError as e:
                error = _("Failed to remove attachment: ") + str(e)
                break
            request.session.modified = True
            return ajax_response(request)
    if error is None:
        error = _("Unknown attachment")
    return ajax_response(request, "ko", respmsg=error)


def render_mboxes_list(request, imapc):
    """Return the HTML representation of a mailboxes list

    :param request: a ``Request`` object
    :param imapc: an ``IMAPconnector` object
    :return: a string
    """
    curmbox = WebmailNavigationParameters(request).get("mbox", "INBOX")
    return render_to_string("modoboa_webmail/folders.html", {
        "selected": curmbox,
        "mboxes": imapc.getmboxes(request.user),
        "withunseen": True
    }, request)


def listmailbox(request, defmailbox="INBOX", update_session=True):
    """Mailbox content listing.

    Return a list of messages contained in the specified mailbox. The
    number of elements returned depends on the ``MESSAGES_PER_PAGE``
    parameter. (user preferences)

    :param request: a ``Request`` object
    :param defmailbox: the default mailbox (when not present inside
                       request arguments)
    :return: a dictionnary
    """
    navparams = WebmailNavigationParameters(request, defmailbox)
    previous_page_id = int(navparams["page"]) if "page" in navparams else None
    if update_session:
        navparams.store()
    mbox = navparams.get('mbox')
    page_id = int(navparams["page"])
    mbc = get_imapconnector(request)
    mbc.parse_search_parameters(
        navparams.get("criteria"), navparams.get("pattern"))
    sort_order = navparams.get("order")
    paginator = Paginator(
        mbc.messages_count(folder=mbox, order=sort_order),
        request.user.parameters.get_value("messages_per_page")
    )
    page = paginator.getpage(page_id)
    content = ""
    if page is not None:
        email_list = mbc.fetch(page.id_start, page.id_stop, mbox)
        content = render_to_string(
            "modoboa_webmail/email_list.html", {
                "email_list": email_list,
                "page": page_id,
                "with_top_div": request.GET.get("scroll", "false") == "false"
            }, request
        )
        length = len(content)
    else:
        if page_id == 1:
            content = u"<div class='alert alert-info'>{0}</div>".format(
                _("Empty mailbox")
            )
        length = 0
        if previous_page_id is not None:
            navparams["page"] = previous_page_id
    return {
        "listing": content, "length": length, "pages": [page_id],
        "menuargs": {"sort_order": sort_order}
    }


def render_compose(request, form, posturl, email=None, **kwargs):
    """Render the compose form."""
    resp = {}
    if email is None:
        body = ""
        textheader = ""
    else:
        body = email.body
        textheader = email.textheader
    if kwargs.get("insert_signature"):
        signature = EmailSignature(request.user)
        body = "{}{}".format(body, signature)
    randid = None
    condition = (
        "id" not in request.GET or
        "compose_mail" not in request.session or
        request.session["compose_mail"]["id"] != request.GET["id"]
    )
    if condition:
        randid = set_compose_session(request)
        if kwargs.get("load_email_attachments"):
            for pnum, fname in email.attachments.items():
                partdef, payload = email.fetch_attachment(pnum)
                request.session["compose_mail"]["attachments"].append({
                    "fname": fname,
                    "content-type": partdef["Content-Type"],
                    "size": partdef["size"],
                    "tmpname": save_attachment(base64.b64decode(payload))
                })
            request.session.modified = True

    attachment_list = request.session["compose_mail"]["attachments"]
    if attachment_list:
        resp["menuargs"] = {"attachment_counter": len(attachment_list)}

    if textheader:
        body = "{}\n{}".format(textheader, body)
    form.fields["body"].initial = body
    content = render_to_string("modoboa_webmail/compose.html", {
        "form": form, "posturl": posturl
    }, request)

    resp.update({
        "listing": content,
        "editor": request.user.parameters.get_value("editor")
    })
    if randid is not None:
        resp["id"] = randid
    return resp


def compose(request):
    """Compose email."""
    url = "?action=compose"
    if request.method == "POST":
        form = ComposeMailForm(request.user, request.POST)
        status, resp = send_mail(request, form, posturl=url)
        return resp

    form = ComposeMailForm(request.user)
    return render_compose(request, form, url, insert_signature=True)


def get_mail_info(request):
    """Retrieve a mailbox and an email ID from a request.
    """
    mbox = request.GET.get("mbox", None)
    mailid = request.GET.get("mailid", None)
    if mbox is None or mailid is None:
        raise BadRequest(_("Invalid request"))
    return mbox, mailid


def new_compose_form(request, action, mbox, mailid, **kwargs):
    """Return a new composition form.

    Valid for reply and forward actions only.
    """
    form = ComposeMailForm(request.user)
    modclass = globals()["%sModifier" % action.capitalize()]
    email = modclass(form, request, "%s:%s" % (mbox, mailid), links=True)
    url = "?action=%s&mbox=%s&mailid=%s" % (action, mbox, mailid)
    return render_compose(request, form, url, email, **kwargs)


def reply(request):
    """Reply to email."""
    mbox, mailid = get_mail_info(request)
    if request.method == "POST":
        url = "?action=reply&mbox=%s&mailid=%s" % (mbox, mailid)
        form = ComposeMailForm(request.user, request.POST)
        status, resp = send_mail(request, form, url)
        if status:
            get_imapconnector(request).msg_answered(mbox, mailid)
        return resp
    return new_compose_form(request, "reply", mbox, mailid)


def forward(request):
    """Forward email."""
    mbox, mailid = get_mail_info(request)
    if request.method == "POST":
        url = "?action=forward&mbox=%s&mailid=%s" % (mbox, mailid)
        form = ForwardMailForm(request.user, request.POST)
        status, resp = send_mail(request, form, url)
        if status:
            get_imapconnector(request).msg_forwarded(mbox, mailid)
        return resp
    return new_compose_form(
        request, "forward", mbox, mailid, load_email_attachments=True)


@login_required
@needs_mailbox()
def getmailcontent(request):
    mbox = request.GET.get("mbox", None)
    mailid = request.GET.get("mailid", None)
    if mbox is None or mailid is None:
        raise BadRequest(_("Invalid request"))
    email = ImapEmail(
        request,
        "%s:%s" % (mbox, mailid), dformat="DISPLAYMODE",
        links=request.GET.get("links", "0") == "1"
    )
    return render(request, "common/viewmail.html", {
        "mailbody": email.body if email.body else ""
    })


@login_required
@needs_mailbox()
def getmailsource(request):
    """Retrieve message source."""
    mbox = request.GET.get("mbox", None)
    mailid = request.GET.get("mailid", None)
    if mbox is None or mailid is None:
        raise BadRequest(_("Invalid request"))
    email = ImapEmail(
        request,
        "%s:%s" % (mbox, mailid), dformat="DISPLAYMODE",
        links=request.GET.get("links", "0") == "1"
    )
    return render(request, "modoboa_webmail/mail_source.html", {
        "title": _("Message source"),
        "source": email.source
    })


def viewmail(request):
    mbox = request.GET.get("mbox", None)
    mailid = request.GET.get("mailid", None)
    if mbox is None or mailid is None:
        raise BadRequest(_("Invalid request"))
    links = request.GET.get("links", None)
    if links is None:
        links = int(request.user.parameters.get_value("enable_links"))
    else:
        links = int(links)
    email = ImapEmail(
        request,
        "%s:%s" % (mbox, mailid), dformat="DISPLAYMODE", links=links
    )
    email.fetch_headers()
    context = {
        "mbox": mbox,
        "mailid": mailid,
        "links": links,
        "headers": email.headers,
        "attachments": email.attachments
    }
    content = render_to_string(
        "modoboa_webmail/headers.html", context, request)
    return {"listing": content, "menuargs": {"mail_id": mailid}}


@login_required
@needs_mailbox()
def submailboxes(request):
    """Retrieve the sub mailboxes of a mailbox."""
    topmailbox = request.GET.get('topmailbox', '')
    with_unseen = request.GET.get('unseen', None)
    mboxes = get_imapconnector(request).getmboxes(
        request.user, topmailbox, unseen_messages=with_unseen == 'true')
    return render_to_json_response(mboxes)


@login_required
@needs_mailbox()
def check_unseen_messages(request):
    mboxes = request.GET.get("mboxes", None)
    if not mboxes:
        raise BadRequest(_("Invalid request"))
    mboxes = mboxes.split(",")
    counters = {}
    imapc = get_imapconnector(request)
    for mb in mboxes:
        counters[mb] = imapc.unseen_messages(mb)
    return render_to_json_response(counters)


@login_required
@needs_mailbox()
def index(request):
    """Webmail actions handler

    Problèmes liés à la navigation 'anchor based'
    ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

    Lors d'un rafraichissemt complet, une première requête est envoyée
    vers /modoboa_webmail/. On ne connait pas encore l'action qui va être
    demandée mais on peut déjà envoyer des informations indépendantes
    (comme les dossiers, le quota).

    Si on se contente de cela, l'affichage donnera un aspect décomposé
    qui n'est pas très séduisant (à cause de la latence notamment). Il
    faudrait pouvoir envoyer le menu par la même occasion, le souci
    étant de savoir lequel...

    Une solution possible : il suffirait de déplacer le menu vers la
    droite pour l'aligner avec le contenu, remonter la liste des
    dossiers (même hauteur que le menu) et renvoyer le menu en même
    temps que le contenu. Le rendu sera plus uniforme je pense.

    """
    action = request.GET.get("action", None)
    if action is not None:
        if action not in globals():
            raise UnknownAction
        response = globals()[action](request)
    else:
        if request.is_ajax():
            raise BadRequest(_("Invalid request"))
        response = {"selection": "webmail"}

    curmbox = WebmailNavigationParameters(request).get("mbox", "INBOX")
    if not request.is_ajax():
        request.session["lastaction"] = None
        imapc = get_imapconnector(request)
        imapc.getquota(curmbox)
        trash = request.user.parameters.get_value("trash_folder")
        response.update({
            "hdelimiter": imapc.hdelimiter,
            "mboxes": render_mboxes_list(request, imapc),
            "refreshrate": request.user.parameters.get_value(
                "refresh_interval"),
            "quota": imapc.quota_usage,
            "trash": trash,
            "ro_mboxes": [
                "INBOX", "Junk",
                request.user.parameters.get_value("sent_folder"),
                trash,
                request.user.parameters.get_value("drafts_folder")
            ],
            "mboxes_col_width": request.user.parameters.get_value(
                "mboxes_col_width"),
            "contacts_plugin_enabled": exts_pool.get_extension(
                "modoboa_contacts")
        })
        return render(request, "modoboa_webmail/index.html", response)

    if action in ["reply", "forward"]:
        action = "compose"
    if request.session["lastaction"] != action:
        extra_args = {}
        if "menuargs" in response:
            extra_args = response["menuargs"]
            del response["menuargs"]
        try:
            menu = getattr(webmail_tags, "%s_menu" % action)
            response["menu"] = menu("", curmbox, request.user, **extra_args)
        except KeyError:
            pass

    response.update(callback=action)
    http_status = 200
    if "status" in response:
        del response['status']
        http_status = 400
    return render_to_json_response(response, status=http_status)
