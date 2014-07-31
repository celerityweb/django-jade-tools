# -*- coding: utf-8 -*-
from __future__ import absolute_import

import logging

logger = logging.getLogger(__name__)

import contextlib
import inspect
import decimal
import itertools

from django.core.urlresolvers import reverse
from django.db import models
from django.db.models.query import QuerySet
from django.test.client import Client
from django.template.loader import BaseLoader

class BlankStringLoader(BaseLoader):
    is_usable = True

    def load_template_source(self, template_name, template_dirs=None):
        return u'', template_name

    def reset(self):
        pass

def repr_maybe(value):
    return repr(value) if not isinstance(value, basestring) else value

class ContextMaker(object):
    def __init__(self, view_name, args=[], kwargs={}, max_length=10,
                 max_depth=3):
        self.view_name = view_name
        self.args = args
        self.kwargs = kwargs
        self.max_length = max_length
        self.max_depth = max_depth

    @contextlib.contextmanager
    def shortcircuit_template_loader(self):
        """The template might not exist yet. We don't really care."""
        from django.template import loader
        actual_template_source_loaders = loader.template_source_loaders
        loader.template_source_loaders = [BlankStringLoader()]
        yield
        loader.template_source_loaders = actual_template_source_loaders

    def fake_request_to_get_context(self):
        with self.shortcircuit_template_loader():
            url = reverse(self.view_name, args=self.args, kwargs=self.kwargs)
            client = Client()
            response = client.get(url)
        return response.context_data

    def serialize_queryset(self, qs, depth):
        if depth:
            return [self.serialize_object(obj, depth-1)
                    for obj in qs[:self.max_length]]
        else:
            return repr_maybe(qs)

    def serialize_iterable(self, list_, depth):
        if depth:
            [self.serialize_foo(item, depth-1)
             for item in itertools.islice(list_, 0, self.max_length)]
        else:
            return [repr_maybe(item)
                    for item in itertools.islice(list_, 0, self.max_length)]

    def serialize_dict(self, dict_, depth):
        if depth:
            return {key: self.serialize_foo(value, depth-1)
                    for key, value in dict_.iteritems()}
        else:
            return {key: repr_maybe(value)
                    for key, value in dict.iteritems()}

    def serialize_object(self, obj, depth):
        # logger.debug("#####")
        # logger.debug('%s %s', type(obj), obj)
        to_return = {"": unicode(obj)}
        for attrname in [a for a in dir(obj) if not a.startswith('_')]:
            # logger.debug('attrname is %s', attrname)
            try:
                attr = getattr(obj, attrname)
            except AttributeError:
                continue
            # logger.debug('attr is %s %s', type(attr), attr)
            if not depth:
                to_return[attrname] = repr_maybe(attr)
                continue
            # only argumentless methods are allowed
            if isinstance(attr, type(self.serialize_object)):
                # logger.debug('instancemethod')
                # Common exceptions
                if (isinstance(obj, models.Model) and
                            attrname in ('save', 'delete', 'save_base',
                                         'clean', 'clean_fields',
                                         'full_clean')):
                    continue
                argspec = inspect.getargspec(attr)
                # logger.debug('%s', argspec)
                args, defaults = argspec.args, argspec.defaults
                if args and args[0] == 'self':
                    # this should always be the case.
                    args.pop(0)
                # logger.debug('%s %s', args, defaults)
                if args and (not defaults or len(defaults) < len(args)):
                    # This function requires arguments
                    # logger.debug('requires args')
                    continue
                try:
                    to_return[attrname] = self.serialize_foo(attr(),
                                                             depth-1)
                except Exception, e:
                    to_return[attrname] = repr_maybe(e)
            else:
                # logger.debug('not instancemethod')
                to_return[attrname] = self.serialize_foo(attr, depth-1)
        if len(to_return) == 1:
            return to_return.values()[0]
        return to_return

    def serialize_foo(self, foo, depth):
        if not depth:
            return repr_maybe(foo)
        # We don't decrement depth here, as this is merely a dispatch method
        if isinstance(foo, type):
            return repr_maybe(foo)
        if isinstance(foo, QuerySet):
            return self.serialize_queryset(foo, depth)
        if isinstance(foo, basestring):
            return foo
        if isinstance(foo, dict):
            return self.serialize_dict(foo, depth)
        if hasattr(foo, '__iter__'):
            return self.serialize_iterable(foo, depth)
        # Anything that isn't a primitive should be treated as an object
        if not isinstance(foo, (int, long, bool, float, complex,
                                decimal.Decimal, set)):
            return self.serialize_object(foo, depth)
        # Trust that our json serializer knows what to do here, then.
        return foo

    def serialize(self, context):
        return self.serialize_dict(context, depth=self.max_depth)

    def generate_context(self):
        context = self.fake_request_to_get_context()
        # We don't need the view in there...
        del context['view']
        return self.serialize(context)

