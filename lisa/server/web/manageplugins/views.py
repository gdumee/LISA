from django.shortcuts import render_to_response
from django.template import RequestContext
from models import Plugin
from django.contrib.auth.decorators import login_required
import requests, json
from lisa.server.web.weblisa.utils import method_restricted_to

from pkg_resources import get_distribution

@method_restricted_to('GET')
@login_required()
def list(request):
    plugins = []
    return render_to_response('list.html', {'Plugins': plugins,
                                            'server_version': get_distribution('lisa-server').version},
                              context_instance=RequestContext(request))
