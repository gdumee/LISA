# -*- coding: UTF-8 -*-
#-----------------------------------------------------------------------------
# project     : Lisa server
# module      : web interface
# file        : websockets.py
# description : Server socket management for web interface
# author      : G.Dumee
#-----------------------------------------------------------------------------
# copyright   : Neotique
#-----------------------------------------------------------------------------


#-----------------------------------------------------------------------------
# Imports
#-----------------------------------------------------------------------------
import os, json
from twisted.python import log
from twisted.internet.protocol import ReconnectingClientFactory
from twisted.protocols.basic import LineReceiver
from OpenSSL import SSL
from twisted.internet import reactor, ssl
from autobahn.twisted.websocket import WebSocketServerProtocol
from lisa.server.config_manager import ConfigManager


#-----------------------------------------------------------------------------
# Globals
#-----------------------------------------------------------------------------
configuration = ConfigManager.getConfiguration()
_ = configuration['trans']


#-----------------------------------------------------------------------------
# ClientAuthContextFactory
#-----------------------------------------------------------------------------
class ClientAuthContextFactory(ssl.ClientContextFactory):
    def getContext(self):
        self.method = SSL.SSLv23_METHOD
        ctx = ssl.ClientContextFactory.getContext(self)
        ctx.use_certificate_file(configuration['path'] + '/configuration/ssl/public/websocket.crt')
        ctx.use_privatekey_file(configuration['path'] + '/configuration/ssl/websocket.key')
        return ctx


#-----------------------------------------------------------------------------
# ServerTLSContext
#-----------------------------------------------------------------------------
class WebSocketProtocol(WebSocketServerProtocol):
    def connectionMade(self):
        WebSocketServerProtocol.connectionMade(self)
        self.LisaProtocolfactory = LisaProtocolFactory(self)
        if configuration['enable_secure_mode']:
             self.conn = reactor.connectSSL(configuration['lisa_url'], configuration['lisa_port'], self.LisaProtocolfactory, ClientAuthContextFactory())
        else:
            self.conn = reactor.connectTCP(configuration['lisa_url'], configuration['lisa_port'], self.LisaProtocolfactory)

    def onMessage(self, msg, binary):
        self.LisaProtocolfactory.protocol.sendMessage(json.dumps(
            {"from": "Lisa-Web","type": "chat", "body": unicode(msg.decode('utf-8')), "zone": "Web"}))

    def connectionLost(self, reason):
        self.conn.transport = None


#-----------------------------------------------------------------------------
# ServerTLSContext
#-----------------------------------------------------------------------------
class ServerTLSContext(ssl.ClientContextFactory):
    isClient = 1
    def getContext(self):
        return SSL.Context(SSL.TLSv1_METHOD)


#-----------------------------------------------------------------------------
# LisaProtocol
#-----------------------------------------------------------------------------
class LisaProtocol(LineReceiver):
    def __init__(self, WebSocketProtocol, factory):
        self.WebSocketProtocol = WebSocketProtocol
        self.factory = factory

    def sendMessage(self, msg):
        self.sendLine(msg)

    def lineReceived(self, data):
        self.WebSocketProtocol.sendMessage(data)

    def connectionMade(self):
        if configuration['enable_secure_mode']:
            ctx = ServerTLSContext()
            self.transport.startTLS(ctx, self.factory)

        self.sendMessage(json.dumps({"from": "Lisa-Web", "zone": "Web", "type": "command", "command": "login req"}))


#-----------------------------------------------------------------------------
# LisaProtocolFactory
#-----------------------------------------------------------------------------
class LisaProtocolFactory(ReconnectingClientFactory):
    def __init__(self, WebSocketProtocol):
        self.WebSocketProtocol = WebSocketProtocol

    def startedConnecting(self, connector):
        log.msg('Start connection')

    def buildProtocol(self, addr):
        self.protocol = LisaProtocol(self.WebSocketProtocol, factory=self)
        log.msg('Connected to server')
        self.resetDelay()
        return self.protocol

    def clientConnectionLost(self, connector, reason):
        log.err("Lost connection with server.  Reason : {reason}".format(reason = str(reason)))
        ReconnectingClientFactory.clientConnectionLost(self, connector, reason)

    def clientConnectionFailed(self, connector, reason):
        log.err("Connection failed with server. Reason : {reason}".format(reason = str(reason)))
        self.resetDelay()
        ReconnectingClientFactory.clientConnectionFailed(self, connector, reason)

# --------------------- End of websockets.py  ---------------------
