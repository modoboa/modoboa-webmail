# coding: utf-8
from django.conf.urls import url

from . import views

urlpatterns = [
    url(r'^$', views.index, name="index"),
    url(r'^submailboxes', views.submailboxes, name="submailboxes_get"),
    url(r'^getmailcontent', views.getmailcontent, name="mailcontent_get"),
    url(r'^unseenmsgs', views.check_unseen_messages,
        name="unseen_messages_check"),

    url(r'^delete/$', views.delete,
        name="mail_delete"),
    url(r'^move/$', views.move,
        name="mail_move"),
    url(r'^mark/(?P<name>.+)/$', views.mark,
        name="mail_mark"),

    url(r'^newfolder/$', views.newfolder,
        name="folder_add"),
    url(r'^editfolder/$', views.editfolder,
        name="folder_change"),
    url(r'^delfolder/$', views.delfolder,
        name="folder_delete"),
    url(r'^compressfolder/$', views.folder_compress,
        name="folder_compress"),
    url(r'^emptytrash/$', views.empty,
        name="trash_empty"),

    url(r'^attachments/$', views.attachments, name="attachment_list"),
    url(r'^delattachment/$', views.delattachment, name="attachment_delete"),
    url(r'^getattachment/$', views.getattachment, name="attachment_get"),
]
