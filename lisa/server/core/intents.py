# -*- coding: UTF-8 -*-
#-----------------------------------------------------------------------------
# project     : Lisa server
# module      : Core plugin
# file        : intents.py
# description : Return server abilities
# author      : G.Dumée
#-----------------------------------------------------------------------------
# copyright   : Neotique
#-----------------------------------------------------------------------------


#-----------------------------------------------------------------------------
# Imports
#-----------------------------------------------------------------------------
import json, os
from random import random
from lisa.server.plugins.IPlugin import IPlugin
from lisa.server.web.manageplugins.models import Intent as oIntents
from lisa.server.config_manager import ConfigManager
from lisa.server.plugins.PluginManager import PluginManager
from lisa.Neotique.NeoConv import NeoConv


#-----------------------------------------------------------------------------
# Intents
#-----------------------------------------------------------------------------
class Intents(IPlugin):
    #-----------------------------------------------------------------------------
    def __init__(self):
        super(Intents, self).__init__()
        configuration_server = ConfigManager.getConfiguration()
        self._ = configuration_server['trans']

    #-----------------------------------------------------------------------------
    def list_plugins(self, jsonInput):
        # Get context
        context = jsonInput['context']

        # Parse plugins that has i_can strings
        desc_list = []
        for plugin in PluginManager.getEnabledPlugins():
            if hasattr(plugin, 'i_can') == True and plugin.i_can is not None:
                # Get translation method from plugin
                instance = PluginManager.getPluginInstance(plugin.name)

                # Translate intent description
                desc_list.append(instance._(plugin.i_can))

        # When there is too much sentences
        message = ""
        if len(desc_list) > 4:
            message = self._("i_can_do_many") + ". "

        # Get 4 sentences randomly
        for i in range(4):
            if len(desc_list) == 0:
                break;

            val = int(random() * len(desc_list))
            message += desc_list[val] + ". "
            desc_list.pop(val)

        # Speak to client
        self.speakToClient(text = message, context = context)

    #-----------------------------------------------------------------------------
    def list_plugin_intents(self, jsonInput):
        # Get context
        context = jsonInput['context']

        # Get plugin name
        plugin_name = None
        try:
            plugin_name = jsonInput['outcome']['entities']['plugin_name']['value']
        except:
            pass

        # Parse intents that has i_can strings
        desc_list = []
        for intent in PluginManager.getEnabledIntents():
            if NeoConv.compareSimilar(intent.plugin_name, plugin_name) == False:
                continue

            if hasattr(intent, 'i_can') == True and intent.i_can is not None:
                # Get translation method from plugin
                instance = PluginManager.getPluginInstance(intent.plugin_name)

                # Translate intent description
                desc_list.append(instance._(intent.i_can))

        # If no plugin given
        if len(desc_list) == 0:
            # No plugin
            message = self._("core_intent_no_plugin")

            # Speak to client
            self.speakToClient(text = message, context = context)

            return

        # When there is too much sentences
        message = ""
        if len(desc_list) > 4:
            message = self._("i_can_do_many") + ". "

        # Get 4 sentences randomly
        for i in range(4):
            if len(desc_list) == 0:
                break;

            val = int(random() * len(desc_list))
            message += desc_list[val] + ". "
            desc_list.pop(val)

        # Speak to client
        self.speakToClient(text = message, context = context)

# --------------------- End of intents.py  ---------------------
