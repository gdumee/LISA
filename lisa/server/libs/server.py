# -*- coding: UTF-8 -*-
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
from lisa.server.ConfigManager import ConfigManagerSingleton
from lisa.server.web.manageplugins.models import Intent, Rule
from lisa.Neotique.NeoDialog import NeoDialog

# Create a task manager to pass it to other services

configuration_server = ConfigManagerSingleton.get().getConfiguration()
dir_path = ConfigManagerSingleton.get().getPath()
path = '/'.join([ConfigManagerSingleton.get().getPath(), 'lang'])
_ = translation = gettext.translation(domain='lisa', localedir=path, fallback=True,
                                              languages=[configuration_server['lang']]).ugettext

taskman = ScheduledTaskManager(configuration_server)
scheduler = ScheduledTaskService(taskman)


class ServerTLSContext(ssl.DefaultOpenSSLContextFactory):
    def __init__(self, *args, **kw):
        kw['sslmethod'] = SSL.TLSv1_METHOD
        ssl.DefaultOpenSSLContextFactory.__init__(self, *args, **kw)


#-----------------------------------------------------------------------------
# LisaProtocol : built by factory on every client connection
#-----------------------------------------------------------------------------
class LisaProtocol(LineReceiver):
    #-----------------------------------------------------------------------------
    def __init__(self, factory, client_uid):
        self.uid = str(uuid.uuid1())
        self.factory = factory
        self.client = factory.clients[client_uid]
        
    #-----------------------------------------------------------------------------
    def connectionMade(self):
        log.msg(_("New connection with client {name} in zone {zone}".format(name = self.client['name'], zone = self.client['zone'])))

        # Add protocol to client
        self.client['protocols'][self.uid] = {'object': self}

        # TLS connection
        if configuration_server['enable_secure_mode']:
            ctx = ServerTLSContext(
                privateKeyFileName=os.path.normpath(dir_path + '/' + 'configuration/ssl/server.key'),
                certificateFileName= os.path.normpath(dir_path + '/' + 'configuration/ssl/server.crt')
            )
            self.transport.startTLS(ctx, self.factory)
            pass
        
    #-----------------------------------------------------------------------------
    def connectionLost(self, reason):
        log.err(_("Lost connection with client {name} in zone {zone}.  Reason: {reason}".format(name = self.client['name'], zone = self.client['zone'], reason = str(reason))))

        # Remove protocol from client
        self.client['protocols'].pop(self.uid)

    #-----------------------------------------------------------------------------
    def lineReceived(self, data):
        # Debug
        if configuration_server['debug']['debug_output']:
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
            self.sendError(_("Error : Unknwon input format"))
            return

        # Read type
        if jsonData['type'] == "chat":
            self.client['dialog'].parse(jsonData = jsonData)
        elif jsonData['type'] == "command" and jsonData.has_key('command') == True:
            # Select command
            if jsonData['command'].lower() == 'login req':
                # Get name and zone
                self.client['name'] = jsonData['from']
                self.client['zone'] = jsonData['zone']
                self.client['zone_uid'] = self.factory.getZone(zone_name = jsonData['zone'], client = self.client)

                # Send login ack
                jsonOut = {'type': 'command', 'command': 'login ack', 'bot_name': configuration_server['bot_name']}
                self.sendToClient(jsonOut)
            else:
                self.sendError(_("Error : Unknwon command type {command}").format(type = jsonData['command']))
        else:
            self.sendError(_("Error : Unknwon input type {type}").format(type = jsonData['type']))

    #-----------------------------------------------------------------------------
    def sendError(self, msg):
        log.err(msg)
        jsonData = {'type': 'Error', 'message': msg}
        self.sendToClient(jsonData)

    #-----------------------------------------------------------------------------
    def sendToClient(self, jsonData):
        # Add info to data
        jsonData['from'] = 'Server'
        jsonData['to'] = self.client['name']
        jsonData['zone'] = self.client['zone']

        # Debug
        if configuration_server['debug']['debug_output']:
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

        if self.__instance is not None:
            raise Exception("Singleton can't be created twice !")

    #-----------------------------------------------------------------------------
    def get(self):
        """
        Actually create an instance
        """
        if self.__instance is None:
            self.__instance = LisaFactorySingleton.get().buildProtocol("web_interface")
        return self.__instance
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

    #-----------------------------------------------------------------------------
    def stopFactory(self):
        # Clean clients
        for c in self.clients:
            self.clients[c].pop('dialog')
            self.clients[c].pop('context')

    #-----------------------------------------------------------------------------
    def buildProtocol(self, addr):
        # Lock access
        self.__lock.acquire()
        
        # Search if we already had a connection
        client = None
        client_uid = None
        for c in self.clients:
            if self.clients[c]['addr'] == addr:
                client = self.clients[c]
                client_uid = c
                break
        
        # If not found
        if client is None:
            # Add client
            client_uid = str(uuid.uuid1())
            self.clients[client_uid] = {'uid': client_uid, 'addr': addr, 'protocols': {}, 'name': "uninitialized", 'zone': "uninitialized", 'zone_uid': None}
            client = self.clients[client_uid]
            
            # Each client has its own dialog instance
            client['dialog'] = NeoDialog(factory = self, client_uid = client_uid)

        # Create protocol
        p = LisaProtocol(factory = self, client_uid = client_uid)
            
        # Release access
        self.__lock.release()

        return p

    #-----------------------------------------------------------------------------
    def getZone(self, zone_name, client):
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
            # Add client
            zone_uid = str(uuid.uuid1())
            self.zones[zone_uid] = {'name': zone_name, 'client_uids': []}
            zone = self.zones[zone_uid]

        # Add client to zone
        found_flag = False
        for c in zone['client_uids']:
            if c == client['uid']:
                found_flag = True
                break
        if found_flag == False:
            zone['client_uids'].append(client['uid'])

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

        log.msg(_('Reloading L.I.S.A Engine'))
        sys.path = self.syspath
        enabled_plugins = []
        self.build_activeplugins()

    #-----------------------------------------------------------------------------
    def SchedReload(self):
        global taskman
        log.msg(_("Reloading Task Scheduler"))
        self.taskman = taskman
        return self.taskman.reload()


# TODO rename to ClientFactorySingleton
#-----------------------------------------------------------------------------
# LisaFactorySingleton
#-----------------------------------------------------------------------------
class LisaFactorySingleton(object):
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


# Create an instance of factory, then create a protocol instance to import it everywhere
LisaFactorySingleton.get()
LisaProtocolSingleton.get()

# Load the plugins
PluginManagerSingleton.get().loadPlugins()

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
