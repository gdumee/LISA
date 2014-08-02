# -*- coding: UTF-8 -*-
#-----------------------------------------------------------------------------
# project     : Lisa server
# module      : plugins
# file        : PluginManager.py
# description : Management of the plugins
# author      : G.Dumee
#-----------------------------------------------------------------------------
# copyright   : Neotique
#-----------------------------------------------------------------------------


#-----------------------------------------------------------------------------
# Imports
#-----------------------------------------------------------------------------
import lisa.plugins, os, pip, shutil, inspect, json, datetime, uuid, importlib
import lisa.server.core
from lisa.server.web.manageplugins.models import Plugin, Cron, Intent
from twisted.python.reflect import namedAny
from django.template.loader import render_to_string
from pymongo import MongoClient
from twisted.python import log
from lisa.server.config_manager import ConfigManager
from twisted.python.reflect import namedAny


#-----------------------------------------------------------------------------
# Globals
#-----------------------------------------------------------------------------
# Get server configuration
configuration = ConfigManager.getConfiguration()

# Get paths
server_path = configuration['path']
plugins_path = os.path.dirname(lisa.plugins.__file__)


#-----------------------------------------------------------------------------
# PluginManager
#-----------------------------------------------------------------------------
class PluginManager(object):
    """
    Manage plugins
    """
    # Plugins instances
    __PluginsInstances = {}

    #-----------------------------------------------------------------------------
    def __init__(self):
        # Not to be implemented
        raise

    #-----------------------------------------------------------------------------
    @classmethod
    def getEnabledPluginNames(cls):
        # List enabled plugins
        plugin_list = Plugin.objects(enabled = True, lang = configuration['lang_short'])

        # Fill plugins name list
        enabled_plugins_names = []
        for plugin in plugin_list:
            enabled_plugins_names.append(str(plugin['name']))

        return enabled_plugins_names

    #-----------------------------------------------------------------------------
    @classmethod
    def getEnabledPlugins(cls):
        # List enabled plugins
        return Plugin.objects(enabled = True, lang = configuration['lang_short'])

    #-----------------------------------------------------------------------------
    @classmethod
    def getEnabledIntents(cls):
        return Intent.objects(enabled = True)

    #-----------------------------------------------------------------------------
    @classmethod
    def getIntent(cls, intent_name):
        # TODO get these intents from a core function
        # Create the default core intents
        defaults_intent_list = {'name': "core_i_can",
                                'method_name': "list_plugins",
                                'plugin_name': "Core",
                                'enabled': True}
        intent_list, created = Intent.objects.get_or_create(name = 'core_i_can', defaults = defaults_intent_list)
        defaults_intent_list = {'name': "core_i_can_plugin",
                                'method_name': "list_plugin_intents",
                                'plugin_name': "Core",
                                'enabled': True}
        intent_list, created = Intent.objects.get_or_create(name = 'core_i_can_plugin', defaults = defaults_intent_list)

        # List enabled intents
        intent_list = Intent.objects(name = intent_name, enabled = True)

        # If not a unique enabled intent
        if intent_list is None or len(intent_list) != 1:
            return None

        return intent_list[0]

    #-----------------------------------------------------------------------------
    @classmethod
    def init(cls, global_context):
        # Instantiate Core plugin
        module = importlib.import_module("lisa.server.core.intents")
        cls.__PluginsInstances[0] = getattr(module, "Intents")()
        cls.__PluginsInstances[0].uid = 0

        # Get enabled plugin lists
        plugin_list = cls.getEnabledPlugins()

        # Update plugin install
        for plugin in plugin_list:
            log.msg("Initiating plugin {name}".format(name = plugin.name))
            cls._updatePlugin(plugin = plugin)

            try:
                # Create plugin instance
                cls.__PluginsInstances[plugin.pk] = namedAny(plugin.module)()
                cls.__PluginsInstances[plugin.pk].uid = plugin.pk
            except:
                log.err("Error while instantiating plugin {}".format(plugin.name))
                if configuration['debug']['debug_plugin'] == True:
                    raise

            # Init global context vars
            if hasattr(plugin, 'context') == True and plugin.context.has_key('global') == True:
                for var in plugin.context['global']:
                    try:
                        global_context.createGlobalVar(name = var, default = plugin.context['global'][var])
                    except:
                        log.err("Error while creating global context var {} for plugin {}".format(var, plugin.name))
                        if configuration['debug']['debug_plugin'] == True:
                            raise

    #-----------------------------------------------------------------------------
    @classmethod
    def initContext(cls, context):
        # Get enabled plugin lists
        plugin_list = cls.getEnabledPlugins()

        # Update plugin install
        for plugin in plugin_list:
            if hasattr(plugin, 'context') == True and plugin.context.has_key('client') == True:
                for var in plugin.context['client']:
                    try:
                        context.createClientVar(name = var, default = plugin.context['client'][var])
                    except:
                        log.err("Error while creating client context var {} for plugin {}".format(var, plugin['name']))
                        if configuration['debug']['debug_plugin'] == True:
                            raise

    #-----------------------------------------------------------------------------
    @classmethod
    def deinit(cls):
        # Get enabled plugin lists
        plugin_list = cls.getEnabledPlugins()

        # Delete plugin instances
        for pk in cls.__PluginsInstances:
            try:
                cls.__PluginsInstances[pk].clean()
            except:
                pass
        cls.__PluginsInstances = {}

    #-----------------------------------------------------------------------------
    @classmethod
    def getPlugin(cls, plugin_name = None, plugin_uid = None):
        # Return fake core plugin
        if (plugin_uid is not None and plugin_uid == 0) or (plugin_name is not None and plugin_name == "Core"):
            class FakePlugin():
                def __init__(self):
                    self.name = "Core"
                    self.pk = 0
                    self.uid = 0
                    self.steps = {'count': 0, 'first': None, 'last': None}
            return FakePlugin()

        # List enabled plugins
        plugin_list = Plugin.objects(enabled = True, lang = configuration['lang_short'])

        # Search plugin
        for plugin in plugin_list:
            # Search plugin by name
            if plugin_name is not None and plugin.name == plugin_name:
                return plugin

            # Search plugin by uid
            if plugin_uid is not None and plugin.pk == plugin_uid:
                return plugin

        # Not found
        return None

    #-----------------------------------------------------------------------------
    @classmethod
    def getPluginInstance(cls, plugin_name = None, plugin_uid = None):
        plugin = cls.getPlugin(plugin_name = plugin_name, plugin_uid = plugin_uid)
        if plugin is None:
            return None

        if cls.__PluginsInstances.has_key(plugin.pk) == False:
            return None

        return cls.__PluginsInstances[plugin.pk]

    #-----------------------------------------------------------------------------
    @classmethod
    def getPluginMethod(cls, plugin, method_name):
        # Core intents
        if plugin.name == "Core":
            return getattr(cls.__PluginsInstances[0], method_name)

        # Get method from instance
        try:
            return getattr(cls.__PluginsInstances[plugin.pk], method_name)
        except:
            if configuration['debug']['debug_plugin'] == True:
                raise

        return None

    #-----------------------------------------------------------------------------
    @classmethod
    def installPlugin(cls, plugin_name = None, test_mode = False, dev_mode = False):
        # If already installed
        if Plugin.objects(name = plugin_name):
            return {'status': 'fail', 'log': 'Plugin already installed'}

        # If not dev mode, download package
        if not dev_mode:
            if test_mode:
                pip.main(['install', '--quiet', '--install-option=--install-platlib=' + os.getcwd() + '/../',
                          '--install-option=--install-purelib=' + os.getcwd() + '/../', 'lisa-plugin-' + plugin_name])
            else:
                pip.main(['install', 'lisa-plugin-' + plugin_name])

        # Create new plugin
        plugin = Plugin()

        # Update plugin in DB
        cls._updatePlugin(plugin = plugin)

        return {'status': 'success', 'log': 'Plugin installed'}

    #-----------------------------------------------------------------------------
    @classmethod
    def updatePlugin(cls, plugin_name = None, plugin_pk = None):
        # Get plugin by name or pk
        if plugin_pk:
            plugin_list = Plugin.objects(pk = plugin_pk)
        else:
            plugin_list = Plugin.objects(name = plugin_name)

        # Should be only one result
        if not plugin_list or len(plugin_list) != 1:
            return {'status': 'fail', 'log': 'Plugin not installed'}
        plugin = plugin_list[0]

        # Update plugin
        cls._updatePlugin(plugin = plugin)

        return {'status': 'success', 'log': 'Plugin updated'}

    #-----------------------------------------------------------------------------
    @classmethod
    def _updatePlugin(cls, plugin):
        # Load JSON
        plugin_path = os.path.normpath(plugins_path + '/' + plugin.name)
        jsonfile = os.path.normpath(plugin_path + '/' + plugin.name.lower() + '.json')
        try:
            metadata = json.load(open(jsonfile))
        except:
            log.err("Invalid JSON file for plugin {plugin} : {file}".format(plugin = plugin.name, file = jsonfile))
            return

        # Parse file
        for item in metadata:
            if item == 'enabled':
                if metadata[item] == 0 or (type(metadata[item]) == str and metadata[item].lower() == 'false'):
                    setattr(plugin, item, False)
                else:
                    setattr(plugin, item, True)
            elif item != 'crons':
                setattr(plugin, item, metadata[item])

        # Delete older items
        d = plugin.__dict__.copy()
        for k in d:
            if k.startswith("_") == False and k not in metadata and k != 'enabled':
                delattr(plugin, k)

        # TODO remove when uid are not useful
        setattr(plugin, 'uid', plugin.pk)

        #TODO
        setattr(plugin, 'steps', {'count': 0, 'first': None, 'last': None})

        # Add langages from directory search
        setattr(plugin, 'lang', [])
        localedir = os.path.normpath(plugin_path + '/lang')
        for x in os.listdir(localedir):
            try:
                if os.path.isfile("{localedir}/{lang}/LC_MESSAGES/{plugin}.po".format(localedir = localedir, lang = x, plugin = plugin.name.lower())) == True:
                    plugin.lang.append(x)
            except:
                pass

        # Add items
        setattr(plugin, 'path', plugin_path)
        setattr(plugin, 'module', '.'.join(['lisa.plugins', plugin.name, 'modules', plugin.name.lower(), plugin.name]))

        # Save updated plugin
        plugin.save()

        # Update crons
        remove_list = list(Cron.objects(plugin = plugin))
        if metadata.has_key('crons'):
           for cron_name, cron_item in metadata['crons'].iteritems():
                # Get cron from DB
                cron = None
                cron_list = Cron.objects(plugin = plugin, name = cron_name)
                if cron_list is not None and len(cron_list) == 1:
                    cron = cron_list[0]

                # It's a new cron
                if cron is None:
                    # Create a new cron
                    cron = Cron()
                    new_cron= True
                else:
                    # Remove cron from list of crons to remove
                    remove_list.remove(cron)
                    new_cron = False

                # Update cron
                for parameter in cron_item:
                    if parameter != 'enabled':
                        setattr(cron, parameter, cron_item[parameter])

                # Delete older items
                d = cron.__dict__.copy()
                for k in d:
                    if k.startswith("_") == False and k not in cron_item and k != 'enabled':
                        delattr(cron, k)

                # Set enabled only for new crons
                if new_cron == True:
                    if cron_item.has_key('enabled') == True and (cron_item['enabled'] == 0 or (type(cron_item['enabled']) == str and cron_item['enabled'].lower() == 'false')):
                        setattr(cron, 'enabled', False)
                    else:
                        setattr(cron, 'enabled', True)

                # Add items
                setattr(cron, 'name', cron_name)

                # Connect cron to plugin
                cron.plugin = plugin

                # Save cron
                cron.save()

        # Delete older crons for this plugin
        for i in remove_list:
            i.delete()

        # Update intents
        remove_list = list(Intent.objects(plugin = plugin))
        metadata_intents = None
        if metadata.has_key('configuration') and metadata['configuration'].has_key('intents'):
            metadata_intents = metadata['configuration']['intents']
        if metadata.has_key('intents'):
            metadata_intents = metadata['intents']
        if metadata_intents is not None:
            for wit_intent, intent_item in metadata_intents.iteritems():
                # Get intent from DB
                intent = None
                intent_list = Intent.objects(plugin = plugin, name = wit_intent)
                if intent_list is not None and len(intent_list) == 1:
                    intent = intent_list[0]

                # It's a new intent
                if intent is None:
                    # Create a new intent
                    intent = Intent()
                    new_intent= True
                else:
                    # Remove intent from list of intents to remove
                    remove_list.remove(intent)
                    new_intent = False

                # Update intent
                for parameter in intent_item:
                    if parameter == 'method':
                        setattr(intent, 'method_name', intent_item[parameter])
                    elif parameter == 'i_can':
                        setattr(intent, parameter, intent_item[parameter])

                # Delete older items
                d = intent.__dict__.copy()
                for k in d:
                    if k.startswith("_") == False and k not in intent_item and k != 'enabled':
                        delattr(intent, k)

                # Set enabled only for new intents
                if new_intent == True:
                    setattr(intent, 'enabled', True)

                # Connect intent to plugin
                intent.plugin = plugin
                intent.plugin_name = plugin.name

                # Add items
                setattr(intent, 'name', wit_intent)

                # Save intent
                intent.save()

        # Delete older intents for this plugin
        for i in remove_list:
            i.delete()

    #-----------------------------------------------------------------------------
    @classmethod
    def enablePlugin(cls, plugin_name = None, plugin_pk = None):
        return cls._set_plugin_enabled(enabled = True, plugin_name = plugin_name, plugin_pk = plugin_pk)

    #-----------------------------------------------------------------------------
    @classmethod
    def disablePlugin(cls, plugin_name = None, plugin_pk = None):
        return cls._set_plugin_enabled(enabled = False, plugin_name = plugin_name, plugin_pk = plugin_pk)

    #-----------------------------------------------------------------------------
    @classmethod
    def _set_plugin_enabled(cls, enabled, plugin_name = None, plugin_pk = None):
        # Log string
        if enabled == True:
            astr = "enabled"
        else:
            astr = "disabled"

        # Get plugin by name or pk
        if plugin_pk:
            plugin_list = Plugin.objects(pk = plugin_pk)
        else:
            plugin_list = Plugin.objects(name = plugin_name)

        # Should be only one result
        if not plugin_list or len(plugin_list) != 1:
            return {'status': 'fail', 'log': 'Plugin not installed'}
        plugin = plugin_list[0]

        # If already done
        if enabled == True and plugin.enabled == enabled:
            return {'status': 'fail', 'log': 'Plugin already ' + astr}
        if enabled == False and plugin.enabled == enabled:
            return {'status': 'fail', 'log': 'Plugin already ' + astr}

        # Enable plugin
        plugin.enabled = enabled
        plugin.save()

        # Enable plugin crons
        for cron in Cron.objects(plugin = plugin):
            cron.enabled = enabled
            cron.save()

        # Enable plugin intents
        for intent in Intent.objects(plugin = plugin):
            intent.enabled = enabled
            intent.save()

        return {'status': 'success', 'log': 'Plugin ' + astr}

    #-----------------------------------------------------------------------------
    @classmethod
    def uninstallPlugin(cls, plugin_name = None, plugin_pk = None, dev_mode = False):
        # Get plugin by name or pk
        if plugin_pk:
            plugin_list = Plugin.objects(pk = plugin_pk)
        else:
            plugin_list = Plugin.objects(name = plugin_name)

        # Should be only one result
        if not plugin_list or len(plugin_list) != 1:
            return {'status': 'fail', 'log': 'Plugin not installed'}
        plugin = plugin_list[0]

        # Uninstall pip package
        if not dev_mode:
            pip.main(['uninstall', '--quiet', 'lisa-plugin-' + plugin_name])

        # Remove plugin crons
        for cron in Cron.objects(plugin = plugin):
            cron.delete()

        # Remove plugin intents
        for oIntent in Intent.objects(plugin = plugin):
            oIntent.delete()

        # Remove plugin
        plugin.delete()

        return {'status': 'success', 'log': 'Plugin uninstalled'}

    #-----------------------------------------------------------------------------
    @classmethod
    def getPluginMethods(cls, plugin_name = None):
        # Get plugin by name or pk
        if plugin_name:
            plugin_list = Plugin.objects(name = plugin_name)
        else:
            plugin_list = Plugin.objects

        # Parse plugins
        listallmethods = []
        for plugin in plugin_list:
            plugininstance = namedAny('.'.join(('lisa.plugins', str(plugin.name), 'modules', str(plugin.name).lower(), str(plugin.name))))()
            listpluginmethods = []
            for m in inspect.getmembers(plugininstance, predicate = inspect.ismethod):
                if not "__init__" in m and not m.startswith("_"):
                    listpluginmethods.append(m[0])
            listallmethods.append({'plugin': plugin.name, 'methods': listpluginmethods})

        # Parse core plugins
        for f in os.listdir(os.path.normpath(server_path + '/core')):
            fileName, fileExtension = os.path.splitext(f)
            if os.path.isfile(os.path.join(os.path.normpath(server_path + '/core'), f)) and not f.startswith('__init__') and fileExtension != '.pyc':
                coreinstance = namedAny('.'.join(('lisa.server.core', str(fileName).lower(), str(fileName).capitalize())))()
                listcoremethods = []
                for m in inspect.getmembers(coreinstance, predicate = inspect.ismethod):
                    #init shouldn't be listed in methods and _ is for translation
                    if not "__init__" in m and not m.startswith("_"):
                        listcoremethods.append(m[0])
                listallmethods.append({'core': fileName, 'methods': listcoremethods})

        log.msg(listallmethods)
        return listallmethods

    #-----------------------------------------------------------------------------
    @classmethod
    def _template_to_file(cls, filename, template, context):
        import codecs
        codecs.open(filename, 'w', 'utf-8').write(render_to_string(template, context))

    #-----------------------------------------------------------------------------
    @classmethod
    def createPlugin(cls, plugin_name, author_name, author_email):
        import requests
        import pytz

        metareq = requests.get('/'.join([configuration['plugin_store'], 'plugins.json']))
        if(metareq.ok):
            for item in json.loads(metareq.text or metareq.content):
                if item['name'].lower() == plugin_name.lower():
                    return {'status': 'fail', 'log': 'Plugin already exist in the store'}
        context = {
            'plugin_name': plugin_name,
            'plugin_name_lower': plugin_name.lower(),
            'author_name': author_name,
            'author_email': author_email,
            'creation_date': pytz.UTC.localize(datetime.datetime.now()).strftime("%Y-%m-%d %H:%M%z")
        }

        # Create plugin dir
        os.mkdir(os.path.normpath(plugins_path + '/' + plugin_name))

        # Lang stuff
        os.mkdir(os.path.normpath(plugins_path + '/' + plugin_name + '/lang'))
        os.mkdir(os.path.normpath(plugins_path + '/' + plugin_name + '/lang/fr'))
        os.mkdir(os.path.normpath(plugins_path + '/' + plugin_name + '/lang/fr/LC_MESSAGES'))
        cls._template_to_file(filename = os.path.normpath(plugins_path + '/' + plugin_name + '/lang/fr/LC_MESSAGES/' + plugin_name.lower() + '.po'),
                          template = 'plugin/lang/fr/LC_MESSAGES/module.po',
                          context = context)

        # Module stuff
        os.mkdir(os.path.normpath(plugins_path + '/' + plugin_name + '/modules'))
        cls._template_to_file(filename = os.path.normpath(plugins_path + '/' + plugin_name + '/modules/' + plugin_name.lower() + '.py'),
                               template = 'plugin/modules/module.tpl',
                               context = context)
        open(os.path.normpath(plugins_path + '/' + plugin_name + '/modules/__init__.py'), "a")

        # Web stuff
        os.mkdir(os.path.normpath(plugins_path + '/' + plugin_name + '/web'))
        os.mkdir(os.path.normpath(plugins_path + '/' + plugin_name + '/web/templates'))
        shutil.copy(src = os.path.normpath(server_path + '/web/manageplugins/templates/plugin/web/templates/widget.html'),
                    dst = os.path.normpath(plugins_path + '/' + plugin_name + '/web/templates/widget.html'))
        shutil.copy(src = os.path.normpath(server_path + '/web/manageplugins/templates/plugin/web/templates/index.html'),
                    dst = os.path.normpath(plugins_path + '/' + plugin_name + '/web/templates/index.html'))
        open(os.path.normpath(plugins_path + '/' + plugin_name + '/web/__init__.py'), "a")
        cls._template_to_file(filename = os.path.normpath(plugins_path + '/' + plugin_name + '/web/api.py'),
                          template = 'plugin/web/api.tpl',
                          context = context)
        cls._template_to_file(filename = os.path.normpath(plugins_path + '/' + plugin_name + '/web/models.py'),
                          template = 'plugin/web/models.tpl',
                          context = context)
        cls._template_to_file(filename = os.path.normpath(plugins_path + '/' + plugin_name + '/web/tests.py'),
                              template = 'plugin/web/tests.tpl',
                              context = context)
        cls._template_to_file(filename = os.path.normpath(plugins_path + '/' + plugin_name + '/web/urls.py'),
                              template = 'plugin/web/urls.tpl',
                              context = context)
        cls._template_to_file(filename = os.path.normpath(plugins_path + '/' + plugin_name + '/web/views.py'),
                          template = 'plugin/web/views.tpl',
                          context = context)

        # Plugin stuff (metadata)
        cls._template_to_file(filename = os.path.normpath(plugins_path + '/' + plugin_name + '/__init__.py'),
                          template = 'plugin/__init__.tpl',
                          context = context)
        cls._template_to_file(filename = os.path.normpath(plugins_path + '/' + plugin_name + '/README.rst'),
                          template = 'plugin/README.rst',
                          context = context)
        cls._template_to_file(filename = os.path.normpath(plugins_path + '/' + plugin_name + '/' + plugin_name.lower() + '.json'),
                          template = 'plugin/module.json',
                          context = context)

        return {'status': 'success', 'log': 'Plugin created'}

# --------------------- End of PluginManager.py  ---------------------
