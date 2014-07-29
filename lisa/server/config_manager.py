# -*- coding: UTF-8 -*-
#-----------------------------------------------------------------------------
# project     : Lisa server
# module      : server
# file        : config_manager.py
# description : Manage server configuration
# author      : G.Dumee
#-----------------------------------------------------------------------------
# copyright   : Neotique
#-----------------------------------------------------------------------------


#-----------------------------------------------------------------------------
# Imports
#-----------------------------------------------------------------------------
from twisted.python import log
import os
import pkg_resources
import json
import platform
from lisa.Neotique.NeoTrans import NeoTrans


#-----------------------------------------------------------------------------
# ConfigManager
#-----------------------------------------------------------------------------
class ConfigManager(object):
    """
    """
    # Singleton
    __instance = None

    #-----------------------------------------------------------------------------
    def __init__(self, config_file = ""):
        self.valid_flag = True
        self.configuration = {}

        # Read configuration file
        if os.path.isfile(config_file) == True and config_file.endswith('.json') == True:
            self.configuration = json.load(open(config_file))
        elif os.path.isfile('/etc/lisa/server/configuration/lisa.json') == True:
            self.configuration = json.load(open('/etc/lisa/server/configuration/lisa.json'))
        else:
            self.configuration = json.load(open(pkg_resources.resource_filename(__name__, 'configuration/lisa.json.sample')))

        # Path
        self.configuration['path'] = os.path.dirname(__file__)

        # Lang params
        if self.configuration.has_key('lang') == False:
            self.configuration['lang'] = "fr-FR"
        self.configuration['lang_short'] = self.configuration['lang'].split('-')[0]

        # Server params
        if self.configuration.has_key('lisa_web_port') == False:
            log.err("Error configuration : no web port : 'lisa_web_port'")
            self.valid_flag = False
        if self.configuration.has_key('lisa_port') == False:
            log.err("Error configuration : no server port : 'lisa_port'")
            self.valid_flag = False

        # SSL params
        if self.configuration.has_key('enable_secure_mode') == True and self.configuration['enable_secure_mode'] == True:
            # SSL cert
            if self.configuration.has_key('lisa_ssl_crt') == True:
                if os.path.isfile(self.configuration['lisa_ssl_crt']) == False:
                    log.err("Error configuration : SSL certificat {} is not found : 'lisa_ssl_crt'".format(self.configuration['lisa_ssl_crt']))
                    self.valid_flag = False
            elif os.path.isfile(self.configuration['path'] + '/configuration/ssl/server.crt') == False:
                log.err("Error configuration : no valid SSL certificat found : 'lisa_ssl_crt'")
                self.valid_flag = False
            else:
                self.configuration['lisa_ssl_crt'] = os.path.normpath(self.configuration['path'] + '/configuration/ssl/server.crt')

            # SSL private key
            if self.configuration.has_key('lisa_ssl_key') == True:
                if os.path.isfile(self.configuration['lisa_ssl_key']) == False:
                    log.err("Error configuration : SSL private key {} is not found : 'lisa_ssl_key'".format(self.configuration['lisa_ssl_key']))
                    self.valid_flag = False
            elif os.path.isfile(self.configuration['path'] + '/configuration/ssl/server.key') == False:
                log.err("Error configuration : no valid SSL private key found : 'lisa_ssl_key'")
                self.valid_flag = False
            else:
                self.configuration['lisa_ssl_key'] = os.path.normpath(self.configuration['path'] + '/configuration/ssl/server.key')

        # Translation function
        lang_path = self.configuration['path'] + "/lang"
        self.configuration['trans'] = NeoTrans(domain = 'lisa', localedir = lang_path, languages = [self.configuration['lang_short']]).Trans

    #-----------------------------------------------------------------------------
    def _getConfiguration(self):
        if ConfigManager.__instance is None:
            ConfigManager.__instance = ConfigManager()
        return ConfigManager.__instance.configuration
    getConfiguration = classmethod(_getConfiguration)

    #-----------------------------------------------------------------------------
    def _setConfiguration(self, config_file):
        ConfigManager.__instance = None
        ConfigManager.__instance = ConfigManager(config_file)
        return ConfigManager.__instance.valid_flag
    setConfiguration = classmethod(_setConfiguration)


# --------------------- End of config_manager.py  ---------------------
