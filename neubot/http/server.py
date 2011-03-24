# neubot/http/server.py

#
# Copyright (c) 2010-2011 Simone Basso <bassosimone@gmail.com>,
#  NEXA Center for Internet & Society at Politecnico di Torino
#
# This file is part of Neubot <http://www.neubot.org/>.
#
# Neubot is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Neubot is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Neubot.  If not, see <http://www.gnu.org/licenses/>.
#

import StringIO
import mimetypes
import sys
import os.path
import socket
import getopt
import time

if __name__ == "__main__":
    sys.path.insert(0, ".")

from neubot.http.stream import ERROR
from neubot.http.messages import Message
from neubot.http.ssi import ssi_replace
from neubot.http.utils import nextstate
from neubot.http.stream import StreamHTTP
from neubot.http.utils import prettyprint
from neubot.net.stream import Listener
from neubot.utils import safe_seek
from neubot.options import OptionParser
from neubot.utils import asciify
from neubot.log import LOG
from neubot.net.poller import POLLER
from neubot.net.stream import VERBOSER

# 3-letter abbreviation of month names, note that
# python tm.tm_mon is in range [1,12]
# we use our abbreviation because we don't want the
# month name to depend on the locale
MONTH = [
    "", "Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug",
    "Sep", "Oct", "Nov", "Dec",
]


class ServerStream(StreamHTTP):

    """Reads HTTP requests and provides ways to send a response."""

    def __init__(self, poller):
        StreamHTTP.__init__(self, poller)
        self.request = None

    def got_request_line(self, method, uri, protocol):
        self.request = Message(method=method, uri=uri, protocol=protocol)

    def got_response_line(self, protocol, code, reason):
        self.close()

    def got_header(self, key, value):
        if self.request:
            self.request[key] = value
        else:
            self.close()

    def got_end_of_headers(self):
        if self.request:
            prettyprint(LOG.debug, "< ", self.request)
            if not self.parent.got_request_headers(self, self.request):
                return ERROR, 0
            return nextstate(self.request)
        else:
            return ERROR, 0

    def got_piece(self, piece):
        if self.request:
            self.request.body.write(piece)
        else:
            self.close()

    def got_end_of_body(self):
        if self.request:
            safe_seek(self.request.body, 0)
            self.parent.got_request(self, self.request)
            self.request = None
        else:
            self.close()

    def send_response(self, request, response):
        prettyprint(LOG.debug, "> ", response)
        self.send_message(response)

        address = self.peername[0]
        now = time.gmtime()
        timestring = "%02d/%s/%04d:%02d:%02d:%02d -0000" % (now.tm_mday,
          MONTH[now.tm_mon], now.tm_year, now.tm_hour, now.tm_min, now.tm_sec)
        requestline = " ".join([request.method, request.uri, request.protocol])
        statuscode = response.code

        nbytes = "-"
        if response["content-length"]:
            nbytes = response["content-length"]
            if nbytes == "0":
                nbytes = "-"

        LOG.log_access("%s - - [%s] \"%s\" %s %s" % (address, timestring,
                                                     requestline, statuscode,
                                                     nbytes))


class HTTPListener(Listener):

    """Reads HTTP requests and dispatch control to some parent class."""

    def __init__(self, poller):
        Listener.__init__(self, poller)
        self.stream = ServerStream
        self.dictionary = {}
        self.parent = None                      # XXX

    def configure(self, dictionary):
        self.dictionary = dictionary

    def bind_failed(self, exception):
        self.parent.bind_failed(self, exception)

    def started_listening(self):
        self.parent.started_listening(self)

    def accept_failed(self, exception):
        self.parent.accept_failed(self, exception)

    def connection_lost(self, stream):
        self.parent.connection_lost(self, stream)

    def connection_made(self, stream):
        stream.configure(self.dictionary)

    def got_request_headers(self, stream, request):
        return self.parent.got_request_headers(self, stream, request)

    def got_request(self, stream, request):
        try:
            self.process_request(stream, request)
        except (KeyboardInterrupt, SystemExit):
            raise
        except:
            LOG.exception()
            response = Message()
            response.compose(code="500", reason="Internal Server Error",
                    body=StringIO.StringIO("500 Internal Server Error"))
            stream.send_response(request, response)

    def process_request(self, stream, request):
        return self.parent.process_request(self, stream, request)


REDIRECT = """
<HTML>
 <HEAD>
  <TITLE>Moved permanently</TITLE>
 </HEAD>
 <BODY>
  Moved permanently to <A HREF="/index.html">index.html</A>.
 </BODY>
</HTML>
"""


