# -*- coding: UTF-8 -*-
#-----------------------------------------------------------------------------
# project     : Lisa server
# module      : libs
# file        : NeoDialog.py
# description : Manage dialog with clients in the plugins
# author      : G.Dumee
#-----------------------------------------------------------------------------
# copyright   : Neotique
#-----------------------------------------------------------------------------


#-----------------------------------------------------------------------------
# Imports
#-----------------------------------------------------------------------------
import lisa.plugins, json, uuid, threading, os, inspect
from datetime import datetime
from twisted.python import log
from lisa.Neotique.NeoTimer import NeoTimer
from lisa.server.config_manager import ConfigManager
from lisa.server.plugins.PluginManager import PluginManager


#-----------------------------------------------------------------------------
# Globals
#-----------------------------------------------------------------------------
configuration_server = ConfigManager.getConfiguration()
_ = configuration_server['trans']


#-----------------------------------------------------------------------------
# NeoContext
#-----------------------------------------------------------------------------
class NeoContext():
    # Global context
    __lock = threading.RLock()
    __global_ctx = {}
    __history = {}
    __steps = {'count': 0, 'first': None, 'last': None}
    __Vars = {}
    __factory = None

    #-----------------------------------------------------------------------------
    def __init__(self, client_uid):
        # Client context
        self.client = NeoContext.__factory.getClient(client_uid)
        self.wait_step = None
        self._client_steps = {'count': 0, 'first': None, 'last': None}
        self.Vars = {}

        # Init plugins client variables
        PluginManager.initContext(context = self)

    #-----------------------------------------------------------------------------
    def parse(self, jsonInput, plugin_name = None, method_name = None):
        # If waiting an answer
        if self._process_answer(jsonInput) == True:
            # The answer was processed
            return

        # Check Wit confidence
        if jsonInput['outcome'].has_key('confidence') == False or jsonInput['outcome']['confidence'] < configuration_server['wit_confidence']:
            # Add an error step
            step = NeoContext._create_step(context = self)
            step['type'] = "error confidence"
            step['in_json'] = jsonInput.copy()

            # Return an error to client
            jsonData = {'type': 'Error', 'message': _("error_intent_low_confidence")}
            NeoContext.__factory.sendToClients(client_uids = [self.client['uid']], jsonData = jsonData)
            return

        # Get initialized plugin
        plugin = PluginManager.getPlugin(plugin_name = plugin_name)
        if plugin is None:
            # Add an error step
            step = NeoContext._create_step(context = self)
            step['type'] = "Error no plugin"
            step['in_json'] = jsonInput.copy()

            # Return an error to client
            jsonData = {'type': 'Error', 'message': _("error_intent_unknown")}
            NeoContext.__factory.sendToClients(client_uids = [self.client['uid']], jsonData = jsonData)
            return

        # Get method to call
        methodToCall = PluginManager.getPluginMethod(plugin = plugin, method_name = method_name)
        if methodToCall is None:
            # Add an error step
            step = NeoContext._create_step(plugin_uid = plugin.uid, context = self)
            step['type'] = "Error plugin no method"
            step['plugin_name'] = plugin_name
            step['method_name'] = method_name
            step['in_json'] = jsonInput.copy()

            # Return an error to client
            jsonData = {'type': 'Error', 'message': _("error_plugin_no_func")}
            NeoContext.__factory.sendToClients(client_uids = [self.client['uid']], jsonData = jsonData)
            return

        # Save step in context
        step = NeoContext._create_step(plugin_uid = plugin.uid, context = self)
        step['type'] = "Plugin call"
        step['in_json'] = jsonInput.copy()

        # Call plugin method
        jsonInput['context'] = self
        try:
            jsonOutput = methodToCall(jsonInput)
        except:
            # In debug mode, raise exception
            if configuration_server['debug']['debug_plugin'] == True:
                raise

            # Add an error step
            step = NeoContext._create_step(context = self)
            step['type'] = "error plugin exec"
            step['plugin_name'] = plugin_name
            step['method_name'] = method_name
            step['in_json'] = jsonInput.copy()

            # Return an error to client
            jsonData = {'type': 'Error', 'message': _("error_plugin_exec")}
            NeoContext.__factory.sendToClients(client_uids = [self.client['uid']], jsonData = jsonData)
            return

        # Old-style plugin output
        if jsonOutput is not None:
            self.speakToClient(plugin_uid = plugin.uid, text = jsonOutput['body'])

    #-----------------------------------------------------------------------------
    def speakToClient(self, plugin_uid, text, client_uids = None, zone_uids = None):
        """
        Speak to the client

        plugin_uid : uid of the plugin calling the API
        text : speech for user
        context : current dialog context, can be None for global notification to user (associated with no context)
        client_uids : optional list of destination clients, use clients uids
        zone_uids : optional list of destination zones, use zone uids

        To answer a client, do net set client_uids and zone_uids
        To send to everyone : client_uids = ['all'] or zone_uids = ['all']
        """
        # Call global API
        NeoContext.globalSpeakToClient(context = self, text = text, plugin_uid = plugin_uid, client_uids = client_uids, zone_uids = zone_uids)

    #-----------------------------------------------------------------------------
    def askClient(self, plugin_uid, text, answer_cbk, wit_context = None, client_uids = None, zone_uids = None):
        """
        Ask a question, and wait for an answer

        plugin_uid : uid of the plugin calling the API
        text : question for user
        wit_context : optional json sent to Wit as context input (ex : Wit states)
        client_uids : optional list of destination clients, use clients uids
        zone_uids : optional list of destination zones, use zone uids
        answer_cbk : function called on answer

        To answer a client, do net set client_uids and zone_uids
        To send to everyone : client_uids = ['all'] or zone_uids = ['all']

        The callback prototype is : def answer_cbk(self, context, jsonAnswer)
            context : identical to context given here
            jsonAnswer : json received from the client (!!may have no intent!!), None when no answer is received after a timeout
        """
        # Call global API
        NeoContext.globalAskToClient(context = self, text = text, answer_cbk = answer_cbk, plugin_uid = plugin_uid, wit_context = wit_context, client_uids = client_uids, zone_uids = zone_uids)

    #-----------------------------------------------------------------------------
    @classmethod
    def globalSpeakToClient(cls, text, plugin_uid = None, context = None, client_uids = None, zone_uids = None):
        # Check params
        if client_uids is None:
            client_uids = []
        if zone_uids is None:
            zone_uids = []

        # If no destination
        if context is not None and len(client_uids) == 0 and len(zone_uids) == 0:
            # Add current client as destination
            client_uids.append(context.client['uid'])

        # Add a step
        step = NeoContext._create_step(plugin_uid = plugin_uid, context = context)
        step['type'] = "Plugin speech"
        step['message'] = text

        # Send to client
        jsonData = {}
        jsonData['type'] = 'chat'
        jsonData['message'] = text
        cls.__factory.sendToClients(client_uids = client_uids, zone_uids = zone_uids, jsonData = jsonData)

    #-----------------------------------------------------------------------------
    @classmethod
    def globalAskToClient(cls, text, answer_cbk, plugin_uid = None, context = None, wit_context = None, client_uids = None, zone_uids = None):
        # Check params
        if client_uids is None:
            client_uids = []
        if zone_uids is None:
            zone_uids = []

        # If no destination
        if context is not None and len(client_uids) == 0 and len(zone_uids) == 0:
            # Add current client as destination
            client_uids.append(context.client['uid'])

        # Add a step
        step = NeoContext._create_step(plugin_uid = plugin_uid, context = context)
        step['type'] = "Plugin question"
        step['message'] = text
        step['clients'] = client_uids
        step['zones'] = zone_uids
        if wit_context is not None:
            step['wit_context'] = wit_context

        # Lock access
        NeoContext.__lock.acquire()

        # TODO : don't work, no global step, no global wait step
        if context is not None:
            # If there is a current question, end it without answer
            context._process_answer()

            # Set waiting state
            step['answer_cbk'] = answer_cbk
            step['wait_timer'] = NeoTimer(duration_s = 20, user_cbk = context._timer_cbk, user_param = None)
            context.wait_step = step

        # Release access
        NeoContext.__lock.release()

        # Send to client
        jsonData = {}
        jsonData['type'] = 'command'
        jsonData['command'] = 'ask'
        jsonData['message'] = text
        if wit_context is not None:
            jsonData['wit_context'] = wit_context
        print client_uids, zone_uids, jsonData
        NeoContext.__factory.sendToClients(client_uids = client_uids, zone_uids = zone_uids, jsonData = jsonData)

    #-----------------------------------------------------------------------------
    def _timer_cbk(self, param):
        """
        Internal timer callback
        """
        # No answer timeout
        self._process_answer()

    #-----------------------------------------------------------------------------
    def _process_answer(self, jsonAnswer = None):
        # Lock access
        NeoContext.__lock.acquire()

        # Answer may arrive simultaneously
        if self.wait_step is None:
            # Release access
            NeoContext.__lock.release()
            return False

        # Keep step locally
        step = self.wait_step
        self.wait_step = None

        # Stop timer
        step['wait_timer'].stop()
        step.pop('wait_timer')

        # Add a step
        new_step = NeoContext._create_step(plugin_uid = step['plugin_uid'], context = self)
        new_step['type'] = "Answer"
        new_step['question_step'] = step['uid']
        step['answer_step'] = new_step

        # Release access
        NeoContext.__lock.release()

        # If there is an answer
        if jsonAnswer is not None:
            new_step['json'] = jsonAnswer.copy()
            jsonAnswer['context'] = self

        # Callback caller without answer
        step['answer_cbk'](context = self, jsonAnswer = jsonAnswer)

        # Clear step
        step.pop('answer_cbk')

        # Change client mode
        jsonData = {}
        jsonData['type'] = 'command'
        jsonData['command'] = 'kws'
        NeoContext.__factory.sendToClients(client_uids = step['clients'], zone_uids = step['zones'], jsonData = jsonData)
        return True

    #-----------------------------------------------------------------------------
    @classmethod
    def _create_step(cls, plugin_uid = None, context = None):
        # Lock access
        NeoContext.__lock.acquire()

        # Create a step
        step_uid = str(uuid.uuid1())
        step = {'uid': step_uid, 'date': datetime.now(), 'previous': None, 'next': None, 'client_uid': None, 'client_previous': None, 'client_next': None, 'plugin_uid': plugin_uid, 'plugin_previous': None, 'plugin_next': None}
        cls.__history[step_uid] = step

        # First step
        cls.__steps['count'] += 1
        if cls.__steps['first'] is None:
            cls.__steps['first'] = step_uid

        # Link to last step
        if cls.__steps['last'] is not None:
            cls.__history[cls.__steps['last']]['next'] = step_uid
            step['previous'] = cls.__history[cls.__steps['last']]['uid']
        cls.__steps['last'] = step_uid

        # link to a client
        if context is not None:
            # Set client uid
            step['client_uid'] = context.client['uid']

            # First client step
            context._client_steps['count'] += 1
            if context._client_steps['first'] is None:
                context._client_steps['first'] = step_uid

            # Link to client last step
            if context._client_steps['last'] is not None:
                cls.__history[context._client_steps['last']]['client_next'] = step_uid
                step['client_previous'] = cls.__history[context._client_steps['last']]['uid']
            context._client_steps['last'] = step_uid

        # link to a plugin
        if plugin_uid is not None:
            # First plugin step
            plugin = PluginManager.getPlugin(plugin_uid = plugin_uid)
            plugin.steps['count'] += 1
            if plugin.steps['first'] is None:
                plugin.steps['first'] = step_uid

            # Link to plugin last step
            if plugin.steps['last'] is not None:
                cls.__history[plugin.steps['last']]['plugin_next'] = step_uid
                step['plugin_previous'] = cls.__history[plugin.steps['last']]['uid']
            plugin.steps['last'] = step_uid

        # Release access
        cls.__lock.release()

        return step

    #-----------------------------------------------------------------------------
    def createClientVar(self, name, default = None):
        # If var doesn't exists
        if self.Vars.has_key(name) == False:
            # Add client variable
            self.Vars[name] = default
        # If property doesn't exist
        if hasattr(self, name) == False:
            # Create local fget and fset functions
            fget = lambda self: self._getClientVar(name)
            fset = lambda self, value: self._setClientVar(name, value)

            # Add property to class
            setattr(self.__class__, name, property(fget, fset))

    #-----------------------------------------------------------------------------
    def _setClientVar(self, name, value):
        self.Vars[name] = value

    #-----------------------------------------------------------------------------
    def _getClientVar(self, name):
        return self.Vars[name]

    #-----------------------------------------------------------------------------
    @classmethod
    def logSteps(cls):
        # TODO add debug tool that use this function
        # Lock access
        cls.__lock.acquire()

        uid = cls.__steps['first']
        while uid is not None:
            print cls.__history[uid]
            uid = cls.__history[uid]['next']

        # Release access
        cls.__lock.release()

    #-----------------------------------------------------------------------------
    @classmethod
    def init(cls, factory):
        # Set factory
        cls.__factory = factory

        # Init plugin manager
        PluginManager.init(global_context = cls)

    #-----------------------------------------------------------------------------
    @classmethod
    def deinit(cls):
        # Lock access
        cls.__lock.acquire()

        # Clean global vars
        cls.__global_ctx = None
        cls.__history = None
        cls.__steps = None
        cls.__Vars = None
        cls._ = None
        cls.__factory = None

        # Deinit plugin manager
        PluginManager.deinit()

        # Release access
        cls.__lock.release()

    #-----------------------------------------------------------------------------
    @classmethod
    def createGlobalVar(cls, name, default = None):
        # If var doesn't exists
        if cls.__Vars.has_key(name) == False:
            # Add client variable
            cls.__Vars[name] = default

        # If property doesn't exist in class
        if hasattr(cls, name) == False:
            # Create local fget and fset functions
            fget = lambda cls: cls._getGlobalVar(name)
            fset = lambda cls, value: cls._setGlobalVar(name, value)

            # Add property to class
            setattr(cls, name, property(fget, fset))

    #-----------------------------------------------------------------------------
    @classmethod
    def _setGlobalVar(cls, name, value):
        cls.__Vars[name] = value

    #-----------------------------------------------------------------------------
    @classmethod
    def _getGlobalVar(cls, name):
        return cls.__Vars[name]

# --------------------- End of NeoDialog.py  ---------------------
