# coding: utf-8

# flake8: noqa

"""Tests data."""

BODYSTRUCTURE_SAMPLE_1 = [
    b'36 (FLAGS (\\Seen))',
    b'36 (UID 36 BODYSTRUCTURE (("text" "plain" ("charset" "UTF-8") NIL NIL "QUOTED-PRINTABLE" 959 29 NIL ("inline" NIL) NIL NIL)("text" "html" ("charset" "UTF-8") NIL NIL "QUOTED-PRINTABLE" 14695 322 NIL ("inline" NIL) NIL NIL) "alternative" ("boundary" "----=_Part_2437867_661044267.1501268072105") NIL NIL NIL))'
]

BODYSTRUCTURE_SAMPLE_2 = [
    (b'19 (UID 19 FLAGS (\\Seen $label4) BODYSTRUCTURE (("text" "plain" ("charset" "ISO-8859-1" "format" "flowed") NIL NIL "7bit" 2 1 NIL NIL NIL NIL)("message" "rfc822" ("name*" "ISO-8859-1\'\'%5B%49%4E%53%43%52%49%50%54%49%4F%4E%5D%20%52%E9%63%E9%70%74%69%6F%6E%20%64%65%20%76%6F%74%72%65%20%64%6F%73%73%69%65%72%20%64%27%69%6E%73%63%72%69%70%74%69%6F%6E%20%46%72%65%65%20%48%61%75%74%20%44%E9%62%69%74") NIL NIL "8bit" 3632 ("Wed, 13 Dec 2006 20:30:02 +0100" {70}',
    b"[INSCRIPTION] R\xe9c\xe9ption de votre dossier d'inscription Free Haut D\xe9bit"),
    (b' (("Free Haut Debit" NIL "inscription" "freetelecom.fr")) (("Free Haut Debit" NIL "inscription" "freetelecom.fr")) ((NIL NIL "hautdebit" "freetelecom.fr")) ((NIL NIL "nguyen.antoine" "wanadoo.fr")) NIL NIL NIL "<20061213193125.9DA0919AC@dgroup2-2.proxad.net>") ("text" "plain" ("charset" "iso-8859-1") NIL NIL "8bit" 1428 38 NIL ("inline" NIL) NIL NIL) 76 NIL ("inline" ("filename*" "ISO-8859-1\'\'%5B%49%4E%53%43%52%49%50%54%49%4F%4E%5D%20%52%E9%63%E9%70%74%69%6F%6E%20%64%65%20%76%6F%74%72%65%20%64%6F%73%73%69%65%72%20%64%27%69%6E%73%63%72%69%70%74%69%6F%6E%20%46%72%65%65%20%48%61%75%74%20%44%E9%62%69%74")) NIL NIL) "mixed" ("boundary" "------------040706080908000209030901") NIL NIL NIL) BODY[HEADER.FIELDS (DATE FROM TO CC SUBJECT)] {266}',
     b'Date: Tue, 19 Dec 2006 19:50:13 +0100\r\nFrom: Antoine Nguyen <nguyen.antoine@wanadoo.fr>\r\nTo: Antoine Nguyen <tonio@koalabs.org>\r\nSubject: [Fwd: [INSCRIPTION] =?ISO-8859-1?Q?R=E9c=E9ption_de_votre_?=\r\n =?ISO-8859-1?Q?dossier_d=27inscription_Free_Haut_D=E9bit=5D?=\r\n\r\n'),
    b')'
]

BODYSTRUCTURE_SAMPLE_3 = [
    (b'58 (UID 123753 BODYSTRUCTURE ((("text" "plain" ("charset" "iso-8859-1") NIL NIL "quoted-printable" 90 10 NIL NIL NIL NIL)("text" "html" ("charset" "iso-8859-1") NIL NIL "quoted-printable" 1034 33 NIL NIL NIL NIL) "alternative" ("boundary" "_000_HE1PR10MB1642F2B8BA7FF8EAC0FC7AECD86E0HE1PR10MB1642EURP_") NIL NIL NIL)("application" "pdf" ("name" "=?iso-8859-1?Q?CV=5FAude=5FGIRODON=5FNGUYEN=5Fao=FBt2017_g=E9n=E9rique.pd?= =?iso-8859-1?Q?f?=") NIL {95}', '=?iso-8859-1?Q?CV=5FAude=5FGIRODON=5FNGUYEN=5Fao=FBt2017_g=E9n=E9rique.pd?=\n =?iso-8859-1?Q?f?='),
    b' "base64" 94130 NIL ("attachment" ("filename" "=?iso-8859-1?Q?CV=5FAude=5FGIRODON=5FNGUYEN=5Fao=FBt2017_g=E9n=E9rique.pd?= =?iso-8859-1?Q?f?=" "size" "68787" "creation-date" "Wed, 13 Sep 2017 08:50:03 GMT" "modification-date" "Wed, 13 Sep 2017 08:50:03 GMT")) NIL NIL) "mixed" ("boundary" "_004_HE1PR10MB1642F2B8BA7FF8EAC0FC7AECD86E0HE1PR10MB1642EURP_") NIL ("fr-FR") NIL))'
]

