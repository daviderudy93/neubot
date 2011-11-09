# neubot/speedtest/wrapper.py

#
# Copyright (c) 2011 Simone Basso <bassosimone@gmail.com>,
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

''' Wrapper for speedtest server '''

import StringIO

from neubot.http.server import ServerHTTP
from neubot.http.server import HTTP_SERVER
from neubot.speedtest.server import SPEEDTEST_SERVER
from neubot.negotiate.server import NEGOTIATE_SERVER
from neubot.compat import json
from neubot import marshal

#
# Classes that represent the old XML messages used
# by speedtest.  I need to disable pylint because
# it's not possible here to fix the names and/or to
# add methods or remove fields.
#

class SpeedtestCollect(object):

    ''' Old XML collect request '''

    # pylint: disable=R0902
    # pylint: disable=R0903

    def __init__(self):
        # pylint: disable=C0103
        self.client = ''
        self.timestamp = 0
        self.internalAddress = ''
        self.realAddress = ''
        self.remoteAddress = ''
        self.connectTime = 0.0
        self.latency = 0.0
        self.downloadSpeed = 0.0
        self.uploadSpeed = 0.0
        self.privacy_informed = 0
        self.privacy_can_collect = 0
        self.privacy_can_share = 0
        self.platform = ''
        self.neubot_version = ''

class SpeedtestNegotiate_Response(object):

    ''' Old XML negotiate response '''

    # pylint: disable=R0903

    def __init__(self):
        # pylint: disable=C0103
        self.authorization = ''
        self.publicAddress = ''
        self.unchoked = 0
        self.queuePos = 0
        self.queueLen = 0

# Wrapper because the negotiator uses JSON and clients use XML
class SpeedtestWrapper(ServerHTTP):

    ''' Speedtest server wrapper '''

    # Adapted from neubot/negotiate/server.py
    def got_request_headers(self, stream, request):
        ''' Decide whether we can accept this HTTP request '''
        isgood = (request['transfer-encoding'] == '' and
                  request.content_length() <= 1048576 and
                  request.uri.startswith('/speedtest/'))
        return isgood

    def process_request(self, stream, request):
        ''' Dispatch and process the incoming HTTP request '''
        if request.uri == '/speedtest/negotiate':
            self.do_negotiate(stream, request)
        elif request.uri == '/speedtest/collect':
            self.do_collect(stream, request)
        else:
            raise RuntimeError('Invalid URI')

    @staticmethod
    def _rewrite_response(request, response):
        ''' Rewrite response and translate JSON to XML '''

        # Do not touch error responses
        if response.code != '200':
            return

        elif request.uri == '/negotiate/speedtest':
            response_body = json.loads(response.body)

            xmlresp = SpeedtestNegotiate_Response()
            xmlresp.authorization = response_body['authorization']
            xmlresp.unchoked = response_body['unchoked']
            xmlresp.queuePos = response_body['queue_pos']
            xmlresp.publicAddress = response_body['real_address']

            response.body = marshal.marshal_object(xmlresp, 'application/xml')
            del response['content-type']
            del response['content-length']
            response['content-type'] = 'application/xml'
            response['content-length'] = str(len(response.body))

        elif request.uri == '/collect/speedtest':
            del response['content-type']
            del response['content-length']
            response.body = ''

        #
        # We MUST NOT be too strict here because old clients
        # use the same stream for both negotiation and testing
        # and the stream already has the rewriter installed
        # due to that.
        #
        else:
            pass

    #
    # Set the response rewriter so that we can spit out XML
    # as expected by speedtest clients.
    # We should rewrite the URI because the negotiate server
    # does not like a URI starting with /speedtest.
    #
    def do_negotiate(self, stream, request):
        ''' Invoked on GET /speedtest/negotiate '''
        stream.response_rewriter = self._rewrite_response
        request.uri = '/negotiate/speedtest'
        request.body = StringIO.StringIO('{}')
        NEGOTIATE_SERVER.process_request(stream, request)

    #
    # Set the response rewriter so that we can suppress the
    # empty JSON returned by the negotiation server.
    # We should rewrite the URI because the negotiate server
    # does not like a URI starting with /speedtest.
    # Map message fields from the unserialized XML object
    # to the serialized JSON expected by the new speedtest
    # negotiator code.
    #
    def do_collect(self, stream, request):
        ''' Invoked on GET /speedtest/collect '''
        stream.response_rewriter = self._rewrite_response
        request.uri = '/collect/speedtest'

        xmlreq = marshal.unmarshal_object(request.body.read(),
           'application/xml', SpeedtestCollect)
        message = {
            'uuid': xmlreq.client,
            'timestamp': int(float(xmlreq.timestamp)),  # old clients bug
            'internal_address': xmlreq.internalAddress,
            'real_address': xmlreq.realAddress,
            'remote_address': xmlreq.remoteAddress,
            'connect_time': xmlreq.connectTime,
            'latency': xmlreq.latency,
            'download_speed': xmlreq.downloadSpeed,
            'upload_speed': xmlreq.uploadSpeed,
            'privacy_informed': xmlreq.privacy_informed,
            'privacy_can_collect': xmlreq.privacy_can_collect,
            'privacy_can_share': xmlreq.privacy_can_share,
            'platform': xmlreq.platform,
            'neubot_version': xmlreq.neubot_version,
        }
        request['content-type'] = 'application/json'
        request.body = StringIO.StringIO(json.dumps(message))

        NEGOTIATE_SERVER.process_request(stream, request)

SPEEDTEST_WRAPPER = SpeedtestWrapper(None)

#
# Add here the run() function but this should actually
# be moved in speedtest/__init__.py in the future.
#
def run(poller, conf):
    ''' Start the server-side of the speedtest module '''

    HTTP_SERVER.register_child(SPEEDTEST_WRAPPER, '/speedtest/negotiate')
    HTTP_SERVER.register_child(SPEEDTEST_WRAPPER, '/speedtest/collect')

    HTTP_SERVER.register_child(SPEEDTEST_SERVER, '/speedtest/latency')
    HTTP_SERVER.register_child(SPEEDTEST_SERVER, '/speedtest/download')
    HTTP_SERVER.register_child(SPEEDTEST_SERVER, '/speedtest/upload')