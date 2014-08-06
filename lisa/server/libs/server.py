# -*- coding: UTF-8 -*-
#-----------------------------------------------------------------------------
# project     : Lisa server
# module      : server
# file        : server.py
# description : Lisa server protocol management
# author      : G.Dumee
#-----------------------------------------------------------------------------
# copyright   : Neotique
#-----------------------------------------------------------------------------


#-----------------------------------------------------------------------------
# Imports
#-----------------------------------------------------------------------------
import os, json, sys, uuid, threading
from twisted.internet.protocol import Factory
from twisted.protocols.basic import LineReceiver
from twisted.python import log
from twisted.internet import ssl
from OpenSSL import SSL
from lisa.server.libs.txscheduler.manager import ScheduledTaskManager
from lisa.server.libs.txscheduler.service import ScheduledTaskService
from lisa.server.plugins.PluginManager import PluginManager
from lisa.server.config_manager import ConfigManager
from NeoDialog import NeoContext
from wit import Wit


#-----------------------------------------------------------------------------
# Globals
#-----------------------------------------------------------------------------
configuration = ConfigManager.getConfiguration()
_ = configuration['trans']

#TODO what is that
taskman = ScheduledTaskManager(configuration)
scheduler = ScheduledTaskService(taskman)


#-----------------------------------------------------------------------------
# ServerTLSContext
#-----------------------------------------------------------------------------
class ServerTLSContext(ssl.DefaultOpenSSLContextFactory):
    def __init__(self, *args, **kw):
        kw['sslmethod'] = SSL.TLSv1_METHOD
        ssl.DefaultOpenSSLContextFactory.__init__(self, *args, **kw)


#-----------------------------------------------------------------------------
# LisaProtocol : built by factory on every client connection
#-----------------------------------------------------------------------------
class LisaProtocol(LineReceiver):
    """
    TCP server/client Protocol
    """

    #-----------------------------------------------------------------------------
    def __init__(self):
        self.uid = str(uuid.uuid1())
        self.client = None

    #-----------------------------------------------------------------------------
    def connectionMade(self):
        log.msg("New connection from a client")

        # TLS connection
        if configuration['enable_secure_mode']:
            ctx = ServerTLSContext(
                privateKeyFileName = configuration['lisa_ssl_key'],
                certificateFileName = configuration['lisa_ssl_crt']
            )
            self.transport.startTLS(ctx, ClientFactory.get())

    #-----------------------------------------------------------------------------
    def connectionLost(self, reason):
        # Remove protocol from client
        if self.client is not None:
            log.err("Lost connection with client {name} in zone {zone} with reason : {reason}".format(name = self.client['name'], zone = self.client['zone'], reason = str(reason)))
            self.client['protocols'].pop(self.uid)
        else:
            log.err("Lost connection with unlogged client")

    #-----------------------------------------------------------------------------
    def lineReceived(self, data):
        # Debug
        if self.client is not None and configuration['debug']['debug_output']:
            log.msg("INPUT from {name} in zone {zone} : {data}".format(name = self.client['name'], zone = self.client['zone'], data = str(data)))

        # Try to get Json
        jsonData = {}
        try:
            jsonData = json.loads(data)
        except ValueError, e:
            self.sendError(_("Error : Invalid JSON") + " : " + str(e))
            return

        # Check format
        if jsonData.has_key('type') == False:
            self.sendError(_("Error : no type in input JSON"))
            return

        # Read type
        if self.client is not None and jsonData['type'] == "chat":
            ClientFactory.parseChat(jsonData = jsonData, client_uid = self.client['uid'])
        elif jsonData['type'] == "command" and jsonData.has_key('command') == True:
            # Select command
            if jsonData['command'].lower() == 'login req':
                # Init client
                self.initClient(client_name = jsonData['from'], zone_name = jsonData['zone'])

                # Debug
                if configuration['debug']['debug_output']:
                    log.msg("INPUT from {name} in zone {zone} : {data}".format(name = self.client['name'], zone = self.client['zone'], data = str(data)))

                # Send login ack
                jsonOut = {'type': 'command', 'command': 'login ack', 'bot_name': configuration['bot_name']}
                self.sendToClient(jsonOut)
            else:
                self.sendError(_("Error : Unknwon command type {command}").format(command = jsonData['command']))
        else:
            self.sendError(_("Error : Unknwon input type {type}").format(type = jsonData['type']))

    #-----------------------------------------------------------------------------
    def initClient(self, client_name, zone_name):
        # Get client
        self.client = ClientFactory.initClient(client_name = client_name, zone_name = zone_name)
        self.client['protocols'][self.uid] = {'object': self}

    #-----------------------------------------------------------------------------
    def sendError(self, msg):
        log.err(msg)
        jsonData = {'type': 'Error', 'message': msg}
        self.sendToClient(jsonData)

    #-----------------------------------------------------------------------------
    def sendToClient(self, jsonData):
        # If no client logged in
        if self.client is None:
            return

        # Add info to data
        jsonData['from'] = 'Server'
        jsonData['to'] = self.client['name']
        jsonData['zone'] = self.client['zone']

        # Debug
        if configuration['debug']['debug_output']:
            log.msg("OUTPUT to {name} in zone {zone} : {data}".format(name = self.client['name'], zone = self.client['zone'], data = str(jsonData)))

        # Send message
        self.sendLine(json.dumps(jsonData))


