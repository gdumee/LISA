# -*- coding: UTF-8 -*-
#-----------------------------------------------------------------------------
# project     : Lisa plugins
# module      : {{ plugin_name }}
# file        : {{ plugin_name_lower }}.py
# description : TODO
# author      : G. Dumee, G. Audet
#-----------------------------------------------------------------------------
# copyright   : Neotique
#-----------------------------------------------------------------------------


#-----------------------------------------------------------------------------
# Imports
#-----------------------------------------------------------------------------
import os, inspect
from lisa.server.plugins.IPlugin import IPlugin


#-----------------------------------------------------------------------------
# {{ plugin_name }}
#-----------------------------------------------------------------------------
class {{ plugin_name }}(IPlugin):
    #-----------------------------------------------------------------------------
    def __init__(self):
        super({{ plugin_name }}, self).__init__(plugin_name = {{ plugin_name }})

    #-----------------------------------------------------------------------------
    def sayHello(self, jsonInput):
        # Get context
        context = jsonInput['context']

        # Create message
        message = self._("multiple_trans").format(param = "test de plugin")

        # Return result to client
        self.speakToClient(context = jsonInput['context'], text = message)

# --------------------- End of {{ plugin_name_lower }}.py  ---------------------

