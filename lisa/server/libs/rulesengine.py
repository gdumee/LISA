# -*- coding: UTF-8 -*-
import gettext
from pymongo import MongoClient
from twisted.python.reflect import namedAny
from twisted.python import log
from wit import Wit
import json
from lisa.Neotique.NeoTrans import NeoTrans
from lisa.Neotique.NeoDialog import NeoDialog
from lisa.server.ConfigManager import ConfigManagerSingleton


#-----------------------------------------------------------------------------
# RulesEngine
#-----------------------------------------------------------------------------
class RulesEngine():
    def __init__(self):
        self.configuration = ConfigManagerSingleton.get().getConfiguration()
        client = MongoClient(self.configuration['database']['server'], self.configuration['database']['port'])
        self.database = client.lisa
        self.wit = Wit(self.configuration['wit_token'])
        self.rulescollection = self.database.rules
        self.intentscollection = self.database.intents
        self.dialog = NeoDialog(self.configuration)

        path = '/'.join([ConfigManagerSingleton.get().getPath(), 'lang'])
        self._ = NeoTrans(domain='lisa', localedir=path, fallback=True, languages=[self.configuration['lang']]).Trans

    #-----------------------------------------------------------------------------
    def parse(self, jsonData, lisaprotocol):
        # If input has already a decoded intent
        if jsonData.has_key("outcome") == True:
            jsonInput = {}
            jsonInput['outcome'] = jsonData['outcome']
        else:
            # Ask Wit for intent decoding
            jsonInput = self.wit.get_message(unicode(jsonData['body']))
        
        # Initialize output from input
        jsonInput['from'], jsonInput['type'], jsonInput['zone'] = jsonData['from'], jsonData['type'], jsonData['zone']
        jsonInput['lisaprotocol'] = lisaprotocol

        # Before rules
        if self.configuration['debug']['debug_before_before_rule']:
            log.msg(self._("Before 'before' rule: %(jsonInput)s" % {'jsonInput': str(jsonInput)}))
        for rule in self.rulescollection.find({"enabled": True, "before": {"$ne": None}}).sort([("order", 1)]):
            exec(rule['before'])
        if self.configuration['debug']['debug_after_before_rule']:
            log.msg(self._("After 'before' rule: %(jsonInput)s" % {'jsonInput': str(jsonInput)}))
        
        # Execute intent in a plugin
        if self.configuration['debug']['debug_wit']:
            log.msg("WIT: " + str(jsonInput['outcome']))
        oIntent = self.intentscollection.find_one({"name": jsonInput['outcome']['intent']})
        if oIntent and jsonInput['outcome']['confidence'] >= self.configuration['wit_confidence']:
            instance = namedAny(str(oIntent["module"]))()
            methodToCall = getattr(instance, oIntent['function'])
            jsonOutput = methodToCall(jsonInput)
        else:
            jsonOutput = {}
            jsonOutput['plugin'] = "None"
            jsonOutput['method'] = "None"
            jsonOutput['body'] = self._("no_plugin")
        
        # After rules
        jsonOutput['from'] = jsonInput['from']
        if self.configuration['debug']['debug_before_after_rule']:
            log.msg(self._("Before 'after' rule: %(jsonOutput)s" % {'jsonOutput': str(jsonOutput)}))
        for rule in self.rulescollection.find({"enabled": True, "after": {"$ne":None}}).sort([("order", 1)]):
            exec(rule['after'])
            if rule['end']:
                break
        if self.configuration['debug']['debug_after_after_rule']:
            log.msg(self._("After 'after' rule: %(jsonOutput)s" % {'jsonOutput': str(jsonOutput)}))

# --------------------- End of rulesengine.py  ---------------------
