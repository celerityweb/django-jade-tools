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
from django.db.models import get_app
from django.template import loader, RequestContext
from django.test import RequestFactory

from pyjade.ext.django.loader import Loader
from pyjade.ext.django.compiler import Compiler
from pyjade.utils import process

class DjangoJadeCompiler(object):

    INCLUDE_RE = re.compile(
        r'^(?P<indent>[\t ]*)include +(?P<included>[^ ]+) *$',
        re.MULTILINE)

    def __init__(self, app, url_map=None, base_context=None):
        self.app = app
        self.template_path = os.path.join(
            os.path.dirname(get_app(app).__file__), 'jade_templates')
        self.base_context = base_context

    @classmethod
    def preempt_url_patterns(cls, url_map):
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
            if viewname in url_map:
                url_mapped_view = url_map[viewname]
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
                # it is compilable.
                if not jade_file.endswith('.jade'):
                    logger.debug('Skipping %s - not a .jade file', jade_file)
                    continue
                base_file, _ = os.path.splitext(jade_file)
                json_file = '%s.json' % base_file
                if json_file not in files:
                    logger.debug('Skipping %s - no corresponding json file %s',
                                 jade_file, json_file)
                    continue
                template_path_base = os.path.relpath(path,
                                                     start=self.template_path)
                if template_path_base == '.':
                    template_path_base = ''
                yield {'base_file_name': base_file,
                       'path': path,
                       'template_path': template_path_base}

    def preprocess_includes(self, template_src):
        # Can't do finditer() here because the indices of matches change
        match = self.INCLUDE_RE.search(template_src)
        while match:
            base_indent, included_path = match.groups()
            included_path = os.path.normpath(
                os.path.join(os.getcwd(), included_path)).strip()
            logger.debug('Found include statement: base indent is "%s" and '
                         'included path is %s; pwd is %s', base_indent,
                         included_path, os.getcwd())
            if os.path.exists(included_path):
                included_src = open(included_path, 'r').read()
            elif os.path.exists("%s.jade" % included_path):
                included_src = open("%s.jade" % included_path, 'r').read()
            else:
                raise Exception("Include path doesn't exists")
            included_src = included_src.decode('utf8')
            if self.INCLUDE_RE.search(included_src):
                current_pwd = os.getcwd()
                logger.debug('Current working dir is %s - '
                             'changing relative to template', current_pwd)
                os.chdir(os.path.dirname(included_path))
                logger.debug('Now in %s to process %s', os.getcwd(),
                             included_path)
                included_src = self.preprocess_includes(included_src)
                os.chdir(current_pwd)
                logger.debug('Now back in %s', current_pwd)
            template_src = (
                template_src[0:match.start()] + base_indent +
                included_src.replace(u'\n', u'\n'+base_indent).rstrip() +
                template_src[match.end():]
            )
            match = self.INCLUDE_RE.search(template_src)
        return template_src


    def compile(self, base_file_name, path, template_path):
        jade_template_path = os.path.join(template_path,
                                          '%s.jade' % (base_file_name,))
        logger.debug('Working with jade template %s', jade_template_path)
        # Change the pwd to the template's location
        current_pwd = os.getcwd()
        os.chdir(path)
        # Hackery to allow for pre-processing the jade source
        jade_loader = Loader(
            ('django.template.loaders.filesystem.Loader',))
        tmpl_src, display_name = jade_loader.load_template_source(
            jade_template_path, [self.template_path,])
        if self.INCLUDE_RE.search(tmpl_src):
            tmpl_src = self.preprocess_includes(tmpl_src)
        # WHITESPACE! HUH! WHAAAAT IS IT GOOD FOR? ABSOLUTELY NOTHING!
        tmpl_src = u'\n'.join([line for line in tmpl_src.split('\n')
                               if line.strip()])
        origin = loader.make_origin(display_name,
                                    jade_loader.load_template_source,
                                    jade_template_path, None)
        if settings.DEBUG:
            logger.debug(
                'Template is: \n%s',
                '\n'.join(['%4d: %s' % (i, s)
                           for i, s in enumerate(tmpl_src.split('\n'))]))
        compiled_jade = process(tmpl_src, filename=jade_template_path,
                                compiler=Compiler)
        try:
            tmpl = loader.get_template_from_string(compiled_jade, origin,
                                                   jade_template_path)
        except Exception, e:
            logger.exception('Failed to compile Jade-derived HTML template:')
            logger.exception(
                '\n'.join(['%4d: %s' % (i, s)
                           for i, s in enumerate(compiled_jade.split('\n'))]))
            raise
        os.chdir(current_pwd)
        return compiled_jade

    def mock(self, base_file_name, path, template_path):
        html_template_path = os.path.join(self.app.replace('.', '/'),
                                          '%s.html' % (base_file_name,))
        json_file_path = os.path.join(path, '%s.json' % (base_file_name,))
        tmpl = loader.get_template(html_template_path)
        # We need to simulate request middleware but without short-circuiting
        # the response
        request_factory = RequestFactory()
        req = request_factory.get('/%s' % (html_template_path,),
                                  data={})
        handler = WSGIHandler()
        handler.load_middleware()
        for middleware_method in handler._request_middleware:
            middleware_method(req)
        # Render the template with a RequestContext
        ctx = RequestContext(req,
                             json.load(open(json_file_path)))
        logger.debug('Updating context with base context %s', self.base_context)
        ctx.update(self.base_context)
        return tmpl.render(ctx)






