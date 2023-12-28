#!/usr/bin/env python
# -*- coding: utf-8 -*-

# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2018

import os
import sys
import time
import opentracing
import opentracing.ext.tags as ext
try:
    from django.urls import re_path
except ImportError:
    from django.conf.urls import url as re_path

from django.http import HttpResponse, Http404

filepath, extension = os.path.splitext(__file__)
os.environ['DJANGO_SETTINGS_MODULE'] = os.path.basename(filepath)
sys.path.insert(0, os.path.dirname(os.path.abspath(filepath)))

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SECRET_KEY = '^(myu#*^5v-9o$i-%6vnlwvy^#7&hspj$m3lcq#b$@__@+zd@c'
DEBUG = True
ALLOWED_HOSTS = ['testserver', 'localhost']
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
]
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]
ROOT_URLCONF = 'app_django'
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]
WSGI_APPLICATION = 'app_django.wsgi.application'
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': os.path.join(BASE_DIR, 'db.sqlite3'),
    }
}
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_L10N = True
USE_TZ = True
STATIC_URL = '/static/'


def index(request):
    return HttpResponse('Stan wuz here!')


def cause_error(request):
    raise Exception('This is a fake error: /cause-error')


def another(request):
    return HttpResponse('Stan wuz here!')


def not_found(request):
    raise Http404('Nothing here')


def complex(request):
    with opentracing.tracer.start_active_span('asteroid') as pscope:
        pscope.span.set_tag(ext.COMPONENT, "Python simple example app")
        pscope.span.set_tag(ext.SPAN_KIND, ext.SPAN_KIND_RPC_SERVER)
        pscope.span.set_tag(ext.PEER_HOSTNAME, "localhost")
        pscope.span.set_tag(ext.HTTP_URL, "/python/simple/one")
        pscope.span.set_tag(ext.HTTP_METHOD, "GET")
        pscope.span.set_tag(ext.HTTP_STATUS_CODE, 200)
        pscope.span.log_kv({"foo": "bar"})
        time.sleep(.2)

        with opentracing.tracer.start_active_span('spacedust', child_of=pscope.span) as cscope:
            cscope.span.set_tag(ext.SPAN_KIND, ext.SPAN_KIND_RPC_CLIENT)
            cscope.span.set_tag(ext.PEER_HOSTNAME, "localhost")
            cscope.span.set_tag(ext.HTTP_URL, "/python/simple/two")
            cscope.span.set_tag(ext.HTTP_METHOD, "POST")
            cscope.span.set_tag(ext.HTTP_STATUS_CODE, 204)
            cscope.span.set_baggage_item("someBaggage", "someValue")
            time.sleep(.1)

    return HttpResponse('Stan wuz here!')


def response_with_headers(request):
    response = HttpResponse(content_type='')
    response['X-Capture-This-Too'] = 'this too'
    return response


urlpatterns = [
    re_path(r'^$', index, name='index'),
    re_path(r'^cause_error$', cause_error, name='cause_error'),
    re_path(r'^another$', another),
    re_path(r'^not_found$', not_found, name='not_found'),
    re_path(r'^complex$', complex, name='complex'),
    re_path(r'^response_with_headers$', response_with_headers, name='response_with_headers')
]
