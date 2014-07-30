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
import lisa.plugins
import pip
import shutil
import inspect
from lisa.server.web.manageplugins.models import Plugin, Description, Rule, Cron, Intent
import json
from twisted.python.reflect import namedAny
from django.template.loader import render_to_string
import datetime
from pymongo import MongoClient
from twisted.python import log
import os
from lisa.server.config_manager import ConfigManager


#-----------------------------------------------------------------------------
# Globals
#-----------------------------------------------------------------------------
configuration = ConfigManager.getConfiguration()
dir_path = configuration['path']


#-----------------------------------------------------------------------------
# PluginManager
#-----------------------------------------------------------------------------
class PluginManager(object):
    """
    """

    #-----------------------------------------------------------------------------
    def __init__(self):
        self.pkgpath = os.path.dirname(lisa.plugins.__file__)
        self.enabled_plugins = []
        mongo = MongoClient(configuration['database']['server'], configuration['database']['port'])
        self.database = mongo.lisa
        self.loadPlugins()

    #-----------------------------------------------------------------------------
    def getEnabledPlugins(self):
        return self.enabled_plugins

    #-----------------------------------------------------------------------------
    def loadPlugins(self):
        self.enabled_plugins = []
        for plugin in self.database.plugins.find({"enabled": True, "lang": configuration['lang_short']}):
            self.enabled_plugins.append(str(plugin['name']))

        return self.enabled_plugins

    #-----------------------------------------------------------------------------
    def installPlugin(self, plugin_name = None, test_mode = False, dev_mode = False):
        if Plugin.objects(name = plugin_name):
            return {'status': 'fail', 'log': 'Plugin already installed'}

        # If not dev mode, download package
        if not dev_mode:
            if test_mode:
                pip.main(['install', '--quiet', '--install-option=--install-platlib=' + os.getcwd() + '/../',
                          '--install-option=--install-purelib=' + os.getcwd() + '/../', 'lisa-plugin-' + plugin_name])
            else:
                pip.main(['install', 'lisa-plugin-' + plugin_name])

        # Create plugin
        plugin = Plugin()

        self._updatePlugin(plugin, plugin_name)

        self.loadPlugins()

        return {'status': 'success', 'log': 'Plugin installed'}

    #-----------------------------------------------------------------------------
    def updatePlugin(self, plugin_name = None, plugin_pk = None):
        if plugin_pk:
            plugin_list = Plugin.objects(pk = plugin_pk)
        else:
            plugin_list = Plugin.objects(name = plugin_name)

        if not plugin_list:
            return {'status': 'fail', 'log': 'Plugin not installed'}

        for plugin in plugin_list:
            self._updatePlugin(plugin, plugin.name)
            break

        self.loadPlugins()

        return {'status': 'success', 'log': 'Plugin updated'}

    #-----------------------------------------------------------------------------
    def _updatePlugin(self, plugin, plugin_name):
        # Load Json
        jsonfile = self.pkgpath + '/' + plugin_name + '/' + plugin_name.lower() + '.json'
        metadata = json.load(open(jsonfile))

        # Parse description
        for item in metadata:
            if item == 'description':
                description_list = []
                for description in metadata[item]:
                    oDescription = Description()
                    for k, v in description.iteritems():
                        setattr(oDescription, k, v)
                    description_list.append(oDescription)
                setattr(plugin, item, description_list)
            elif item == 'enabled':
                if metadata[item] == 0 or (type(metadata[item]) == str and metadata[item].lower() == 'false'):
                    setattr(plugin, item, False)
                else:
                    setattr(plugin, item, True)
            elif item != 'crons' and item != 'rules':
                setattr(plugin, item, metadata[item])
        d = plugin.__dict__.copy()
        for k in d:
            if k.startswith("_") == False and k not in metadata:
                delattr(plugin, k)
        plugin.save()

        # Register rules and crons after plugin is saved
        rule_list = Rule.objects(plugin = plugin)
        for r in rule_list:
            r.delete()
        cron_list = Cron.objects(plugin = plugin)
        for c in cron_list:
            c.delete()
        if metadata.has_key('rules'):
            for rule_item in metadata['rules']:
                rule = Rule()
                for parameter in rule_item:
                    if parameter == 'enabled':
                        if rule_item[parameter] == 0:
                            setattr(rule, parameter, False)
                        else:
                            setattr(rule, parameter, True)
                    else:
                        setattr(rule, parameter, rule_item[parameter])
                rule.plugin = plugin
                d = rule.__dict__.copy()
                rule.save()
        if metadata.has_key('crons'):
            for cron_item in metadata['crons']:
                cron = Cron()
                for parameter in cron_item:
                    if parameter == 'enabled':
                        if cron_item[parameter] == 0:
                            setattr(cron, parameter, False)
                        else:
                            setattr(cron, parameter, True)
                    else:
                        setattr(cron, parameter, cron_item[parameter])
                cron.plugin = plugin
                d = cron.__dict__.copy()
                cron.save()

        # Register intents after plugin is saved
        intent_list = Intent.objects(plugin = plugin)
        for i in intent_list:
            i.delete()
        for intent, value in metadata['configuration']['intents'].iteritems():
            oIntent = Intent()
            oIntent.name = intent
            oIntent.function = value['method']
            oIntent.module = '.'.join(['lisa.plugins', plugin_name, 'modules', plugin_name.lower(), plugin_name])
            oIntent.enabled = True
            oIntent.plugin = plugin
            oIntent.save()

    #-----------------------------------------------------------------------------
    def isPluginEnabled(self, plugin_name = None, plugin_pk = None):
        if plugin_pk:
            plugin_list = Plugin.objects(pk = plugin_pk)
        else:
            plugin_list = Plugin.objects(name = plugin_name)

        if not plugin_list:
            return False

        return plugin.enabled

    #-----------------------------------------------------------------------------
    def enablePlugin(self, plugin_name = None, plugin_pk = None):
        return self._set_plugin_enabled(enabled = True, plugin_name = plugin_name, plugin_pk = plugin_pk)

    #-----------------------------------------------------------------------------
    def disablePlugin(self, plugin_name = None, plugin_pk = None):
        return self._set_plugin_enabled(enabled = False, plugin_name = plugin_name, plugin_pk = plugin_pk)

    #-----------------------------------------------------------------------------
    def _set_plugin_enabled(self, enabled, plugin_name = None, plugin_pk = None):
        if enabled == True:
            astr = "enabled"
        else:
            astr = "disabled"

        if plugin_pk:
            plugin_list = Plugin.objects(pk = plugin_pk)
        else:
            plugin_list = Plugin.objects(name = plugin_name)

        if not plugin_list:
            return {'status': 'fail', 'log': 'Plugin not installed'}

        for plugin in plugin_list:
            if enabled == True and plugin.enabled == enabled:
                return {'status': 'fail', 'log': 'Plugin already ' + astr}
            if enabled == False and plugin.enabled == enabled:
                return {'status': 'fail', 'log': 'Plugin already ' + astr}

            plugin.enabled = enabled
            plugin.save()
            for cron in Cron.objects(plugin = plugin):
                cron.enabled = enabled
                cron.save()
            for rule in Rule.objects(plugin = plugin):
                rule.enabled = enabled
                rule.save()
            for intent in Intent.objects(plugin = plugin):
                intent.enabled = enabled
                intent.save()
            break

        self.loadPlugins()

        return {'status': 'success', 'log': 'Plugin ' + astr}

    #-----------------------------------------------------------------------------
    def uninstallPlugin(self, plugin_name = None, plugin_pk = None, dev_mode = False):
        if plugin_pk:
            plugin_list = Plugin.objects(pk = plugin_pk)
        else:
            plugin_list = Plugin.objects(name = plugin_name)

        if not plugin_list:
            return {'status': 'fail', 'log': 'Plugin not installed'}

        for plugin in plugin_list:
            if not dev_mode:
                pip.main(['uninstall', '--quiet', 'lisa-plugin-' + plugin_name])
            for cron in Cron.objects(plugin = plugin):
                cron.delete()
            for rule in Rule.objects(plugin = plugin):
                rule.delete()
            for oIntent in Intent.objects(plugin = plugin):
                oIntent.delete()
            plugin.delete()
            break

        self.loadPlugins()

        return {'status': 'success', 'log': 'Plugin uninstalled'}

    #-----------------------------------------------------------------------------
    def methodListPlugin(self, plugin_name = None):
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
        for f in os.listdir(os.path.normpath(dir_path + '/core')):
            fileName, fileExtension = os.path.splitext(f)
            if os.path.isfile(os.path.join(os.path.normpath(dir_path + '/core'), f)) and not f.startswith('__init__') and fileExtension != '.pyc':
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
    def _template_to_file(self, filename, template, context):
        import codecs
        codecs.open(filename, 'w', 'utf-8').write(render_to_string(template, context))

    #-----------------------------------------------------------------------------
    def createPlugin(self, plugin_name, author_name, author_email):
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
        os.mkdir(os.path.normpath(self.pkgpath + '/' + plugin_name))

        # Lang stuff
        os.mkdir(os.path.normpath(self.pkgpath + '/' + plugin_name + '/lang'))
        os.mkdir(os.path.normpath(self.pkgpath + '/' + plugin_name + '/lang/en'))
        os.mkdir(os.path.normpath(self.pkgpath + '/' + plugin_name + '/lang/en/LC_MESSAGES'))
        self._template_to_file(filename=os.path.normpath(self.pkgpath + '/' + plugin_name + '/lang/en/LC_MESSAGES/' +
                                                    plugin_name.lower() + '.po'),
                          template='plugin/lang/en/LC_MESSAGES/module.po',
                          context=context)

        # Module stuff
        os.mkdir(os.path.normpath(self.pkgpath + '/' + plugin_name + '/modules'))
        self._template_to_file(filename=os.path.normpath(self.pkgpath + '/' + plugin_name + '/modules/' +
                               plugin_name.lower() + '.py'),
                               template='plugin/modules/module.tpl',
                               context=context)
        open(os.path.normpath(self.pkgpath + '/' + plugin_name + '/modules/__init__.py'), "a")

        # Web stuff
        os.mkdir(os.path.normpath(self.pkgpath + '/' + plugin_name + '/web'))
        os.mkdir(os.path.normpath(self.pkgpath + '/' + plugin_name + '/web/templates'))
        shutil.copy(src=os.path.normpath(dir_path + '/web/manageplugins/templates/plugin/web/templates/widget.html'),
                    dst=os.path.normpath(self.pkgpath + '/' + plugin_name + '/web/templates/widget.html'))
        shutil.copy(src=os.path.normpath(dir_path + '/web/manageplugins/templates/plugin/web/templates/index.html'),
                    dst=os.path.normpath(self.pkgpath + '/' + plugin_name + '/web/templates/index.html'))
        open(os.path.normpath(self.pkgpath + '/' + plugin_name + '/web/__init__.py'), "a")
        self._template_to_file(filename=os.path.normpath(self.pkgpath + '/' + plugin_name + '/web/api.py'),
                          template='plugin/web/api.tpl',
                          context=context)
        self._template_to_file(filename=os.path.normpath(self.pkgpath + '/' + plugin_name + '/web/models.py'),
                          template='plugin/web/models.tpl',
                          context=context)
        self._template_to_file(filename=os.path.normpath(self.pkgpath + '/' + plugin_name + '/web/tests.py'),
                              template='plugin/web/tests.tpl',
                              context=context)
        self._template_to_file(filename=os.path.normpath(self.pkgpath + '/' + plugin_name + '/web/urls.py'),
                              template='plugin/web/urls.tpl',
                              context=context)
        self._template_to_file(filename=os.path.normpath(self.pkgpath + '/' + plugin_name + '/web/views.py'),
                          template='plugin/web/views.tpl',
                          context=context)

        # Plugin stuff (metadata)
        self._template_to_file(filename=os.path.normpath(self.pkgpath + '/' + plugin_name + '/__init__.py'),
                          template='plugin/__init__.tpl',
                          context=context)
        self._template_to_file(filename=os.path.normpath(self.pkgpath + '/' + plugin_name + '/README.rst'),
                          template='plugin/README.rst',
                          context=context)
        self._template_to_file(filename=os.path.normpath(self.pkgpath + '/' + plugin_name +
                                                    '/' + plugin_name.lower() + '.json'),
                          template='plugin/module.json',
                          context=context)

        self.loadPlugins()

        return {'status': 'success', 'log': 'Plugin created'}


#-----------------------------------------------------------------------------
# PluginManagerSingleton
#-----------------------------------------------------------------------------
class PluginManagerSingleton(object):
    """
    Singleton version of the plugin manager.

    Being a singleton, this class should not be initialised explicitly
    and the ``get`` classmethod must be called instead.

    To call one of this class's methods you have to use the ``get``
    method in the following way:
    ``PluginManagerSingleton.get().themethodname(theargs)``
    """

    __instance = None

    #-----------------------------------------------------------------------------
    def __init__(self):
        """
        Initialisation: this class should not be initialised
        explicitly and the ``get`` classmethod must be called instead.
        """

        if self.__instance is not None:
            raise Exception("Singleton can't be created twice !")

    #-----------------------------------------------------------------------------
    def get(self):
        """
        Actually create an instance
        """
        if self.__instance is None:
            self.__instance = PluginManager()
            log.msg("PluginManagerSingleton initialised")
        return self.__instance
    get = classmethod(get)

# --------------------- End of PluginManager.py  ---------------------
