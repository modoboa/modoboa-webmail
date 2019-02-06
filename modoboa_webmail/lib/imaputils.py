# coding: utf-8
"""
:mod:`imaputils` --- Extra IMAPv4 utilities
-------------------------------------------
"""

import email
from functools import wraps
import imaplib
import re
import socket
import ssl
import time

import six

from django.utils.encoding import smart_bytes
from django.utils.translation import ugettext as _

from modoboa.lib import imap_utf7  # noqa
from modoboa.lib.connections import ConnectionsManager
from modoboa.lib.exceptions import InternalError
from modoboa.parameters import tools as param_tools

from ..exceptions import ImapError, WebmailInternalError
from .fetch_parser import FetchResponseParser

# imaplib.Debug = 4

# workaround for the "got more than 10000 bytes" exception. MAXLINE
# value set to 1M, as on latest python versions.
MAXLINE = 1000000
if hasattr(imaplib, "_MAXLINE") and getattr(imaplib, "_MAXLINE") < MAXLINE:
    setattr(imaplib, "_MAXLINE", MAXLINE)


class capability(object):

    """
    Simple decorator to check if the server presents the required
    capability. If not, a fallback method is called instead.

    :param name: the capability name (upper case)
    :param fallback_method: a method's name
    """

    def __init__(self, name, fallback_method):
        self.name = name
        self.fallback_method = fallback_method

    def __call__(self, method):
        @wraps(method)
        def wrapped_func(cls, *args, **kwargs):
            if self.name in cls.capabilities:
                return method(cls, *args, **kwargs)
            return getattr(cls, self.fallback_method)(cls, **kwargs)

        return wrapped_func


class BodyStructure(object):

    """
    BODYSTRUCTURE response parser.

    Just a simple class that tries to distinguish content parts from
    attachments.
    """

    def __init__(self, definition=None):
        self.is_multipart = False
        self.contents = {}
        self.attachments = []
        self.inlines = {}

        if definition is not None:
            self.load_from_definition(definition)

    def __store_part(self, definition, pnum, multisubtype):
        """Store the given message part in the appropriate category.

        This method sort parts in two categories:

        * contents (what is going to be displayed)
        * attachments

        As there is no official definition about what is a content and
        what is an attachment, the following rules are applied:

        * If the MIME type is text/plain or text/html:

         * If no previous part of this type has already been seen,
           it's a content
         * Otherwise it's an attachment

        * Else, if the multipart subtype is related, we consider this
          part as content because it is certainly an embedded image

        * Any other MIME type is considered as an attachment (for now)

        :param definition: a part definition (list)
        :param pnum: the part's number
        :param multisubtype: the multipart subtype

        """
        pnum = "1" if pnum is None else pnum
        params = {
            "pnum": pnum,
            "params": definition[2],
            "cid": definition[3],
            "description": definition[4],
            "encoding": definition[5],
            "size": definition[6]
        }
        mtype = definition[0].lower()
        subtype = definition[1].lower()
        ftype = "%s/%s" % (definition[0].lower(), subtype)
        if ftype in ("text/plain", "text/html"):
            if subtype not in self.contents:
                self.contents[subtype] = [params]
            else:
                self.contents[subtype].append(params)
            return
        elif multisubtype in ["related"]:
            self.inlines[params["cid"].strip("<>")] = params
            return

        params["Content-Type"] = ftype
        if len(definition) > 7:
            extensions = ["md5", "disposition", "language", "location"]
            if mtype == "text":
                extensions = ["textlines"] + extensions
            elif ftype == "message/rfc822":
                extensions = [
                    "envelopestruct",
                    "bodystruct",
                    "textlines"] + extensions
            for idx, value in enumerate(definition[7:]):
                params[extensions[idx]] = value

        self.attachments += [params]

    def load_from_definition(self, definition, multisubtype=None):
        for mp in definition:
            if isinstance(mp, list):
                if isinstance(mp[0], list):
                    self.load_from_definition(mp, mp[1])
                else:
                    self.load_from_definition(mp)
            elif isinstance(mp, dict):
                if isinstance(mp["struct"][0], list):
                    self.load_from_definition(mp["struct"][0], mp["struct"][1])
                    continue
                self.__store_part(mp["struct"], mp["partnum"], multisubtype)

    def has_attachments(self):
        return len(self.attachments)

    def find_attachment(self, pnum):
        for att in self.attachments:
            if pnum == att["pnum"]:
                return att
        return None


