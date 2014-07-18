# -*- coding: utf-8 -*-
from __future__ import absolute_import

import logging

logger = logging.getLogger(__name__)

import re
import os
import json

from django.conf import settings
from django.core.handlers.wsgi import WSGIHandler
from django.core import urlresolvers
from django.template import loader, RequestContext
from django.test import RequestFactory

from pyjade.ext.django.loader import Loader
from pyjade.ext.django.compiler import Compiler
from pyjade.utils import process

class DjangoJadeCompiler(object):

    INCLUDE_RE = re.compile(
        r'^(?P<indent>[\t ]*)include +(?P<included>[^ ]+) *$',
        re.MULTILINE)

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

    def preprocess_includes(self, template_src):
        # Can't do finditer() here because the indices of matches change
        match = self.INCLUDE_RE.search(template_src)
        while match:
            base_indent, included_path = match.groups()
            logger.debug('Found include statement: base indent is "%s" and '
                         'included path is %s', base_indent, included_path)
            if os.path.exists(included_path):
                included_src = open(included_path, 'r').read()
            elif os.path.exists("%s.jade" % included_path):
                included_src = open("%s.jade" % included_path, 'r').read()
            else:
                raise Exception("Include path doesn't exists")
            if self.INCLUDE_RE.search(included_src):
                current_pwd = os.getcwd()
                os.chdir(os.path.dirname('./'+included_src))
                included_src = self.preprocess_includes(included_src)
                os.chdir(current_pwd)
            template_src = (
                template_src[0:match.start()] + base_indent +
                included_src.replace('\n', '\n'+base_indent).rstrip() +
                template_src[match.end():]
            )
            match = self.INCLUDE_RE.search(template_src)
        return template_src


    def render_jade_with_json(self, jade_template_path, json_file_path,
                              template_path_base, base_file):
        logger.debug('Working with jade template %s', jade_template_path)
        # Change the pwd to the template's location
        current_pwd = os.getcwd()
        os.chdir(os.path.join(self.template_path, template_path_base))
        # Hackery to allow for pre-processing the jade source
        jade_loader = Loader(
            ('django.template.loaders.filesystem.Loader',
             'django.template.loaders.app_directories.Loader'))
        tmpl_src, display_name = jade_loader.load_template_source(
            jade_template_path)
        if self.INCLUDE_RE.search(tmpl_src):
            tmpl_src = self.preprocess_includes(tmpl_src)
        origin = loader.make_origin(display_name,
                                    jade_loader.load_template_source,
                                    jade_template_path, None)
        compiled_jade = process(tmpl_src, filename=jade_template_path,
                                compiler=Compiler)
        tmpl = loader.get_template_from_string(compiled_jade, origin,
                                               jade_template_path)
        if settings.DEBUG:
            logger.debug(
                'Template is: %s', tmpl_src)
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
        ctx = RequestContext(req,
                             json.load(open(os.path.basename(json_file_path))))
        # Change the pwd back
        os.chdir(current_pwd)
        return tmpl.render(ctx)






