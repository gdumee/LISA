# -*- coding: utf-8; tab-width: 4; indent-tabs-mode: t; python-indent: 4 -*-
from pymongo import MongoClient

from lisa.server.ConfigManager import ConfigManagerSingleton

configuration = ConfigManagerSingleton.get().getConfiguration()


class IPlugin(object):
    """
    The most simple interface to be inherited when creating a plugin.
    """

    #-----------------------------------------------------------------------------
    def __init__(self):
        """
        Set the basic variables.
        """
        self.configuration_lisa = configuration
        self.mongo = MongoClient(host=self.configuration_lisa['database']['server'],
                            port=self.configuration_lisa['database']['port'])

        # UID is set by DialogContext just after constructor
        self.uid = None

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
            NeoDialogContext.globalSpeakToClient(plugin_uid = self.uid, text = text, client_uids = client_uids, zone_uids = zone_uids)
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
            NeoDialogContext.globalAskClient(plugin_uid = self.uid, text = text, wit_context = wit_context, answer_cbk = answer_cbk, client_uids = client_uids, zone_uids = zone_uids)
            return

        # Update context
        context.askClient(plugin_uid = self.uid, text = text, wit_context = wit_context, answer_cbk = answer_cbk, client_uids = client_uids, zone_uids = zone_uids)
