# -*- coding: utf-8 -*-
"""
    flaskext.exceptional
    ~~~~~~~~~~~~~~~~~~~~

    Adds Exceptional support to Flask.

    :copyright: (c) 2011 by Jonathan Zempel.
    :license: BSD, see LICENSE for more details.
"""

from __future__ import with_statement
from Cookie import SimpleCookie
from datetime import datetime
from flask import _request_ctx_stack, Config, Flask, g, json
from functools import wraps
from re import match
from urllib2 import HTTPError, Request, urlopen, URLError
from werkzeug import Headers
from werkzeug.debug import tbtools
from zlib import compress
import os
import sys

EXCEPTIONAL_URL = "http://api.getexceptional.com/api/errors"

class Exceptional(object):
    """Extension for tracking application errors with Exceptional.
    Errors are not tracked if DEBUG is True. The application will
    log a warning if no ``EXCEPTIONAL_API_KEY`` has been configured.

    :param app: Default None. The Flask application to track errors
                for. If the app is not provided on creation, then it
                can be provided later via :meth:`init_app`.
    """

    def __init__(self, app=None):
        """Create this Exceptional extension.
        """
        if app is not None:
            self.init_app(app)
        else:
            self.app = None

    @property
    def __version__(self):
        """Get the version for this extension.
        """
        try:
            ret_val = __import__("pkg_resources").get_distribution("flask-exceptional").version
        except Exception:
            ret_val = "unknown"

        return ret_val

    def init_app(self, app):
        """Initialize this Exceptional extension.

        :param app: The Flask application to track errors for.
        """
        self.app = app

        if "EXCEPTIONAL_API_KEY" in app.config:
            app.config.setdefault("EXCEPTIONAL_COOKIE_FILTER", None)
            app.config.setdefault("EXCEPTIONAL_ENVIRONMENT_FILTER", ["SECRET_KEY"])
            app.config.setdefault("EXCEPTIONAL_HEADER_FILTER", None)
            app.config.setdefault("EXCEPTIONAL_PARAMETER_FILTER", None)
            app.config.setdefault("EXCEPTIONAL_SESSION_FILTER", None)
            app.config.setdefault("EXCEPTIONAL_HTTP_CODES", set(xrange(400, 418)))
            app.config.setdefault("EXCEPTIONAL_DEBUG_URL", None)
            self.__protocol_version = 5 # Using zlib compression.

            if app.debug:
                self.url = app.config["EXCEPTIONAL_DEBUG_URL"]
            elif app.testing:
                self.url = None
            else:
                self.url = "%s?api_key=%s&protocol_version=%d" % (
                    EXCEPTIONAL_URL,
                    app.config["EXCEPTIONAL_API_KEY"],
                    self.__protocol_version
                )

            if not hasattr(app, "extensions"):
                app.extensions = {}

            if "exceptional" in app.extensions:
                app.logger.warning("Repeated Exceptional initialization attempt.")
            else:
                app.handle_exception = self._get_exception_handler()
                app.handle_http_exception = self._get_http_exception_handler()
                app.extensions["exceptional"] = self
        else:
            app.logger.warning("Missing 'EXCEPTIONAL_API_KEY' configuration.")

    @staticmethod
    def test(config):
        """Test the given Flask configuration. If configured correctly,
        an error will be tracked by Exceptional for your app. Unlike
        the initialized extension, this test will post data to Exceptional,
        regardless of the configured ``DEBUG`` setting.

        :param config: The Flask application configuration object to test.
                       Accepts either :class:`flask.Config` or the object
                       types allowed by :meth:`flask.Config.from_object`.
        """
        app = Flask(__name__)
        exceptional = Exceptional()

        if isinstance(config, Config):
            app.config = config
        else:
            app.config.from_object(config)

        assert "EXCEPTIONAL_API_KEY" in app.config
        app.debug = False
        app.testing = False
        exceptional.init_app(app)
        app.testing = True

        @app.route("/exception")
        def exception():
            message = "Congratulations! Your application is configured for Exceptional error tracking."

            raise Exception(message)

        with app.test_client() as client:
            client.get("/exception")
            json.loads(g.exceptional)

    def _get_exception_handler(self):
        """Get a wrapped exception handler. Returns a handler that can be
        used to override Flask's ``app.handle_exception``. The wrapped
        handler posts error data to Exceptional and then passes the exception
        to the wrapped method.
        """
        handle_exception = self.app.handle_exception

        @wraps(handle_exception)
        def ret_val(exception):
            context = _request_ctx_stack.top
            self._post_data(context)

            return handle_exception(exception)

        return ret_val

    def _get_http_exception_handler(self):
        """Get a wrapped HTTP exception handler. Returns a handler that can
        be used to override Flask's ``app.handle_http_exception``. The wrapped
        handler posts HTTP error (i.e. '400: Bad Request') data to Exceptional
        and then passes the exception to the wrapped method.
        """
        handle_http_exception = self.app.handle_http_exception

        @wraps(handle_http_exception)
        def ret_val(exception):
            context = _request_ctx_stack.top

            if exception.code in context.app.config["EXCEPTIONAL_HTTP_CODES"]:
                self._post_data(context)

            return handle_http_exception(exception)

        return ret_val

    def _post_data(self, context):
        """POST data to the the Exceptional API. If DEBUG is True then data is
        sent to ``EXCEPTIONAL_DEBUG_URL`` if it has been defined. If TESTING is
        true, error data is stored in the global ``flask.g.exceptional`` variable.

        :param context: The current application context.
        """
        client_data = {
            "name": "flask-exceptional",
            "version": self.__version__,
            "protocol_version": self.__protocol_version
        }
        traceback = tbtools.get_current_traceback()
        error_data = json.dumps({
            "application_environment": self.__get_application_data(context.app),
            "client": client_data,
            "request": self.__get_request_data(context.app, context.request, context.session),
            "exception": self.__get_exception_data(traceback)
        })

        if context.app.testing:
            g.exceptional = error_data

        if self.url:
            request = Request(self.url)
            request.add_header("Content-Type", "application/json")

            if context.app.debug:
                data = error_data
            else:
                request.add_header("Content-Encoding", "deflate")
                data = compress(error_data, 1)

            try:
                try:
                    urlopen(request, data)
                except HTTPError, e:
                    if e.code >= 400:
                        raise
            except URLError:
                message = "Unable to connect to %s. See \
http://status.getexceptional.com for details. Error data:\n%s" % (self.url, error_data)
                self.app.logger.warning(message, exc_info=True)

    @staticmethod
    def __filter(app, data, filter_name):
        """Filter sensitive data.
        """
        filter = app.config[filter_name]

        if filter:
            ret_val = {}

            for key, value in data.iteritems():
                for item in filter:
                    if match(item, key):
                        value = "[FILTERED]"
                        break

                ret_val[key] = value
        else:
            ret_val = dict(data)

        return ret_val

    @staticmethod
    def __get_application_data(app):
        """Get application data.
        """
        environment = {}

        for name in app.config:
            value = app.config[name]
            environment[name] = str(value) if value else None

        for name in os.environ:
            value = os.environ[name]
            environment["os.%s" % name] = value

        return {
            "framework": "flask",
            "env": Exceptional.__filter(app, environment, "EXCEPTIONAL_ENVIRONMENT_FILTER"),
            "language": "python",
            "language_version": sys.version.replace('\n', ''),
            "application_root_directory": app.root_path
        }

    @staticmethod
    def __get_exception_data(traceback):
        """Get exception data.
        """
        timestamp = datetime.utcnow()
        backtrace = []

        for frame in traceback.frames:
            backtrace.insert(0, "File \"%s\", line %d, in %s\n\t%s" % (
                frame.filename,
                frame.lineno,
                frame.function_name,
                frame.current_line.strip()
            ))

        return {
            "occurred_at": "%sZ" % timestamp.isoformat(),
            "message": traceback.exception.split(': ', 1)[-1],
            "backtrace": backtrace,
            "exception_class": traceback.exception_type
        }

    @staticmethod
    def __get_request_data(app, request, session):
        """Get request data.
        """
        parameters = {}
        form = request.form.to_dict(flat=False)

        for key, value in form.iteritems():
            if len(value) == 1:
                parameters[key] = value[0]
            else:
                parameters[key] = value

        files = request.files.to_dict(flat=False)

        for key, value in files.iteritems():
            if len(value) == 1:
                parameters[key] = value[0].filename
            else:
                parameters[key] = [file.filename for file in value]

        if request.cookies:
            cookies = Exceptional.__filter(app, request.cookies, "EXCEPTIONAL_COOKIE_FILTER")
            headers = Headers(request.headers) # Get a mutable dictionary.
            cookie = SimpleCookie()

            for key, value in cookies.iteritems():
                cookie[key] = value

            headers["Cookie"] = cookie.output(header='', sep=';').strip()
        else:
            headers = request.headers

        return {
            "session": Exceptional.__filter(app, session, "EXCEPTIONAL_SESSION_FILTER"),
            "remote_ip": request.remote_addr,
            "parameters": Exceptional.__filter(app, parameters, "EXCEPTIONAL_PARAMETER_FILTER"),
            "action": request.endpoint.split('.', 1)[-1] if request.endpoint else None,
            "url": request.url,
            "request_method": request.method,
            "controller": request.blueprint if hasattr(request, "blueprint") else request.module,
            "headers": Exceptional.__filter(app, headers, "EXCEPTIONAL_HEADER_FILTER")
        }
