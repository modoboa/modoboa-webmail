modoboa-webmail
===============

|gha| |codecov| |rtfd|

The webmail of Modoboa.

Installation
------------

Install this extension system-wide or inside a virtual environment by
running the following command::

  $ pip install modoboa-webmail

Edit the settings.py file of your modoboa instance and add
``modoboa_webmail`` inside the ``MODOBOA_APPS`` variable like this::

    MODOBOA_APPS = (
      'modoboa',
      'modoboa.core',
      'modoboa.lib',
      'modoboa.admin',
      'modoboa.relaydomains',
      'modoboa.limits',
      'modoboa.parameters',
      # Extensions here
      # ...
      'modoboa_webmail',
    )

Run the following commands to setup the database tables and collect static files::

  $ cd <modoboa_instance_dir>
  $ python manage.py load_initial_data
  $ python manage.py collectstatic
    
Finally, restart the python process running modoboa (uwsgi, gunicorn,
apache, whatever).

.. |gha| image:: https://github.com/modoboa/modoboa-webmail/actions/workflows/plugin.yml/badge.svg
   :target: https://github.com/modoboa/modoboa-webmail/actions/workflows/plugin.yml

.. |codecov| image:: https://codecov.io/gh/modoboa/modoboa-webmail/branch/master/graph/badge.svg
   :target: https://codecov.io/gh/modoboa/modoboa-webmail

.. |rtfd| image:: https://readthedocs.org/projects/modoboa-webmail/badge/?version=latest
   :target: https://readthedocs.org/projects/modoboa-webmail/?badge=latest
   :alt: Documentation Status
