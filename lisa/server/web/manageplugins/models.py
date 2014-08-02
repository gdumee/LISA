from mongoengine import *
from lisa.server.web.weblisa.settings import DBNAME
connect(DBNAME)

class Plugin(DynamicDocument):
    name = StringField(max_length=120, required=True, help_text='Name of the plugin')
    lang = ListField(StringField(max_length=2), help_text="List of supported languages : ['all','WebSocket']")
    enabled = BooleanField(help_text="Boolean to know if the plugin is enabled or not")
    version = StringField(help_text="The version number of the plugin")
    i_can = StringField(help_text="Contains a translation key for what the plugin can do")
    configuration = DictField(help_text="Configuration dictionnary of the plugin")
    meta = {
        'collection': 'plugins',
        'allow_inheritance': False
    }

class Intent(DynamicDocument):
    plugin = ReferenceField(Plugin, reverse_delete_rule=CASCADE)
    name = StringField(required=True, help_text="Name of the intent (whitespaces are _ ). Ex: core_intents_list")
    plugin_name = StringField(required=True, help_text="The path to the module including the class name. Ex: core.intents.Intents")
    method_name = StringField(required=True, help_text="The function name. Ex: list")
    enabled = BooleanField(default=False, help_text="Boolean to know if the intent is enabled or not")
    i_can = StringField(help_text="Contains a translation key for what the intent can do")
    meta = {
        'collection': 'intents',
        'allow_inheritance': False
    }

class Cron(DynamicDocument):
    plugin = ReferenceField(Plugin, reverse_delete_rule=CASCADE)
    enabled = BooleanField()
    name = StringField(required=True, help_text="Name of the rule (whitespaces are _ ). Ex: download_rule")
    meta = {
        'collection': 'crons',
        'allow_inheritance': False
    }
