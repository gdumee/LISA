# -*- coding: UTF-8 -*-
import json, os
from pymongo import MongoClient
from wit import Wit
from lisa.server.web.manageplugins.models import Intent as oIntents
import gettext
import lisa.server

from lisa.server.config_manager import ConfigManager
from lisa.Neotique.NeoTrans import NeoTrans

class Intents:
    def __init__(self, lisa=None):
        self.lisa = lisa
        self.configuration = ConfigManager.getConfiguration()
        self._ = self.configuration['trans']

        mongo = MongoClient(host=self.configuration['database']['server'],
                            port=self.configuration['database']['port'])
        self.database = mongo.lisa
        self.wit = Wit(self.configuration['wit_token'])

    def list(self, jsonInput):
        intentstr = []
        listintents = self.wit.get_intents()
        for oIntent in oIntents.objects(enabled=True):
            for witintent in listintents:
                print witintent
                if witintent["name"] == oIntent.name and 'metadata' in witintent:
                    if witintent['metadata']:
                        metadata = json.loads(witintent['metadata'])
                        intentstr.append(metadata['tts'])

        return {"plugin": "Intents",
                "method": "list",
                "body": self._("intents_list").format(intentslist = ', '.join(intentstr))
        }