@six.add_metaclass(ConnectionsManager)
class IMAPconnector(object):

    """The IMAPv4 connector."""

    namespaces_pattern = re.compile(r'(\(\(.+?\)\)|NIL)')
    namespace_pattern = re.compile(
        r'\("(?P<prefix>.*?)" "(?P<delimiter>.+?)"\)')
    list_base_pattern = (
        r'\((?P<flags>.*?)\) "(?P<delimiter>.*)" "?(?P<name>[^"]*)"?'
    )
    list_response_pattern_literal = re.compile(
        r'\((?P<flags>.*?)\) "(?P<delimiter>.*)" \{(?P<namelen>\d+)\}')
    list_response_pattern = re.compile(list_base_pattern)
    listextended_response_pattern = \
        re.compile(list_base_pattern + r'\s*(?P<childinfo>.*)')
    unseen_pattern = re.compile(r'[^\(]+\(UNSEEN (\d+)\)')

    def __init__(self, user=None, password=None):
        self.__hdelimiter = None
        self.__ns_prefixes = {}
        self.quota_usage = -1
        self.criterions = []
        self.conf = dict(param_tools.get_global_parameters("modoboa_webmail"))
        self.address = self.conf["imap_server"]
        self.port = self.conf["imap_port"]
        self.login(user, password)
        self.load_namespaces()

    def _cmd(self, name, *args, **kwargs):
        """IMAP command wrapper

        To simplify errors handling, this wrapper calls the
        appropriate method (``uid`` or FIXME) and then check the
        return code. If an error has occured, an ``ImapError``
        exception is raised.

        For specific commands commands (FETCH, ...), the result is
        parsed using the IMAPclient module before being returned.

        :param name: the command's name
        :return: the command's result
        """
        if name in ['FETCH', 'SORT', 'STORE', 'COPY', 'SEARCH']:
            try:
                typ, data = self.m.uid(name, *args)
            except imaplib.IMAP4.error as e:
                raise ImapError(e)
            if typ == "NO":
                raise ImapError(data)
            if name == 'FETCH':
                return FetchResponseParser().parse(data)
            return data

        try:
            typ, data = self.m._simple_command(name, *args)
        except imaplib.IMAP4.error as e:
            raise ImapError(e)
        if typ == "NO":
            raise ImapError(data)
        if 'responses' not in kwargs:
            if name not in self.m.untagged_responses:
                return None
            return self.m.untagged_responses.pop(name)
        res = []
        for r in kwargs['responses']:
            if r not in self.m.untagged_responses:
                return None
            res.append(self.m.untagged_responses.pop(r))
        return res

    @property
    def hdelimiter(self):
        """Return the default hierachy delimiter.

        :return: a string
        """
        if self.__hdelimiter is None:
            raise InternalError(
                _("Failed to retrieve hierarchy delimiter"))
        return self.__hdelimiter

    def refresh(self, user, password):
        """Check if current connection needs a refresh

        Is it really secure?
        """
        if self.m is not None:
            try:
                self._cmd("NOOP")
            except ImapError:
                if hasattr(self, "current_mailbox"):
                    del self.current_mailbox
            else:
                return

        self.login(user, password)

    def login(self, user, passwd):
        """Custom login method

        We connect to the server, issue a LOGIN command. If
        successfull, we try to record a eventuel CAPABILITY untagged
        response. Otherwise, we issue the command.

        :param user: username
        :param passwd: password
        """
        try:
            if self.conf["imap_secured"]:
                self.m = imaplib.IMAP4_SSL(self.address, self.port)
            else:
                self.m = imaplib.IMAP4(self.address, self.port)
        except (socket.error, imaplib.IMAP4.error, ssl.SSLError) as error:
            raise ImapError(_("Connection to IMAP server failed: %s" % error))

        passwd = self.m._quote(passwd)
        data = self._cmd("LOGIN", smart_bytes(user), smart_bytes(passwd))
        self.m.state = "AUTH"
        if "CAPABILITY" in self.m.untagged_responses:
            self.capabilities = (
                self.m.untagged_responses.pop('CAPABILITY')[0]
                .decode().split())
        else:
            data = self._cmd("CAPABILITY")
            self.capabilities = data[0].decode().split()

    def logout(self):
        """Logout from server."""
        try:
            self._cmd("CHECK")
        except ImapError:
            pass
        self._cmd("LOGOUT")
        del self.m
        self.m = None
        if hasattr(self, "current_mailbox"):
            del self.current_mailbox

    def load_namespaces(self):
        """Load available namespaces."""
        data = self._cmd("NAMESPACE")
        nslist = self.namespaces_pattern.findall(data[0].decode())
        for pos, item in enumerate(["personal", "others", "public"]):
            if nslist[pos] == "NIL":
                continue
            ns = nslist[pos][1:-1]
            for m in self.namespace_pattern.finditer(ns):
                if self.__hdelimiter is None:
                    self.__hdelimiter = m.group("delimiter")
                if item not in self.__ns_prefixes:
                    self.__ns_prefixes[item] = []
                self.__ns_prefixes[item].append(m.group("prefix"))

    def parse_search_parameters(self, criterion, pattern):
        """Parse search information and apply them."""

        def or_criterion(old, c):
            if old == "":
                return c
            return "OR (%s) (%s)" % (old, c)

        if criterion == u"both":
            criterion = u"from_addr, subject"
        criterions = ""
        for c in criterion.split(','):
            if c == "from_addr":
                key = "FROM"
            elif c == "subject":
                key = "SUBJECT"
            else:
                continue
            criterions = or_criterion(
                criterions, '(%s "%s")' % (key, pattern))
        if six.PY3:
            criterions = bytearray(criterions, "utf-8")
        elif isinstance(criterions, six.text_type):
            criterions = criterions.encode("utf-8")
        self.criterions = [criterions]

    def messages_count(self, **kwargs):
        """An enhanced version of messages_count

        With IMAP, to know how many messages a mailbox contains, we
        have to make a request to the server. To avoid requests
        multiplications, we sort messages in the same time. This will
        be usefull for other methods.

        :param order: sorting order
        :param folder: mailbox to scan
        """
        if "order" in kwargs and kwargs["order"]:
            sign = kwargs["order"][:1]
            criterion = kwargs["order"][1:].upper()
            if sign == '-':
                criterion = "REVERSE %s" % criterion
        else:
            criterion = "REVERSE DATE"
        folder = kwargs["folder"] if "folder" in kwargs else None

        # FIXME: pourquoi suis je obligé de faire un SELECT ici?  un
        # EXAMINE plante mais je pense que c'est du à une mauvaise
        # lecture des réponses de ma part...
        self.select_mailbox(folder, readonly=False)
        cmdname = "SORT" if six.PY3 else b"SORT"
        data = self._cmd(
            cmdname,
            bytearray("(%s)" % criterion, "utf-8"),
            b"UTF-8", b"(NOT DELETED)", *self.criterions)
        self.messages = data[0].decode().split()
        self.getquota(folder)
        return len(self.messages)

    def select_mailbox(self, name, readonly=True, force=False):
        """Issue a SELECT/EXAMINE command to the server

        The given name is first 'imap-utf7' encoded.

        :param name: mailbox's name
        :param readonly:
        """
        if hasattr(self, "current_mailbox"):
            if self.current_mailbox == name and not force:
                return
        self.current_mailbox = name
        name = self._encode_mbox_name(name)
        if readonly:
            self._cmd("EXAMINE", name)
        else:
            self._cmd("SELECT", name)
        self.m.state = "SELECTED"

    def unseen_messages(self, mailbox):
        """Return the number of unseen messages

        :param mailbox: the mailbox's name
        :return: an integer
        """
        data = self._cmd(
            "STATUS", self._encode_mbox_name(mailbox), "(UNSEEN)")
        m = self.unseen_pattern.match(data[-1].decode())
        if m is None:
            return 0
        return int(m.group(1))

    def _encode_mbox_name(self, folder):
        """Encode folder name (str) to imap4-utf-7 and quote it."""
        if not folder:
            return "INBOX"
        return b'"' + folder.encode("imap4-utf-7") + b'"'

    def _parse_mailbox_name(self, descr, prefix, delimiter, parts):
        if not len(parts):
            return False
        path = "%s%s%s" % (prefix, delimiter, parts[0])
        sdescr = None
        for d in descr:
            if d["path"] == path:
                sdescr = d
                break
        if sdescr is None:
            sdescr = {"name": parts[0], "path": path, "sub": []}
            descr += [sdescr]
        if self._parse_mailbox_name(sdescr["sub"], path, delimiter, parts[1:]):
            sdescr["class"] = "subfolders"
        return True

    def _listmboxes_simple(self, topmailbox='INBOX', mailboxes=None, **kwargs):
        # data = self._cmd("LIST", "", "*")
        if not mailboxes:
            mailboxes = []
        (status, data) = self.m.list()
        newmboxes = []
        for mb in data:
            flags, delimiter, name = self.list_response_pattern.match(
                mb.decode()).groups()
            name = bytearray(name.strip('"'), "utf-8").decode("imap4-utf-7")
            mdm_found = False
            for idx, mdm in enumerate(mailboxes):
                if mdm["name"] == name:
                    mdm_found = True
                    descr = mailboxes[idx]
                    break
            if not mdm_found:
                descr = {"name": name}
                newmboxes += [descr]

            if re.search(r"\%s" % delimiter, name):
                parts = name.split(delimiter)
                if "path" not in descr:
                    descr["path"] = parts[0]
                    descr["sub"] = []
                if self._parse_mailbox_name(descr["sub"], parts[0], delimiter,
                                            parts[1:]):
                    descr["class"] = "subfolders"
                continue

        from operator import itemgetter
        mailboxes += sorted(newmboxes, key=itemgetter("name"))

    @capability('LIST-EXTENDED', '_listmboxes_simple')
    def _listmboxes(self, topmailbox, mailboxes, until_mailbox=None):
        """Retrieve mailboxes list."""
        pattern = (
            '"{0}{1}%"'.format(
                topmailbox.encode("imap4-utf-7").decode(), self.hdelimiter)
            if topmailbox else "%"
        )
        resp = self._cmd(
            "LIST", '""', pattern, "RETURN", "(CHILDREN STATUS (MESSAGES))")
        newmboxes = []
        for mb in resp:
            if not mb:
                continue
            if type(mb) in [list, tuple]:
                flags, delimiter, namelen = (
                    self.list_response_pattern_literal.match(
                        mb[0].decode()).groups()
                )
                name = mb[1][0:int(namelen)]
            else:
                flags, delimiter, name, childinfo = (
                    self.listextended_response_pattern.match(
                        mb.decode()).groups())
            flags = flags.split(" ")
            name = bytearray(name, "utf-8")
            name = name.decode("imap4-utf-7")
            mdm_found = False
            for idx, mdm in enumerate(mailboxes):
                if mdm["name"] == name:
                    mdm_found = True
                    descr = mailboxes[idx]
                    break
            if not mdm_found:
                descr = {"name": name}
                newmboxes += [descr]

            if '\\Marked' in flags or '\\UnMarked' not in flags:
                descr["send_status"] = True
            if r'\NonExistent' in flags:
                descr["removed"] = True
            if '\\HasChildren' in flags:
                descr["path"] = name
                descr["sub"] = []
                if until_mailbox and until_mailbox.startswith(name):
                    self._listmboxes(name, descr["sub"], until_mailbox)

        from operator import itemgetter
        mailboxes += sorted(newmboxes, key=itemgetter("name"))

    def getmboxes(
            self, user, topmailbox='', until_mailbox=None,
            unseen_messages=True):
        """Returns a list of mailboxes for a particular user

        By default, only the first level of mailboxes under
        ``topmailbox`` is returned. If ``until_mailbox`` is specified,
        all levels needed to access this mailbox will be returned.

        :param user: a ``User`` instance
        :param topmailbox: the mailbox where to start in the tree
        :param until_mailbox: the deepest needed mailbox
        :param unseen_messages: include unseen messages counters or not
        :return: a list
        """
        if topmailbox:
            md_mailboxes = []
        else:
            md_mailboxes = [
                {"name": "INBOX", "class": "fa fa-inbox",
                 "label": _("Inbox")},
                {"name": user.parameters.get_value("drafts_folder"),
                 "class": "fa fa-file", "label": _("Drafts")},
                {"name": user.parameters.get_value("junk_folder"),
                 "class": "fa fa-fire", "label": _("Junk")},
                {"name": user.parameters.get_value("sent_folder"),
                 "class": "fa fa-envelope", "label": _("Sent")},
                {"name": user.parameters.get_value("trash_folder"),
                 "class": "fa fa-trash", "label": _("Trash")}
            ]
        if until_mailbox:
            name, parent = separate_mailbox(until_mailbox, self.hdelimiter)
            if parent:
                until_mailbox = parent
        self._listmboxes(topmailbox, md_mailboxes, until_mailbox)

        if unseen_messages:
            for mb in md_mailboxes:
                if "send_status" not in mb:
                    continue
                del mb["send_status"]
                key = "path" if "path" in mb else "name"
                if mb.get("removed", False):
                    continue
                count = self.unseen_messages(mb[key])
                if count == 0:
                    continue
                mb["unseen"] = count
        return md_mailboxes

    def _add_flag(self, mbox, msgset, flag):
        """Add flag to a messages set.

        :param mbox: the mailbox containing the messages
        :param msgset: messages set (uid)
        :param flag: the flag to add
        """
        self.select_mailbox(mbox, False)
        self._cmd("STORE", msgset, "+FLAGS", flag)

    def _remove_flag(self, mbox, msgset, flag):
        """Remove flag from a message set.

        :param mbox: the mailbox containing the messages
        :param msgset: messages set (uid)
        :param flag: the flag to remove
        """
        self.select_mailbox(mbox, False)
        self._cmd("STORE", msgset, "-FLAGS", flag)

    def mark_messages_unread(self, mbox, msgset):
        """Mark a set of messages as unread

        :param mbox: the mailbox containing the messages
        :param msgset: messages set (uid)
        """
        self._remove_flag(mbox, msgset, r'(\Seen)')

    def mark_messages_read(self, mbox, msgset):
        """Mark a set of messages as unread

        :param mbox: the mailbox containing the messages
        :param msgset: messages set (uid)
        """
        self._add_flag(mbox, msgset, r'(\Seen)')

    def mark_messages_flagged(self, mbox, msgset):
        """Mark a set of messages as flagged.

        :param mbox: the mailbox containing the messages
        :param msgset: messages set (uid)
        """
        self._add_flag(mbox, msgset, r'(\Flagged)')

    def mark_messages_unflagged(self, mbox, msgset):
        """Mark a set of messages as unflagged.

        :param mbox: the mailbox containing the messages
        :param msgset: messages set (uid)
        """
        self._remove_flag(mbox, msgset, r'(\Flagged)')

    def msg_forwarded(self, mailbox, mailid):
        self._add_flag(mailbox, mailid, '($Forwarded)')

    def msg_answered(self, mailbox, mailid):
        """Add the \Answered flag to this email"""
        self._add_flag(mailbox, mailid, r'(\Answered)')

    def move(self, msgset, oldmailbox, newmailbox):
        """Move messages between mailboxes."""
        self.select_mailbox(oldmailbox, False)
        self._cmd("COPY", msgset, self._encode_mbox_name(newmailbox))
        self._cmd("STORE", msgset, "+FLAGS", r'(\Deleted \Seen)')

    def push_mail(self, folder, msg):
        now = imaplib.Time2Internaldate(time.time())
        msg = bytes(msg) if six.PY3 else str(msg)
        return self.m.append(
            self._encode_mbox_name(folder), r'(\Seen)', now, msg)

    def empty(self, mbox):
        self.select_mailbox(mbox, False)
        resp = self._cmd("SEARCH", "ALL")
        seq = b",".join(resp[0].split())
        if seq == b"":
            return
        self._cmd("STORE", seq, "+FLAGS", r'(\Deleted)')
        self._cmd("EXPUNGE")

    def compact(self, mbox):
        """Compact a specific mailbox

        Issue an EXPUNGE command for the specified mailbox.

        :param mbox: the mailbox's name
        """
        self.select_mailbox(mbox, False)
        self._cmd("EXPUNGE")

    def create_folder(self, name, parent=None):
        if parent is not None:
            name = "%s%s%s" % (parent, self.hdelimiter, name)
        typ, data = self.m.create(self._encode_mbox_name(name))
        if typ == "NO":
            raise WebmailInternalError(data[0])
        return True

    def rename_folder(self, oldname, newname):
        typ, data = self.m.rename(self._encode_mbox_name(oldname),
                                  self._encode_mbox_name(newname))
        if typ == "NO":
            raise WebmailInternalError(data[0], ajax=True)
        return True

    def delete_folder(self, name):
        typ, data = self.m.delete(self._encode_mbox_name(name))
        if typ == "NO":
            raise WebmailInternalError(data[0])
        return True

    def getquota(self, mailbox):
        """Retrieve quota information from the server.

        We also compute the current usage.
        """
        if "QUOTA" not in self.capabilities:
            self.quota_limit = self.quota_current = None
            return
        try:
            data = self._cmd("GETQUOTAROOT", self._encode_mbox_name(mailbox),
                             responses=["QUOTAROOT", "QUOTA"])
        except ImapError:
            data = None
        finally:
            if data is None:
                self.quota_limit = self.quota_current = None
                return

        quotadef = data[1][0].decode()
        m = re.search(r"\(STORAGE (\d+) (\d+)\)", quotadef)
        if not m:
            print("Problem while parsing quota def")
            return
        self.quota_limit = int(m.group(2))
        self.quota_current = int(m.group(1))
        try:
            self.quota_usage = (
                int(float(self.quota_current) / float(self.quota_limit) * 100)
            )
        except TypeError:
            self.quota_usage = -1

    def fetchpart(self, uid, mbox, partnum):
        """Retrieve a specific message part

        Useful to fetch attachments from the server. Part headers and
        the payload are returned separatly.

        :param uid: a message UID
        :param mbox: the mailbox containing the message
        :param partnum: the part number
        :return: a 2uple (dict, string)
        """
        self.select_mailbox(mbox, False)
        data = self._cmd("FETCH", uid, "(BODYSTRUCTURE BODY[%s])" % partnum)
        bs = BodyStructure(data[int(uid)]["BODYSTRUCTURE"])
        attdef = bs.find_attachment(partnum)
        return attdef, data[int(uid)]["BODY[%s]" % partnum]

    def fetch(self, start, stop=None, mbox=None):
        """Retrieve information about messages from the server

        Issue a FETCH command to retrieve information about one or
        more messages (such as headers) from the server.

        :param start: index of the first message
        :param stop: index of the last message (optionnal)
        :param mbox: the mailbox that contains the messages
        """
        self.select_mailbox(mbox, False)
        if start and stop:
            submessages = self.messages[start - 1:stop]
            mrange = ",".join(submessages)
        else:
            submessages = [start]
            mrange = start
        headers = "DATE FROM TO CC SUBJECT"
        query = (
            "(FLAGS BODYSTRUCTURE RFC822.SIZE BODY.PEEK[HEADER.FIELDS ({})])"
            .format(headers)
        )
        data = self._cmd("FETCH", mrange, query)
        result = []
        for uid in submessages:
            msg_data = data[int(uid)]
            msg = email.message_from_string(
                msg_data["BODY[HEADER.FIELDS ({})]".format(headers)]
            )
            msg["imapid"] = uid
            msg["size"] = msg_data["RFC822.SIZE"]
            if r"\Seen" not in msg_data["FLAGS"]:
                msg["style"] = "unseen"
            if r"\Answered" in msg_data["FLAGS"]:
                msg["answered"] = True
            if r"$Forwarded" in msg_data["FLAGS"]:
                msg["forwarded"] = True
            if r"\Flagged" in msg_data["FLAGS"]:
                msg["flagged"] = True
            bstruct = BodyStructure(msg_data["BODYSTRUCTURE"])
            if bstruct.has_attachments():
                msg["attachments"] = True
            result += [msg]
        return result

    def fetchmail(self, mbox, mailid, readonly=True, what="bodystructure"):
        """Retrieve information about a specific message

        Issue a FETCH command to retrieve a message's content from the
        server. In order to not overload the server, we first retrieve
        the BODYSTRUCTURE of the message. Then, according to the
        result and to the user's preferences, we retrieve the
        appropriate content (plain, html, etc.).

        :param mbox: the mailbox containing the message
        :param mailid: the message's unique id
        :param readonly:
        :param headers:
        """
        self.select_mailbox(mbox, readonly)
        if what == "bodystructure":
            to_fetch = "(BODYSTRUCTURE)"
        elif what == "source":
            to_fetch = "(BODY[])"
        else:
            bcmd = "BODY.PEEK" if readonly else "BODY"
            to_fetch = "(BODYSTRUCTURE {}[HEADER.FIELDS ({})])".format(
                bcmd, what)
        data = self._cmd("FETCH", mailid, to_fetch)
        return data[int(mailid)]


def separate_mailbox(fullname, sep="."):
    """Split a mailbox name

    If a separator is found in ``fullname``, this function returns the
    corresponding name and parent mailbox name.
    """
    if sep in fullname:
        parts = fullname.split(sep)
        name = parts[-1]
        parent = sep.join(parts[0:len(parts) - 1])
        return name, parent
    return fullname, None


def get_imapconnector(request):
    """Simple shortcut to create a connector

    :param request: a ``Request`` object
    """
    imapc = IMAPconnector(user=request.user.username,
                          password=request.session["password"])
    return imapc


if __name__ == "__main__":
    import doctest
    doctest.testmod()
