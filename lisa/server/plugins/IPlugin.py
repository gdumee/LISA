# -*- coding: UTF-8 -*-
#-----------------------------------------------------------------------------
# project     : Lisa server
# module      : plugins
# file        : IPlugin.py
# description : Mother class of all plugins
# author      : G.Dumee
#-----------------------------------------------------------------------------
# copyright   : Neotique
#-----------------------------------------------------------------------------


#-----------------------------------------------------------------------------
# Imports
#-----------------------------------------------------------------------------
import inspect, os
from pymongo import MongoClient
from lisa.server.config_manager import ConfigManager
from lisa.server.plugins.PluginManager import PluginManager
from lisa.server.libs.NeoDialog import NeoContext
from lisa.Neotique.NeoTrans import NeoTrans


#-----------------------------------------------------------------------------
# IPlugin
#-----------------------------------------------------------------------------
class IPlugin(object):
    """
    The most simple interface to be inherited when creating a plugin.
    """

    #-----------------------------------------------------------------------------
    def __init__(self, plugin_name = None):
        """
        Set the basic variables.
        """
        # UID will be set by PluginManager just after constructor
        self.uid = None

        # Server configuration
        self.configuration_server = ConfigManager.getConfiguration()

        # New-style plugins give their name to initiate services
        if plugin_name is not None:
            # Read configuration
            self.plugin = PluginManager.getPlugin(plugin_name = plugin_name)
            self.configuration_plugin = self.plugin.configuration

            # Init translation function
            lang_path = self.plugin.path + '/lang'
            self._ = NeoTrans(domain = plugin_name.lower(), localedir = lang_path, fallback = True, languages = [self.configuration_server['lang_short']]).Trans
        # Old-style plugins
        else:
            # Open database
            self.mongo = MongoClient(host = self.configuration_server['database']['server'], port = self.configuration_server['database']['port'])
            self.configuration_lisa = self.configuration_server
            self.configuration_lisa['lang'] = self.configuration_lisa['lang_short']

    #-----------------------------------------------------------------------------
    def speakToClient(self, text, context = None, client_uids = None, zone_uids = None):
        """
        Speak to the client

        text : speech for user
        context : current dialog context, can be None for global notification to user (associated with no context)
        client_uids : optional list of destination clients, use clients uids
        zone_uids : optional list of destination zones, use zone uids

        To answer a client, do net set client_uids and zone_uids
        To send to everyone : client_uids = ['all'] or zone_uids = ['all']
        """
        # if no context
        if context is None:
            NeoContext.globalSpeakToClient(text = text, plugin_uid = self.uid, client_uids = client_uids, zone_uids = zone_uids)
            return

        # Update context
        context.speakToClient(plugin_uid = self.uid, text = text, client_uids = client_uids, zone_uids = zone_uids)

    #-----------------------------------------------------------------------------
    def askClient(self, text, answer_cbk, context = None, wit_context = None, client_uids = None, zone_uids = None):
        """
        Ask a question, and wait for an answer

        text : question for user
        context : current dialog context, can be None for global notification to user (associated with no context)
        client_uids : optional list of destination clients, use clients uids
        zone_uids : optional list of destination zones, use zone uids
        answer_cbk : function called on answer

        To answer a client, do net set client_uids and zone_uids
        To send to everyone : client_uids = ['all'] or zone_uids = ['all']

        The callback prototype is : def answer_cbk(self, context, jsonAnswer)
            context : identical to context given here
            jsonAnswer : json received from the client (!!may have no intent!!), None when no answer is received after a timeout
        """
        # if no context
        if context is None:
            NeoContext.globalAskClient(text = text, plugin_uid = self.uid, wit_context = wit_context, answer_cbk = answer_cbk, client_uids = client_uids, zone_uids = zone_uids)
            return

        # Update context
        context.askClient(plugin_uid = self.uid, text = text, wit_context = wit_context, answer_cbk = answer_cbk, client_uids = client_uids, zone_uids = zone_uids)

# --------------------- End of IPlugin.py  ---------------------
