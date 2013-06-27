# -*- coding: utf-8 -*-
"""
    flask_exceptional
    ~~~~~~~~~~~~~~~~~

    Adds Exceptional support to Flask.

    :copyright: (c) 2012 by Jonathan Zempel.
    :license: BSD, see LICENSE for more details.
"""

from __future__ import with_statement
from Cookie import SimpleCookie
from datetime import datetime
from flask import _request_ctx_stack as stack, Config, Flask, g
from functools import wraps
from httplib import BadStatusLine
from re import match
from urllib2 import HTTPError, Request, urlopen, URLError
from werkzeug import Headers
from werkzeug.debug import tbtools
from zlib import compress
import os
import sys

try:
    from flask.json import _json as json
except ImportError:
    from flask import json

try:
    import pkg_resources
except ImportError:
    pkg_resources = None  # NOQA

EXCEPTIONAL_URL = "http://api.exceptional.io/api/errors"


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

    @property
    def __version__(self):
        """Get the version for this extension.
        """
        if pkg_resources:
            ret_val = pkg_resources.get_distribution("flask-exceptional").version  # NOQA
        else:
            ret_val = "unknown"

        return ret_val

    def init_app(self, app):
        """Initialize this Exceptional extension.

        :param app: The Flask application to track errors for.
        """
        if "EXCEPTIONAL_API_KEY" in app.config:
            app.config.setdefault("EXCEPTIONAL_COOKIE_FILTER", None)
            app.config.setdefault("EXCEPTIONAL_ENVIRONMENT_FILTER",
                    ["SECRET_KEY"])
            app.config.setdefault("EXCEPTIONAL_HEADER_FILTER", None)
            app.config.setdefault("EXCEPTIONAL_PARAMETER_FILTER", None)
            app.config.setdefault("EXCEPTIONAL_SESSION_FILTER", None)
            app.config.setdefault("EXCEPTIONAL_HTTP_CODES",
                    set(xrange(400, 418)))
            app.config.setdefault("EXCEPTIONAL_DEBUG_URL", None)
            self.__protocol_version = 5  # Using zlib compression.

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
                app.logger.warning("Repeated Exceptional initialization attempt.")  # NOQA
            else:
                app.handle_exception = self._get_exception_handler(app)
                app.handle_http_exception = self._get_http_exception_handler(app)  # NOQA
                app.extensions["exceptional"] = self
        else:
            app.logger.warning("Missing 'EXCEPTIONAL_API_KEY' configuration.")

    @staticmethod
    def context(data=None, **kwargs):
        """Add extra context data to the current tracked exception. The context
        data is only valid for the current request. Multiple calls to this
        method will update any existing context with new data.

        :param data: Default ``None``. A dictionary of context data.
        :param kwargs: A series of keyword arguments to use as context data.
        """
        context = getattr(stack.top, "exceptional_context", None)

        if context is None:
            context = {}
            setattr(stack.top, "exceptional_context", context)

        if data is not None:
            context.update(data)

        if len(kwargs):
            context.update(kwargs)

    @staticmethod
    def publish(config, traceback):
        """Publish the given traceback directly to Exceptional. This method is
        useful for tracking errors that occur outside the context of a Flask
        request. For example, this may be called from an asynchronous queue.

        :param config: A Flask application configuration object. Accepts either
                       :class:`flask.Config` or the object types allowed by
                       :meth:`flask.Config.from_object`.
        :param traceback: A :class:`werkzeug.debug.tbtools.Traceback` instance
                          to publish.
        """
        app = Flask(__name__)
        exceptional = Exceptional()

        if isinstance(config, Config):
            app.config = config
        else:
            app.config.from_object(config)

        exceptional.init_app(app)

        return exceptional._post_data(app, traceback=traceback)

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
        context = getattr(stack.top, "exceptional_context", None)
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
            setattr(stack.top, "exceptional_context", context)
            message = "Congratulations! Your application is configured for Exceptional error tracking."  # NOQA

            raise Exception(message)

        with app.test_client() as client:
            client.get("/exception")
            json.loads(g.exceptional)

    def _get_exception_handler(self, app):
        """Get a wrapped exception handler. Returns a handler that can be
        used to override Flask's ``app.handle_exception``. The wrapped
        handler posts error data to Exceptional and then passes the exception
        to the wrapped method.

        :param app: The app for which the exception handler is being wrapped.
        """
        handle_exception = app.handle_exception

        @wraps(handle_exception)
        def ret_val(exception):
            self._post_data(stack.top)

            return handle_exception(exception)

        return ret_val

    def _get_http_exception_handler(self, app):
        """Get a wrapped HTTP exception handler. Returns a handler that can
        be used to override Flask's ``app.handle_http_exception``. The wrapped
        handler posts HTTP error (i.e. '400: Bad Request') data to Exceptional
        and then passes the exception to the wrapped method.

        :param app: The app for which the HTTP exception handler is being
            wrapped.
        """
        handle_http_exception = app.handle_http_exception

        @wraps(handle_http_exception)
        def ret_val(exception):
            context = stack.top

            if exception.code in context.app.config["EXCEPTIONAL_HTTP_CODES"]:
                self._post_data(context)

            return handle_http_exception(exception)

        return ret_val

    def _post_data(self, context, traceback=None):
        """POST data to the the Exceptional API. If DEBUG is True then data is
        sent to ``EXCEPTIONAL_DEBUG_URL`` if it has been defined. If TESTING is
        true, error data is stored in the global ``flask.g.exceptional``
        variable.

        :param context: The current application or application context.
        :param traceback: Default ``None``. The exception stack trace.
        """
        if context:
            if isinstance(context, Flask):
                app = context
                context = None
            else:
                app = context.app
        else:
            app = stack.top.app

        application_data = self.__get_application_data(app)
        client_data = {
            "name": "flask-exceptional",
            "version": self.__version__,
            "protocol_version": self.__protocol_version
        }

        if context:
            request_data = self.__get_request_data(app, context.request,
                    context.session)
            context_data = getattr(context, "exceptional_context", None)
        else:
            request_data = None
            context_data = None

        traceback = traceback or tbtools.get_current_traceback()
        exception_data = self.__get_exception_data(traceback)
        encode_basestring = json.encoder.encode_basestring

        def _encode_basestring(value):
            if isinstance(value, str) and \
                    json.encoder.HAS_UTF8.search(value) is not None:
                value = value.decode("utf-8",
                        "replace")  # ensure the decode succeeds.

            replace = lambda match: json.encoder.ESCAPE_DCT[match.group(0)]

            return u'"%s"' % json.encoder.ESCAPE.sub(replace, value)

        try:
            json.encoder.encode_basestring = _encode_basestring
            ret_val = json.dumps({
                "application_environment": application_data,
                "client": client_data,
                "request": request_data,
                "exception": exception_data,
                "context": context_data
            }, ensure_ascii=False).encode("utf-8")
        finally:
            json.encoder.encode_basestring = encode_basestring

        if context and app.testing:
            g.exceptional = ret_val

        if self.url:
            request = Request(self.url)
            request.add_header("Content-Type", "application/json")

            if app.debug:
                data = ret_val
            else:
                request.add_header("Content-Encoding", "deflate")
                data = compress(ret_val, 1)

            try:
                try:
                    urlopen(request, data)
                except HTTPError, e:
                    if e.code >= 400:
                        raise
            except URLError:
                message = "Unable to connect to %s. See http://status.exceptional.io for details. Error data:\n%s"  # NOQA
                app.logger.warning(message, self.url, ret_val,
                        exc_info=True)
            except BadStatusLine:
                pass

        return ret_val

    @staticmethod
    def __filter(app, data, filter_name):
        """Filter sensitive data.
        """
        filter = app.config.get(filter_name)

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
            environment["os.%s" % name] = str(value)

        if pkg_resources:
            modules = {}

            for module in pkg_resources.working_set:
                modules[module.project_name] = module.version
        else:
            modules = None

        return {
            "framework": "flask",
            "env": Exceptional.__filter(app, environment,
                "EXCEPTIONAL_ENVIRONMENT_FILTER"),
            "language": "python",
            "language_version": sys.version.replace('\n', ''),
            "application_root_directory": app.root_path,
            "loaded_libraries": modules
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
        try:
            parameters = request.json or {}
        except:
            parameters = {"INVALID_JSON": request.data}

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
            cookies = Exceptional.__filter(app, request.cookies,
                    "EXCEPTIONAL_COOKIE_FILTER")
            headers = Headers(request.headers)  # Get a mutable dictionary.
            cookie = SimpleCookie()

            for key, value in cookies.iteritems():
                cookie[key] = value

            headers["Cookie"] = cookie.output(header='', sep=';').strip()
        else:
            headers = request.headers

        return {
            "session": Exceptional.__filter(app, session,
                "EXCEPTIONAL_SESSION_FILTER"),
            "remote_ip": request.remote_addr,
            "parameters": Exceptional.__filter(app, parameters,
                "EXCEPTIONAL_PARAMETER_FILTER"),
            "action": request.endpoint.split('.', 1)[-1] if request.endpoint
                else None,
            "url": request.url,
            "request_method": request.method,
            "controller": request.blueprint if hasattr(request, "blueprint")
                else request.module,
            "headers": Exceptional.__filter(app, headers,
                "EXCEPTIONAL_HEADER_FILTER")
        }
