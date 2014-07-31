# -*- coding: utf-8 -*-
from __future__ import absolute_import

import logging

logger = logging.getLogger(__name__)

from django.conf.urls import include, url, patterns

from .views import TestView

urlpatterns = patterns(
    '',
    url(r'^testview/(?P<arg1>\d+)/(?P<arg2>\d+)/', TestView.as_view(),
        name='test-view'),
)