BODYSTRUCTURE_SAMPLE_4 = [
    (b'855 (UID 46931 BODYSTRUCTURE ((("text" "plain" ("charset" "iso-8859-1") NIL NIL "quoted-printable" 886 32 NIL NIL NIL NIL)("text" "html" ("charset" "us-ascii") NIL NIL "quoted-printable" 1208 16 NIL NIL NIL NIL) "alternative" ("boundary" "----=_NextPart_001_0003_01CCC564.B2F64FF0") NIL NIL NIL)("application" "octet-stream" ("name" "Carte Verte_2.pdf") NIL NIL "base64" 285610 NIL ("attachment" ("filename" "Carte Verte_2.pdf")) NIL NIL) "mixed" ("boundary" "----=_NextPart_000_0002_01CCC564.B2F64FF0") NIL NIL NIL) BODY[HEADER.FIELDS (DATE FROM TO CC SUBJECT)] {153}', b'From: <Service.client10@maaf.fr>\r\nTo: <TONIO@NGYN.ORG>\r\nCc: \r\nSubject: Notre contact du 28/12/2011 - 192175092\r\nDate: Wed, 28 Dec 2011 13:29:17 +0100\r\n\r\n'),
    b')'
]

BODYSTRUCTURE_SAMPLE_5 = [
    (b'856 (UID 46936 BODYSTRUCTURE (("text" "plain" ("charset" "ISO-8859-1") NIL NIL "quoted-printable" 724 22 NIL NIL NIL NIL)("text" "html" ("charset" "ISO-8859-1") NIL NIL "quoted-printable" 2662 48 NIL NIL NIL NIL) "alternative" ("boundary" "----=_Part_1326887_254624357.1325083973970") NIL NIL NIL) BODY[HEADER.FIELDS (DATE FROM TO CC SUBJECT)] {258}', 'Date: Wed, 28 Dec 2011 15:52:53 +0100 (CET)\r\nFrom: =?ISO-8859-1?Q?Malakoff_M=E9d=E9ric?= <communication@communication.malakoffmederic.com>\r\nTo: Antoine Nguyen <tonio@ngyn.org>\r\nSubject: =?ISO-8859-1?Q?Votre_inscription_au_grand_Jeu_Malakoff_M=E9d=E9ric?=\r\n\r\n'),
    b')'
]

BODYSTRUCTURE_SAMPLE_6 = [
    (b'123 (UID 3 BODYSTRUCTURE (((("text" "plain" ("charset" "iso-8859-1") NIL NIL "quoted-printable" 1266 30 NIL NIL NIL NIL)("text" "html" ("charset" "iso-8859-1") NIL NIL "quoted-printable" 8830 227 NIL NIL NIL NIL) "alternative" ("boundary" "_000_152AC7ECD1F8AB43A9AD95DBDDCA3118082C09GKIMA24cmcicfr_") NIL NIL NIL)("image" "png" ("name" "image005.png") "<image005.png@01CC6CAA.4FADC490>" "image005.png" "base64" 7464 NIL ("inline" ("filename" "image005.png" "size" "5453" "creation-date" "Tue, 06 Sep 2011 13:33:49 GMT" "modification-date" "Tue, 06 Sep 2011 13:33:49 GMT")) NIL NIL)("image" "jpeg" ("name" "image006.jpg") "<image006.jpg@01CC6CAA.4FADC490>" "image006.jpg" "base64" 2492 NIL ("inline" ("filename" "image006.jpg" "size" "1819" "creation-date" "Tue, 06 Sep 2011 13:33:49 GMT" "modification-date" "Tue, 06 Sep 2011 13:33:49 GMT")) NIL NIL) "related" ("boundary" "_006_152AC7ECD1F8AB43A9AD95DBDDCA3118082C09GKIMA24cmcicfr_" "type" "multipart/alternative") NIL NIL NIL)("application" "pdf" ("name" "bilan assurance CIC.PDF") NIL "bilan assurance CIC.PDF" "base64" 459532 NIL ("attachment" ("filename" "bilan assurance CIC.PDF" "size" "335811" "creation-date" "Fri, 16 Sep 2011 12:45:23 GMT" "modification-date" "Fri, 16 Sep 2011 12:45:23 GMT")) NIL NIL)(("text" "plain" ("charset" "utf-8") NIL NIL "quoted-printable" 1389 29 NIL NIL NIL NIL)("text" "html" ("charset" "utf-8") NIL NIL "quoted-printable" 1457 27 NIL NIL NIL NIL) "alternative" ("boundary" "===============0775904800==") ("inline" NIL) NIL NIL) "mixed" ("boundary" "_007_152AC7ECD1F8AB43A9AD95DBDDCA3118082C09GKIMA24cmcicfr_") NIL ("fr-FR") NIL)',
    ),
    b')'
]

BODYSTRUCTURE_SAMPLE_7 = [
    (b'856 (UID 11111 BODYSTRUCTURE ((("text" "plain" ("charset" "UTF-8") NIL NIL "7bit" 0 0 NIL NIL NIL NIL) "mixed" ("boundary" "----=_Part_407172_3159001.1321948277321") NIL NIL NIL)("application" "octet-stream" ("name" "26274308.pdf") NIL NIL "base64" 14906 NIL ("attachment" ("filename" "(26274308.pdf")) NIL NIL) "mixed" ("boundary" "----=_Part_407171_9686991.1321948277321") NIL NIL NIL)',)
    ,
    b')'
]

BODYSTRUCTURE_SAMPLE_8 = [
    (b'1 (UID 947 BODYSTRUCTURE ("text" "html" ("charset" "utf-8") NIL NIL "8bit" 889 34 NIL NIL NIL NIL) BODY[HEADER.FIELDS (FROM TO CC DATE SUBJECT)] {80}', 'From: Antoine Nguyen <tonio@ngyn.org>\r\nDate: Sat, 26 Mar 2016 11:45:49 +0100\r\n\r\n'),
    b')'
]