class ServerHTTP(object):

    """Manages multiple HTTP ports."""

    def __init__(self, poller):
        self.poller = poller
        self.dictionary = {}

    def configure(self, dictionary):
        self.dictionary = dictionary

    def register_servicex(self, prefix, service):
        if not "prefixes" in self.dictionary:
            self.dictionary["prefixes"] = {}

        prefixes = self.dictionary["prefixes"]
        prefixes[prefix] = service.serve

    #XXX must be run after configure()
    def register_service(self, prefix, module):

        try:
            exec "from %s import ServiceHTTP" % module
        except ImportError:
            LOG.error("Failed to import service")
            LOG.exception()
            return

        try:
            service = ServiceHTTP()
        except (KeyboardInterrupt, SystemExit):
            raise
        except:
            LOG.error("Failed to create service instance")
            LOG.exception()
            return

        self.register_servicex(prefix, service)

    def listen(self, endpoint, family=socket.AF_INET, sobuf=0):
        listener = HTTPListener(self.poller)
        listener.parent = self
        listener.configure(self.dictionary)
        listener.listen(endpoint, family, sobuf)

    def bind_failed(self, listener, exception):
        VERBOSER.bind_failed(listener.endpoint, exception)

    def started_listening(self, listener):
        VERBOSER.started_listening(listener.endpoint)

    def accept_failed(self, listener, exception):
        pass

    def connection_lost(self, listener, stream):
        pass

    def got_request_headers(self, listener, stream, request):
        return True

    def process_request(self, listener, stream, request):
        response = Message()

        if not request.uri.startswith("/"):
            response.compose(code="403", reason="Forbidden",
                    body=StringIO.StringIO("403 Forbidden"))
            stream.send_response(request, response)
            return

        prefixes = self.dictionary.get("prefixes", None)
        if prefixes:
            for prefix, func in prefixes.items():
                if request.uri.startswith(prefix):
                    func(self, listener, stream, request)
                    return

        rootdir = self.dictionary.get("rootdir", "")
        if not rootdir:
            response.compose(code="403", reason="Forbidden",
                    body=StringIO.StringIO("403 Forbidden"))
            stream.send_response(request, response)
            return

        if request.uri == "/":
            stringio = StringIO.StringIO(REDIRECT)
            response.compose(code="301", reason="Moved Permanently",
              body=stringio, mimetype="text/html; charset=UTF-8")
            # Yes, here we violate RFC 2616 Sect. 14.30
            response["location"] = "/index.html"
            stream.send_response(request, response)
            return

        rootdir = asciify(rootdir)
        uripath = asciify(request.uri)
        fullpath = os.path.normpath(rootdir + uripath)
        fullpath = asciify(fullpath)

        if not fullpath.startswith(rootdir):
            response.compose(code="403", reason="Forbidden",
                    body=StringIO.StringIO("403 Forbidden"))
            stream.send_response(request, response)
            return

        try:
            fp = open(fullpath, "rb")
        except (IOError, OSError):
            response.compose(code="404", reason="Not Found",
                    body=StringIO.StringIO("404 Not Found"))
            stream.send_response(request, response)
            return

        mimetype, encoding = mimetypes.guess_type(fullpath)

        if mimetype == "text/html":
            ssi = self.dictionary.get("ssi", False)
            if ssi:
                body = ssi_replace(rootdir, fp)
                fp = StringIO.StringIO(body)

        if encoding:
            mimetype = "; charset=".join((mimetype, encoding))

        response.compose(code="200", reason="Ok", body=fp,
                         mimetype=mimetype)
        if request.method == "HEAD":
            safe_seek(fp, 0, os.SEEK_END)
        stream.send_response(request, response)


# unit test

USAGE = """Neubot httpd -- Test unit for the http server module

Usage: neubot httpd [-Vv] [-D macro[=value]] [-f file] [--help]

Options:
    -D macro[=value]   : Set the value of the macro `macro`.
    -f file            : Read options from file `file`.
    --help             : Print this help screen and exit.
    -V                 : Print version number and exit.
    -v                 : Run the program in verbose mode.

Macros (defaults in square brackets):
    address=addr       : Select the address to use                 [0.0.0.0]
    ports=port         : Comma-separated list of ports to use      [8080]
    rootdir=dir        : Specify root directory for WWW            []
    services=list      : Comma separated list of `prefix:mod`
                         couples, where `prefix` is the API prefix
                         and `mod` is the module name, e.g.
                             /api:neubot.api_service               []
    ssi                : Enable Server-Side Includes (SSI)         [False]

You MUST specify the root directory if you want this webserver to
serve pages requests.
"""

VERSION = "Neubot 0.3.6\n"

def main(args):

    conf = OptionParser()
    conf.set_option("httpd", "address", "0.0.0.0")
    conf.set_option("httpd", "ports", "8080")
    conf.set_option("httpd", "rootdir", "")
    conf.set_option("httpd", "services", "")
    conf.set_option("httpd", "ssi", "False")

    try:
        options, arguments = getopt.getopt(args[1:], "D:f:Vv", ["help"])
    except getopt.GetoptError:
        sys.stderr.write(USAGE)
        sys.exit(1)

    for name, value in options:
        if name == "-D":
             conf.register_opt(value, "httpd")
             continue
        if name == "-f":
             conf.register_file(value)
             continue
        if name == "--help":
             sys.stdout.write(USAGE)
             sys.exit(0)
        if name == "-V":
             sys.stdout.write(VERSION)
             sys.exit(0)
        if name == "-v":
             LOG.verbose()
             continue

    conf.merge_files()
    conf.merge_environ()
    conf.merge_opts()

    address = conf.get_option("httpd", "address")
    ports = conf.get_option("httpd", "ports")
    rootdir = conf.get_option("httpd", "rootdir")
    services = conf.get_option("httpd", "services")
    ssi = conf.get_option_bool("httpd", "ssi")

    dictionary = {
        "rootdir": rootdir,
        "ssi": ssi,
    }

    server = ServerHTTP(POLLER)
    server.configure(dictionary)

    if services:
        for service in services.split(","):
            prefix, mod = service.split(":")
            server.register_service(prefix, mod)

    for port in ports.split(","):
        endpoint = (address, port)
        server.listen(endpoint)

    POLLER.loop()

if __name__ == "__main__":
    main(sys.argv)
