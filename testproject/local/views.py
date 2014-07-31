# -*- coding: utf-8 -*-
from __future__ import absolute_import

import logging

logger = logging.getLogger(__name__)

import datetime, decimal

from django.contrib.auth.models import Permission
from django.views.generic import TemplateView

class TestObject(object):
    def has_args(self, foo):
        return False

    def has_no_args(self):
        return True

    def has_arg_with_default(self, default=True):
        return default

    @property
    def is_a_property(self):
        return True

    attr = True
    list_attr = range(1,20)
    dict_attr = {k: k for k in range(1,20)}

class TestView(TemplateView):
    template_name = 'does/not/exist/do/not/care.html'

    def get_context_data(self, **kwargs):
        context = super(TestView, self).get_context_data(**kwargs)
        context['list_arg'] = [1, 'a', True]
        context['dict_arg'] = {'nested': {'nested': {'nested': 'nested'}},
                               'decimal': decimal.Decimal('3.14159'),
                               'date': datetime.datetime.now()}
        context['too_many'] = range(1,100)
        context['object'] = TestObject()
        context['qs'] = Permission.objects.all()
        return context