#-----------------------------------------------------------------------------
# Unique client factory : builds LisaProtocol for each connection
#-----------------------------------------------------------------------------
class ClientFactory(Factory):
    # Singleton instance
    __instance = None

    #-----------------------------------------------------------------------------
    def __init__(self):
        # Check Singleton
        if ClientFactory.__instance is not None:
            raise Exception("Singleton can't be created twice !")

        # Variables init
        self.clients = {}
        self.zones = {}
        self._lock = threading.RLock()
        self.wit = None

    #-----------------------------------------------------------------------------
    def startFactory(self):
        # Init global contexts
        NeoContext.init(factory = self)

        # Init Wit
        self.wit = Wit(configuration['wit_token'])

    #-----------------------------------------------------------------------------
    def buildProtocol(self, addr):
        # Create protocol
        return LisaProtocol()

    #-----------------------------------------------------------------------------
    def stopFactory(self):
        # Clean
        if ClientFactory.__instance is not None:
            ClientFactory.__instance.clients = {}
            ClientFactory.__instance.zones = {}
            ClientFactory.__instance.wit = None
            ClientFactory.__instance = None

        # Clear global contexts
        NeoContext.deinit()

    #-----------------------------------------------------------------------------
    @classmethod
    def initClient(cls, client_name, zone_name):
        # Create singleton
        if cls.__instance is None:
            cls.__instance = ClientFactory()
        self = cls.__instance

        # Lock access
        self._lock.acquire()

        # Get zone
        zone_uid = cls.getOrCreateZone(zone_name)

        # Search if we already had a connection with this client
        client = None
        client_uid = None
        for c in self.clients:
            if self.clients[c]['name'] == client_name and self.clients[c]['zone'] == zone_name:
                return self.clients[c]

        # If not found
        if client is None:
            # Add client
            client_uid = str(uuid.uuid1())
            self.clients[client_uid] = {'uid': client_uid, 'protocols': {}, 'name': client_name, 'zone': zone_name, 'zone_uid': zone_uid}
            client = self.clients[client_uid]

            # Each client has its own context
            client['context'] = NeoContext(client_uid = client_uid)

            # Add client to zone
            found_flag = False
            for c in self.zones[zone_uid]['client_uids']:
                if c == client['uid']:
                    found_flag = True
                    break
            if found_flag == False:
                self.zones[zone_uid]['client_uids'].append(client['uid'])

        # Release access
        self._lock.release()

        return client

    #-----------------------------------------------------------------------------
    @classmethod
    def parseChat(cls, jsonData, client_uid):
        # Create singleton
        if cls.__instance is None:
            cls.__instance = ClientFactory()
        self = cls.__instance

        # If input has already a decoded intent
        if jsonData.has_key("outcome") == True:
            jsonInput = {}
            jsonInput['outcome'] = jsonData['outcome']
        elif len(jsonData['body']) > 0:
            # Ask Wit for intent decoding
            jsonInput = self.wit.get_message(unicode(jsonData['body']))
        else:
            # No input => no output
            return

        # Initialize output from input
        jsonInput['from'], jsonInput['type'], jsonInput['zone'] = jsonData['from'], jsonData['type'], jsonData['zone']

        # Show wit result
        if configuration['debug']['debug_wit']:
            log.msg("WIT: " + str(jsonInput['outcome']))

        # Execute intent
        client = cls.getClient(client_uid)
        intent = PluginManager.getIntent(intent_name = jsonInput['outcome']['intent'])
        if intent is not None:
            # Call plugin
            client['context'].parse(jsonInput = jsonInput, plugin_name = intent.plugin_name, method_name = intent.method_name)
        else:
            # Parse without intent
            client['context'].parse(jsonInput = jsonInput)

    #-----------------------------------------------------------------------------
    @classmethod
    def getClient(cls, client_uid):
        # Get singleton
        if cls.__instance is None:
            return None

        # Return client
        return cls.__instance.clients[client_uid]

    #-----------------------------------------------------------------------------
    @classmethod
    def getOrCreateZone(cls, zone_name):
        # Create singleton
        if cls.__instance is None:
            cls.__instance = ClientFactory()

        # All zones
        if zone_name == "all":
            return "all"

        # Lock access
        cls.__instance._lock.acquire()

        # Search zone
        zone = None
        zone_uid = None
        for z in cls.__instance.zones:
            if cls.__instance.zones[z]['name'] == zone_name:
                zone = cls.__instance.zones[z]
                zone_uid = z
                break

        # If not found
        if zone is None:
            # Create zone
            zone_uid = str(uuid.uuid1())
            cls.__instance.zones[zone_uid] = {'name': zone_name, 'client_uids': []}
            zone = cls.__instance.zones[zone_uid]

        # Release access
        cls.__instance._lock.release()

        return zone_uid

    #-----------------------------------------------------------------------------
    @classmethod
    def sendToClients(cls, jsonData, client_uids = [], zone_uids = []):
        # Create singleton
        if cls.__instance is None:
            cls.__instance = ClientFactory()

        # Parse clients
        for c in cls.__instance.clients:
            # If client is in destination
            if "all" in zone_uids or cls.__instance.clients[c]['zone_uid'] in zone_uids or "all" in client_uids or c in client_uids:
                # Parse client protocols
                for p in cls.__instance.clients[c]['protocols']:
                    # Send to client through protocol
                    cls.__instance.clients[c]['protocols'][p]['object'].sendToClient(jsonData)

    #-----------------------------------------------------------------------------
    @classmethod
    def LisaReload(cls):
        # Create singleton
        if cls.__instance is None:
            cls.__instance = ClientFactory()

        log.msg("Reloading engine")
        cls.__instance.build_activeplugins()

    #-----------------------------------------------------------------------------
    @classmethod
    def SchedReload(cls):
        global taskman
        # Create singleton
        if cls.__instance is None:
            cls.__instance = ClientFactory()

        log.msg("Reloading task scheduler")
        cls.__instance.taskman = taskman
        return cls.__instance.taskman.reload()

    #-----------------------------------------------------------------------------
    @classmethod
    def get(cls):
        # Create singleton
        if cls.__instance is None:
            cls.__instance = ClientFactory()
        return cls.__instance

# --------------------- End of server.py  ---------------------
