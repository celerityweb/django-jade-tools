# -*- coding: utf-8 -*-
from __future__ import absolute_import

import logging

logger = logging.getLogger(__name__)

import os
import json
from optparse import make_option

from django.core.management.base import BaseCommand, CommandError
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile

from jade_tools import compiler

class Command(BaseCommand):
    args = '<subcommand>'
    help = 'Execute a jade-tools command on the current Django project.'
    option_list = BaseCommand.option_list + (
        make_option(
            '--template-path',
            action='store',
            dest='template_path',
            default='',
            help='The file path containing the Jade templates to act upon'),
        make_option(
            '--url-map',
            action='store',
            dest='url_map',
            default='',
            help='The file containing a map of URL pattern names to paths of '
                 'the appropriate static HTML.'),
        )

    def handle_compile(self, template_path, url_map, **other_options):
        if not template_path or not os.path.exists(template_path):
            raise CommandError('Invalid template path specified.')
        if url_map and not os.path.exists(url_map):
            raise CommandError('No such URL map at that path.')
        compiler_obj = compiler.DjangoJadeCompiler(template_path,
                                                   json.load(open(url_map)))
        compiler_obj.preempt_url_patterns()
        for tmpl_data in compiler_obj.find_compileable_jade_templates():
            logger.debug('Template data: %s', tmpl_data)
            html = compiler_obj.render_jade_with_json(**tmpl_data)
            faux_file = ContentFile(html)
            html_path = '%s.html' % os.path.join(
                tmpl_data['template_path_base'],
                tmpl_data['base_file'])
            logger.info('Saving HTML file %s', html_path)
            default_storage.save(html_path, faux_file)

    def handle(self, *args, **options):
        if len(args) != 1:
            raise CommandError('Invalid number of arguments.')
        subcommand = args[0]
        try:
            subcommand_fn = getattr(self, 'handle_%s' % subcommand)
        except AttributeError:
            raise CommandError('Invalid subcommand specified.')
        subcommand_fn(**options)
