# -*- coding: utf-8 -*-
from __future__ import absolute_import

import logging

logger = logging.getLogger(__name__)

import os
import json
from optparse import make_option

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.core.files.storage import FileSystemStorage
from django.core.files.base import ContentFile
from django.db.models import get_app

from jade_tools import compiler

class Command(BaseCommand):
    args = '<subcommand>'
    help = 'Execute a jade-tools command on the current Django project.'
    option_list = BaseCommand.option_list + (
        make_option(
            '--app',
            action='store',
            dest='app',
            default='',
            help='The name of the app containing the Jade templates in its '
                 '"jade_templates" directory. If not specified, all apps are '
                 'searched for "jade_templates" directories.'),
        make_option(
            '--url-map',
            action='store',
            dest='url_map',
            default='',
            help='The file containing a map of URL pattern names to paths of '
                 'the appropriate HTML files during mocking'),
        make_option(
            '--base-context',
            action='store',
            dest='base_context',
            default='',
            help='The file containing a JSON fixture to include in the '
                 'template context of all Jade templates rendered during '
                 'mocking'
        ),
        make_option(
            '--output-prefix',
            action='store',
            dest='output_prefix',
            default='',
            help='A path stub to prepend to outputted HTML files during mocking'
        )
    )

    def handle_compile(self, app, **other_options):
        app_list = [app] if app else settings.INSTALLED_APPS
        if [a for a in app_list if a not in settings.INSTALLED_APPS]:
            raise CommandError('Invalid app specified. Only installed apps may '
                               'be used.')
        for app in app_list:
            html_path = os.path.join(
                os.path.dirname(get_app(app).__file__), 'templates',
                app.replace('.', '/'))
            compiler_obj = compiler.DjangoJadeCompiler(app)
            for tmpl_data in compiler_obj.find_compilable_jade_templates():
                logger.debug('Template data: %s', tmpl_data)
                html = compiler_obj.compile(**tmpl_data)
                logger.info('Saving HTML file %s', html_path)
                if not os.path.exists(html_path):
                    os.makedirs(html_path)
                open(os.path.join(html_path,
                                  '%s.html' % (tmpl_data['base_file_name'],)),
                     'w').write(html.encode('utf8') if isinstance(html, unicode) else html)

    def handle_mock(self, app, url_map, output_prefix, base_context,
                    **other_options):
        app_list = [app] if app else settings.INSTALLED_APPS
        if [a for a in app_list if a not in settings.INSTALLED_APPS]:
            raise CommandError('Invalid app specified. Only installed apps may '
                               'be used.')
        if url_map and not os.path.exists(url_map):
            raise CommandError('No such URL map at that path.')
        if base_context and not os.path.exists(base_context):
            raise CommandError('No such URL map at that path.')
        if '..' in output_prefix.split('/') or output_prefix.startswith('/'):
            raise CommandError('Treachery! No root paths or parent navigation '
                               'when specifying an output prefix, you clever '
                               'devil.')
        compiler.DjangoJadeCompiler.preempt_url_patterns(
            json.load(open(url_map)) if url_map else {})
        for app in app_list:
            self.handle_compile(app)
            compiler_obj = compiler.DjangoJadeCompiler(
                app,
                base_context=(json.load(open(base_context))
                              if base_context else {}))
            for tmpl_data in compiler_obj.find_compilable_jade_templates():
                logger.debug('Template data: %s', tmpl_data)
                html = compiler_obj.mock(**tmpl_data)
                faux_file = ContentFile(html)
                html_path = os.path.join(output_prefix,
                                         tmpl_data['template_path'],
                                         '%s.html' % tmpl_data['base_file_name'])
                logger.info('Saving HTML file %s', html_path)
                storage_obj = FileSystemStorage(location=settings.STATIC_ROOT)
                storage_obj.save(html_path, faux_file)

    def handle(self, *args, **options):
        if len(args) != 1:
            raise CommandError('Invalid number of arguments.')
        subcommand = args[0]
        try:
            subcommand_fn = getattr(self, 'handle_%s' % subcommand)
        except AttributeError:
            raise CommandError('Invalid subcommand specified.')
        subcommand_fn(**options)
