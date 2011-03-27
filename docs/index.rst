Flask-Exceptional
=================

.. module:: flaskext.exceptional

Flask-Exceptional adds `Exceptional`_ support to `Flask`_. Exceptional
tracks errors in your application, reports them real-time, and gathers
the info you need to fix them fast. Visit http://www.getexceptional.com
to give it a try.

Installation
------------

The remaining documentation assumes you have access to an Exceptional
account. Install the extension with one of the following commands::

    $ easy_install Flask-Exceptional

or alternatively if you have pip installed::

    $ pip install Flask-Exceptional

Quickstart
----------

After installing Flask-Exceptional, all you have to do is create a Flask
application, configure the Exceptional API key, and create the
:class:`Exceptional` object. It's this easy::

    from flask import Flask
    from flaskext.exceptional import Exceptional
    
    app = Flask(__name__)
    app.config["EXCEPTIONAL_API_KEY"] = "exceptional_forty_character_unique_key"
    exceptional = Exceptional(app)

Your application is configured for cloud-based error monitoring! You can
verify your configuration is working by calling the
:meth:`Exceptional.test` method::

    Exceptional.test(app.config)

Check out the following section for more detail on the available
Flask-Exceptional configuration settings.

Configuration
-------------

The following configuration settings exist for Flask-Exceptional:

=================================== ======================================
`EXCEPTIONAL_API_KEY`               The Exceptional API key for your
                                    application. Login to Exceptional,
                                    select your app, and click the *APP
                                    SETTINGS* link. The displayed API key
                                    is the value to use here.
                                    
                                    Attempting to create the extension
                                    without supplying an API key will
                                    result in a logged warning, but the
                                    app will continue to run as normal.
`EXCEPTIONAL_DEBUG_URL`             If your app is running in debug mode,
                                    errors are not tracked with
                                    Exceptional. Configure this value to
                                    capture error data in debug mode. For
                                    example, you may use a `PostBin`_ URL
                                    to debug your application. JSON error
                                    data is POSTed uncompressed to this
                                    URL, whereas Exceptional requires the
                                    data to be compressed.
`EXCEPTIONAL_HTTP_CODES`            A list of codes for HTTP errors that
                                    will be tracked with Exceptional.
                                    
                                    Defaults to standard HTTP 4xx codes.
`EXCEPTIONAL_PARAMETER_FILTER`      A list of values to filter from the
                                    parameter data sent to Exceptional.
                                    Parameter data includes everything
                                    in ``request.form`` and
                                    ``request.files``.
                                    
                                    For example, to filter passwords you
                                    might use:
                                    
                                    ``['password', 'password_confirm']``
`EXCEPTIONAL_ENVIRONMENT_FILTER`    A list of values to filter from the
                                    environment data sent to Exceptional.
                                    The environment data includes the
                                    Flask application config plus the
                                    current OS environment. OS environment
                                    values are prefixed by ``'os.'``.
                                    
                                    For example, to filter the SQL
                                    Alchemy database URI and all OS
                                    environment values, use:
                                    
                                    ``['SQLALCHEMY_DATABASE_URI', 'os.*']``
                                    
                                    Defaults to ``['SECRET_KEY']``
`EXCEPTIONAL_SESSION_FILTER`        A list of values to filter from the
                                    session data sent to Exceptional.
`EXCEPTIONAL_HEADER_FILTER`         A list of values to filter from the
                                    HTTP header data sent to Exceptional.
`EXCEPTIONAL_COOKIE_FILTER`         A list of names to filter from the
                                    HTTP Cookie header data sent to
                                    Exceptional.
=================================== ======================================

.. note:: All configuration filter lists accept both strings and regular
          expression patterns.

API
___

.. autoclass:: Exceptional
   :members:


.. _Exceptional: http://www.getexceptional.com/
.. _Flask: http://flask.pocoo.org/
.. _PostBin: http://www.postbin.org/