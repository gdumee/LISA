# -*- coding: UTF-8 -*-
import json, os, gettext
from pymongo import MongoClient
from twisted.python.reflect import namedAny
from twisted.python import log
from wit import Wit
import lisa.server


class RulesEngine():
    def __init__(self, configuration):
        self.configuration = configuration
        client = MongoClient(self.configuration['database']['server'], self.configuration['database']['port'])
        self.database = client.lisa

        path = os.path.normpath(str(lisa.server.__path__[0]) + "/lang")
        self._ = translation = gettext.translation(domain='intents', localedir=path, fallback=True,
                                              languages=[self.configuration['lang']]).ugettext
        self.wit = Wit(self.configuration['wit_token'])

    def Rules(self, jsonData, lisaprotocol):
        rulescollection = self.database.rules
        intentscollection = self.database.intents
        jsonInput = self.wit.get_message(unicode(jsonData['body']))
        jsonInput['from'], jsonInput['type'], jsonInput['zone'] = jsonData['from'], jsonData['type'], jsonData['zone']

        if self.configuration['debug']['debug_before_before_rule']:
            log.msg("Before 'before' rule: " + str(jsonInput))
        for rule in rulescollection.find({"enabled": True, "before": {"$ne":None}}).sort([("order", 1)]):
            exec(rule['before'])
        if self.configuration['debug']['debug_after_before_rule']:
            log.msg("After 'before' rule: " + str(jsonInput))
        if self.configuration['debug']['debug_wit']:
            log.msg("WIT: " + str(jsonInput['outcome']))

        oIntent = intentscollection.find_one({"name": jsonInput['outcome']['intent']})
        if oIntent and jsonInput['outcome']['confidence'] >= self.configuration['wit_confidence']:
            instance = namedAny(str(oIntent["module"]))()
            methodToCall = getattr(instance, oIntent['function'])
            jsonOutput = methodToCall(jsonInput)
        else:
            jsonOutput = {}
            jsonOutput['plugin'] = "None"
            jsonOutput['method'] = "None"
            jsonOutput['body'] = self._("I have not the right plugin installed to answer you correctly")
        jsonOutput['from'] = jsonData['from']
        if self.configuration['debug']['debug_before_after_rule']:
            log.msg("Before 'after' rule: " + str(jsonOutput))
        for rule in rulescollection.find({"enabled": True, "after": {"$ne":None}}).sort([("order", 1)]):
            exec(rule['after'])
            #todo it doesn't check if the condition of the rule after has matched to end the rules
            if rule['end']:
                break
        if self.configuration['debug']['debug_after_after_rule']:
            log.msg("After 'after' rule: " + str(jsonOutput))