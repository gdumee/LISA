# -*- coding: UTF-8 -*-
#-----------------------------------------------------------------------------
# project     : Lisa client
# module      : client
# file        : service.py
# description : Lisa client twisted service
# author      : G.Dumee
#-----------------------------------------------------------------------------
# copyright   : Neotique
#-----------------------------------------------------------------------------


#-----------------------------------------------------------------------------
# Imports
#-----------------------------------------------------------------------------
import os
from twisted.internet import reactor, ssl
from twisted.application import internet, service
from twisted.web import server, wsgi, static
from twisted.python import threadpool, log
from autobahn.twisted.websocket import WebSocketServerFactory
from autobahn.twisted.resource import WebSocketResource
from OpenSSL import SSL
from lisa.server.config_manager import ConfigManager
from subprocess import call
import glob


#-----------------------------------------------------------------------------
# Globals
#-----------------------------------------------------------------------------
# Creating MultiService
application = service.Application('LISA')


#-----------------------------------------------------------------------------
# ThreadPoolService
#-----------------------------------------------------------------------------
class ThreadPoolService(service.Service):
    def __init__(self, pool):
        self.pool = pool

    def startService(self):
        service.Service.startService(self)
        self.pool.start()

    def stopService(self):
        service.Service.stopService(self)
        self.pool.stop()


#-----------------------------------------------------------------------------
# SSL client certificat verification callback
#-----------------------------------------------------------------------------
def ClientAuthVerifyCallback(connection, x509, errnum, errdepth, ok):
    if not ok:
        print 'Invalid client certificat :', x509.get_subject()
        return False

    print "Client certificat is OK"
    return ok


#-----------------------------------------------------------------------------
# Make twisted service
#-----------------------------------------------------------------------------
def makeService(config):
    from django.core.handlers.wsgi import WSGIHandler
    os.environ['DJANGO_SETTINGS_MODULE'] = 'lisa.server.web.weblisa.settings'

    # Get configuration
    if config['configuration']:
        if ConfigManager.setConfiguration(config['configuration']) == False:
            log.err("Error : configuration file invalid")
            return

    configuration = ConfigManager.getConfiguration()
    dir_path = configuration['path']

    from lisa.server import libs

    # Multiservice mode
    multi = service.MultiService()
    multi.setServiceParent(application)
    pool = threadpool.ThreadPool()
    tps = ThreadPoolService(pool)
    tps.setServiceParent(multi)

    libs.scheduler.setServiceParent(multi)
    libs.Initialize()

    # Creating the web stuff
    resource_wsgi = wsgi.WSGIResource(reactor, tps.pool, WSGIHandler())
    root = libs.Root(resource_wsgi)
    staticrsrc = static.File('/'.join([dir_path,'web/interface/static']))
    root.putChild("static", staticrsrc)

    # Start client protocol factory
    if configuration['enable_secure_mode']:
        # Create a SSL context factory for clients
        clientAuthContextFactory = ssl.DefaultOpenSSLContextFactory(configuration['lisa_ssl_key'], configuration['lisa_ssl_crt'])

        # Add client authentification to SSL context
        ctx = clientAuthContextFactory.getContext()
        ctx.set_verify(SSL.VERIFY_PEER | SSL.VERIFY_FAIL_IF_NO_PEER_CERT, ClientAuthVerifyCallback)

        # Load client certificates authorized to connect
        cert_path = dir_path + '/' + 'configuration/ssl/public/'
        outfile = os.path.normpath(dir_path + '/' + 'configuration/ssl/public/server.pem')
        with open(outfile, "w") as f:
            wildcard = os.path.normpath("{path}*.crt".format(path = cert_path))
            for infile in glob.glob(wildcard):
                call(['openssl', 'x509', '-in', infile, '-text'], stdout = f)
        ctx.load_verify_locations(outfile)

        # Initialize client factory
        engineService = internet.SSLServer(configuration['lisa_port'], libs.ClientFactorySingleton.get(), clientAuthContextFactory)

        # Create a SSL context factory for web interface
        webAuthContextFactory = ssl.DefaultOpenSSLContextFactory(configuration['lisa_ssl_key'], configuration['lisa_ssl_crt'])

        # Initialize web factory
        webService = internet.SSLServer(configuration['lisa_web_port'], server.Site(root), webAuthContextFactory)
    else:
        # Initialize factories
        engineService = internet.TCPServer(configuration['lisa_port'], libs.ClientFactorySingleton.get())
        webService = internet.TCPServer(configuration['lisa_web_port'], server.Site(root))

    # Create the websocket factory
    if configuration['enable_secure_mode']:
        socketfactory = WebSocketServerFactory("wss://" + configuration['lisa_url'] + ":" +
                                               str(configuration['lisa_web_port']), debug = False)

    else:
        # Initialize factories
        socketfactory = WebSocketServerFactory("ws://" + configuration['lisa_url'] + ":" +
                                               str(configuration['lisa_web_port']), debug = False)
    socketfactory.protocol = libs.WebSocketProtocol
    socketresource = WebSocketResource(socketfactory)
    root.putChild("websocket", socketresource)

    # Add services to application
    engineService.setServiceParent(multi)
    webService.setServiceParent(multi)

    return multi

# --------------------- End of service.py  ---------------------
