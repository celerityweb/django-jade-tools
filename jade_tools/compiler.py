# -*- coding: utf-8 -*-
from __future__ import absolute_import

import logging

logger = logging.getLogger(__name__)

import os
import json

from django.conf import settings
from django.core.handlers.wsgi import WSGIHandler
from django.core import urlresolvers
from django.template import loader, RequestContext
from django.test import RequestFactory

from pyjade.utils import process

class DjangoJadeCompiler(object):
    def __init__(self, template_path, url_map):
        self.template_path = template_path
        self.url_map = url_map

    def preempt_url_patterns(self):
        # Monkeypatch reverse for a clickable static demo
        super_reverse = urlresolvers.reverse
        def reverse(viewname, **kwargs):
            # Django rules say args or kwargs, not both
            view_args = kwargs.get('args')
            view_kwargs = kwargs.get('kwargs')
            # FIXME: I don't have a good solution for handling kwargs yet...
            if view_kwargs:
                raise NotImplementedError, "Reversing urlpatterns with kwargs " \
                                           "is not supported yet by " \
                                           "django-jade-tools"
            view_args = list(view_args)  # Use a copy of the original view args
            if viewname in self.url_map:
                url_mapped_view = self.url_map[viewname]
                while not isinstance(url_mapped_view, basestring):
                    next_arg = view_args.pop(0)
                    if unicode(next_arg) in url_mapped_view:
                        url_mapped_view = url_mapped_view[unicode(next_arg)]
                    elif '__default__' in url_mapped_view:
                        url_mapped_view = url_mapped_view['__default__']
                    else:
                        return super_reverse(viewname, **kwargs)
                return url_mapped_view
            return super_reverse(viewname, **kwargs)
        urlresolvers.reverse = reverse

    def find_compilable_jade_templates(self):
        for path, dirs, files in os.walk(self.template_path):
            logger.debug('Looking for jade templates in %s', path)
            for jade_file in files:
                # If we've got a .jade file with a corresponding .json file,
                # render it.
                if not jade_file.endswith('.jade'):
                    logger.debug('Skipping %s - not a .jade file', jade_file)
                    continue
                base_file, _ = os.path.splitext(jade_file)
                json_file = '%s.json' % base_file
                if json_file not in files:
                    logger.debug('Skipping %s - no corresponding json file %s',
                                 jade_file, json_file)
                    continue
                json_file_path = os.path.join(path,
                                              json_file)
                template_path_base = os.path.relpath(path,
                                                     start=self.template_path)
                if template_path_base == '.':
                    template_path_base = ''
                jade_template_path = os.path.join(template_path_base, jade_file)
                yield {'base_file': base_file,
                       'json_file_path': json_file_path,
                       'template_path_base': template_path_base,
                       'jade_template_path': jade_template_path}

    def render_jade_with_json(self, jade_template_path, json_file_path,
                              template_path_base, base_file):
        logger.debug('Working with jade template %s', jade_template_path)
        tmpl = loader.get_template(jade_template_path)
        if settings.DEBUG:
            logger.debug('Template is: %s',
                         process(open(os.path.join(self.template_path,
                                                   jade_template_path)).read()))
        # We need to simulate request middleware but without short-circuiting
        # the response
        request_factory = RequestFactory()
        req = request_factory.get('/%s/%s.html' % (template_path_base,
                                                   base_file),
                                  data={})
        handler = WSGIHandler()
        handler.load_middleware()
        for middleware_method in handler._request_middleware:
            middleware_method(req)
        # Render the template with a RequestContext
        ctx = RequestContext(req, json.load(open(json_file_path)))
        return tmpl.render(ctx)






