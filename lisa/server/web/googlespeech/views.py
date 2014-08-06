from django.http import HttpResponse
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from lisa.server.config_manager import ConfigManager

configuration = ConfigManager.getConfiguration()

from pkg_resources import get_distribution

@login_required()
def index(request):
    if configuration['enable_secure_mode']:
        websocket = 'wss'
    else:
        websocket = 'ws'
    context = {
        'websocket': websocket,
        'lang': configuration['lang_short'],
        'server_version': get_distribution('lisa-server').version
    }
    return render(request, 'googlespeech/index.html', context)
