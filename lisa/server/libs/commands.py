import json, os, gettext
from pymongo import MongoClient
import lisa.server

class Commands():
    """
        body : contains the text that will be spoken
        type : will be "command"
        from : the message is issued from "LISA Server"
        command : contains the command name
        clients_zone : should be ['sender'] to answer to the client who issued the command,
        * : you can pass other parameters in your json. The client will handle these as he recognize the command name

    """

    def __init__(self, configuration, lisaprotocol):
        self.configuration = configuration
        client = MongoClient(configuration['database']['server'], configuration['database']['port'])
        self.database = client.lisa

        path = os.path.normpath(str(lisa.server.__path__[0]) + "/lang")
        self._ = translation = gettext.translation(domain='lisa', localedir=path, fallback=True,
                                              languages=[self.configuration['lang']]).ugettext
        self.lisaprotocol = lisaprotocol

    def mute(self, zone_list):
        # ask clients to mute
        for client in self.lisaprotocol.factory.clients:
            if 'all' in zone_list or client['zone'] in zone_list:
                client['connection'].sendLine("{'type': 'command', 'command': 'mute', 'from': 'LISA Server'}")

