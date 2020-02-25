# coding: utf-8
from django.urls import path

from . import views

app_name = 'modoboa_webmail'

urlpatterns = [
    path('', views.index, name="index"),
    path('submailboxes', views.submailboxes, name="submailboxes_get"),
    path('getmailcontent', views.getmailcontent, name="mailcontent_get"),
    path('getmailsource', views.getmailsource, name="mailsource_get"),
    path('unseenmsgs', views.check_unseen_messages,
         name="unseen_messages_check"),

    path('delete/', views.delete, name="mail_delete"),
    path('move/', views.move, name="mail_move"),
    path('mark/<path:name>/', views.mark, name="mail_mark"),
    path('mark_as_junk/', views.mark_as_junk, name="mail_mark_as_junk"),
    path('mark_as_not_junk/', views.mark_as_not_junk,
         name="mail_mark_as_not_junk"),

    path('newfolder/', views.newfolder, name="folder_add"),
    path('editfolder/', views.editfolder, name="folder_change"),
    path('delfolder/', views.delfolder, name="folder_delete"),
    path('compressfolder/', views.folder_compress, name="folder_compress"),
    path('emptytrash/', views.empty, name="trash_empty"),

    path('attachments/', views.attachments, name="attachment_list"),
    path('delattachment/', views.delattachment, name="attachment_delete"),
    path('getattachment/', views.getattachment, name="attachment_get"),
]
