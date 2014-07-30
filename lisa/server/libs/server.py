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
from twisted.internet import ssl
from twisted.python import log
from OpenSSL import SSL
from lisa.server.libs.txscheduler.manager import ScheduledTaskManager
from lisa.server.libs.txscheduler.service import ScheduledTaskService
from lisa.server.plugins.PluginManager import PluginManagerSingleton
import gettext
from lisa.server.config_manager import ConfigManager
from lisa.server.web.manageplugins.models import Intent, Rule
from lisa.Neotique.NeoDialog import NeoDialog, NeoContext
from lisa.Neotique.NeoTrans import NeoTrans


#-----------------------------------------------------------------------------
# Globals
#-----------------------------------------------------------------------------
configuration = ConfigManager.getConfiguration()
_ = configuration['trans']

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
    """

    #-----------------------------------------------------------------------------
    def __init__(self, factory):
        self.uid = str(uuid.uuid1())
        self.factory = factory
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
            self.transport.startTLS(ctx, self.factory)

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
            self.factory.parseChat(jsonData = jsonData, client_uid = self.client['uid'])
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
        self.client = self.factory.initClient(client_name = client_name, zone_name = zone_name)
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
# LisaProtocolSingleton (used for web interface connection)
#-----------------------------------------------------------------------------
class LisaProtocolSingleton(object):
    """
    Singleton version of the Lisa Protocol.

    Being a singleton, this class should not be initialised explicitly
    and the ``get`` classmethod must be called instead.
    """
    __instance = None

    #-----------------------------------------------------------------------------
    def __init__(self):
        """
        Initialisation: this class should not be initialised
        explicitly and the ``get`` classmethod must be called instead.
        """
        if LisaProtocolSingleton.__instance is not None:
            raise Exception("Singleton can't be created twice !")

    #-----------------------------------------------------------------------------
    def get(self):
        """
        Actually create an instance
        """
        if LisaProtocolSingleton.__instance is None:
            LisaProtocolSingleton.__instance = ClientFactorySingleton.get().buildProtocol(None)

        return LisaProtocolSingleton.__instance
    get = classmethod(get)


#-----------------------------------------------------------------------------
# Unique client factory : builds LisaProtocol for each connection
#-----------------------------------------------------------------------------
class ClientFactory(Factory):
    __lock = threading.RLock()

    #-----------------------------------------------------------------------------
    def __init__(self):
        self.clients = {}
        self.zones = {}
        self.syspath = sys.path
        NeoContext.initPlugins()
        self.Dialog = NeoDialog(factory = self)

    #-----------------------------------------------------------------------------
    def parseChat(self, jsonData, client_uid):
        self.Dialog.parse(jsonData, client_uid)

    #-----------------------------------------------------------------------------
    def stopFactory(self):
        # Clean clients
        for c in self.clients:
            self.clients[c].pop('context')

    #-----------------------------------------------------------------------------
    def buildProtocol(self, addr):
        # Create protocol
        return LisaProtocol(factory = self)

    #-----------------------------------------------------------------------------
    def initClient(self, client_name, zone_name):
        # Lock access
        self.__lock.acquire()

        # Get zone
        zone_uid = self.getZone(zone_name)

        # Search if we already had a connection
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

            # Each client has its own dialog instance
            client['context'] = NeoContext(factory = self, client_uid = client_uid)

            # Add client to zone
            found_flag = False
            for c in self.zones[zone_uid]['client_uids']:
                if c == client['uid']:
                    found_flag = True
                    break
            if found_flag == False:
                self.zones[zone_uid]['client_uids'].append(client['uid'])

        # Release access
        self.__lock.release()

        return client

    #-----------------------------------------------------------------------------
    def getZone(self, zone_name):
        # Lock access
        self.__lock.acquire()

        # Search zone
        zone = None
        zone_uid = None
        for z in self.zones:
            if self.zones[z]['name'] == zone_name:
                zone = self.zones[z]
                zone_uid = z
                break

        # If not found
        if zone is None:
            # Create zone
            zone_uid = str(uuid.uuid1())
            self.zones[zone_uid] = {'name': zone_name, 'client_uids': []}
            zone = self.zones[zone_uid]

        # Release access
        self.__lock.release()

        return zone_uid

    #-----------------------------------------------------------------------------
    def sendToClients(self, jsonData, client_uids = [], zone_uids = []):
        # Parse clients
        for c in self.clients:
            # If client is in destination
            if 'all' in zone_uids or self.clients[c]['zone_uid'] in zone_uids or 'all' in client_uids or c in client_uids:
                # Parse client protocols
                for p in self.clients[c]['protocols']:
                    # Send to client through protocol
                    self.clients[c]['protocols'][p]['object'].sendToClient(jsonData)

    #-----------------------------------------------------------------------------
    def LisaReload(self):
        global enabled_plugins

        log.msg("Reloading engine")
        sys.path = self.syspath
        enabled_plugins = []
        self.build_activeplugins()

    #-----------------------------------------------------------------------------
    def SchedReload(self):
        global taskman
        log.msg("Reloading task scheduler")
        self.taskman = taskman
        return self.taskman.reload()


#-----------------------------------------------------------------------------
# ClientFactorySingleton
#-----------------------------------------------------------------------------
class ClientFactorySingleton(object):
    """
    Singleton version of the Lisa Factory.

    Being a singleton, this class should not be initialised explicitly
    and the ``get`` classmethod must be called instead.
    """

    __instance = None

    #-----------------------------------------------------------------------------
    def __init__(self):
        """
        Initialisation: this class should not be initialised
        explicitly and the ``get`` classmethod must be called instead.
        """
        if self.__instance is not None:
            raise Exception("Singleton can't be created twice !")

    #-----------------------------------------------------------------------------
    def get(self):
        """
        Actually create an instance
        """
        if self.__instance is None:
            self.__instance = ClientFactory()
            log.msg("ClientFactory initialised")
        return self.__instance
    get = classmethod(get)


# Load the plugins
#PluginManagerSingleton.get().loadPlugins()

# Create an instance of factory, then create a protocol instance to import it everywhere
#ClientFactorySingleton.get()
#LisaProtocolSingleton.get()

def Initialize():
    # Create the default core_intents_list intent
    defaults_intent_list = {'name': "core_intents_list",
                     'function': "list",
                     'module': "lisa.server.core.intents.Intents",
                     'enabled': True
    }
    intent_list, created = Intent.objects.get_or_create(name='core_intents_list', defaults=defaults_intent_list)

    # Create the default rule of the rule engine
    defaults_rule = {'name': "DefaultAnwser",
                     'order': 999,
                     'before': None,
                     'after': """lisaprotocol.sendToClient(json.dumps(
                                                {
                                                    'plugin': jsonOutput['plugin'],
                                                    'method': jsonOutput['method'],
                                                    'body': jsonOutput['body'],
                                                    'clients_zone': ['sender'],
                                                    'from': jsonOutput['from']
                                                }))""",
                     'end': True,
                     'enabled': True
    }
    default_rule, created = Rule.objects.get_or_create(name='DefaultAnwser', defaults=defaults_rule)
