# -*- coding: utf-8 -*-
"""
    tests
    ~~~~~

    Flask Exceptional extension unit testing.

    :copyright: (c) 2011 by Jonathan Zempel.
    :license: BSD, see LICENSE for more details.
"""

from __future__ import with_statement
from flask import abort, Flask, g, json
from flaskext.exceptional import Exceptional
from os import environ
import unittest

class ExceptionalTestCase(unittest.TestCase):
    """Exceptional extension test cases.
    """
    
    @staticmethod
    def create_application():
        """Create a test Flask application.
        """
        ret_val = Flask(__name__)
        ret_val.testing = True
        ret_val.config["EXCEPTIONAL_API_KEY"] = "key"
        ret_val.config["EXCEPTIONAL_DEBUG_URL"] = environ.get("EXCEPTIONAL_DEBUG_URL",
            "http://www.postbin.org/m7viy8")
        
        @ret_val.route("/error")
        def error():
            """Do something that raises an exception.
            """
            1 / 0
        
        @ret_val.route("/http/<int:code>")
        def http(code):
            """Raises an HTTP exception.
            """
            abort(code)
    
        return ret_val
    
    def setUp(self):
        """Set up each test.
        """
        self.app = self.create_application()
        self.exceptional = Exceptional(self.app)
    
    def test_01_exception(self):
        """Test mandatory data requirements for the Exceptional API.
        See http://docs.getexceptional.com/api/publish for details.
        """
        with self.app.test_client() as client:
            client.get("/error")
            data = json.loads(g.exceptional)
            exception = data["exception"]
            assert "backtrace" in exception
            assert "exception_class" in exception
            assert "message" in exception
            assert "occurred_at" in exception
            environment = data["application_environment"]
            assert environment["application_root_directory"] == self.app.root_path
            assert "env" in environment
    
    def test_02_http_exception(self):
        """Test logging an HTTP exception.
        """
        with self.app.test_client() as client:
            client.get("/http/404")
            data = json.loads(g.exceptional)
            exception = data["exception"]
            assert "404" in exception["message"]
    
    def test_03_post_form(self):
        """Test POSTing form data.
        """
        data = {"foo": "bar", "baz": "qux"}
        
        with self.app.test_client() as client:
            client.post("/error", data=data)
            data = json.loads(g.exceptional)
            request = data["request"]
            parameters = request["parameters"]
            assert parameters["foo"] == "bar"
            assert parameters["baz"] == "qux"
    
    def test_04_post_file(self):
        """Test POSTing file data.
        """
        resource = self.app.open_resource("README")
        data = {"file": resource}
        
        with self.app.test_client() as client:
            client.post("/error", data=data)
            data = json.loads(g.exceptional)
            request = data["request"]
            parameters = request["parameters"]
            assert "file" in parameters
    
    def test_05_filter_header(self):
        """Test header data filtering.
        """
        self.app.config["EXCEPTIONAL_HEADER_FILTER"] = ["Host"]
        Exceptional(self.app)
        
        with self.app.test_client() as client:
            client.get("/error")
            data = json.loads(g.exceptional)
            request = data["request"]
            headers = request["headers"]
            assert headers["Host"] == "[FILTERED]"
    
    def test_06_filter_parameter(self):
        """Test parameter data filtering.
        """
        data = {"foo": "bar", "baz": "qux"}
        self.app.config["EXCEPTIONAL_PARAMETER_FILTER"] = ["baz"]
        Exceptional(self.app)
        
        with self.app.test_client() as client:
            client.post("/error", data=data)
            data = json.loads(g.exceptional)
            request = data["request"]
            parameters = request["parameters"]
            assert parameters["baz"] == "[FILTERED]"
    
    def test_07_unexceptional(self):
        """Test disabled Exceptional logging.
        """
        self.app = self.create_application()
        del self.app.config["EXCEPTIONAL_API_KEY"]
        Exceptional(self.app)
        
        with self.app.test_client() as client:
            client.get("/error")
            assert hasattr(g, "exceptional") == False
    
    def test_08_http_unexceptional(self):
        """Test non-logged HTTP error code.
        """
        with self.app.test_client() as client:
            client.get("/http/500")
            assert hasattr(g, "exceptional") == False
    
    def test_09_debug(self):
        """Test exception in debug mode.
        """
        self.app.config["EXCEPTIONAL_ENVIRONMENT_FILTER"].append("os.*")
        self.app.debug = True
        exceptional = Exceptional(self.app)
        assert exceptional.url == self.app.config["EXCEPTIONAL_DEBUG_URL"]
        
        with self.app.test_client() as client:
            self.assertRaises(ZeroDivisionError, client.get, "/error")
            json.loads(g.exceptional)
            print "See {0} for HTTP request details.".format(exceptional.url)

if __name__ == "__main__":
    unittest.main()

