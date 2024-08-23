#!/usr/bin/env python
# -*- coding: utf-8 -*-

# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2018

import os
import sys
import time

try:
    from django.urls import re_path, include
except ImportError:
    from django.conf.urls import url as re_path

from django.http import HttpResponse, Http404
from opentelemetry.semconv.trace import SpanAttributes
from opentelemetry.trace import SpanKind

from instana.singletons import tracer

filepath, extension = os.path.splitext(__file__)
os.environ["DJANGO_SETTINGS_MODULE"] = os.path.basename(filepath)
sys.path.insert(0, os.path.dirname(os.path.abspath(filepath)))

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SECRET_KEY = "^(myu#*^5v-9o$i-%6vnlwvy^#7&hspj$m3lcq#b$@__@+zd@c"
DEBUG = True
ALLOWED_HOSTS = ["testserver", "localhost"]
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
]
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]
ROOT_URLCONF = "app_django"
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]
WSGI_APPLICATION = "app_django.wsgi.application"
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": os.path.join(BASE_DIR, "db.sqlite3"),
    }
}
AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_L10N = True
USE_TZ = True
STATIC_URL = "/static/"


def index(request):
    return HttpResponse("Stan wuz here!")


def cause_error(request):
    raise Exception("This is a fake error: /cause-error")


def induce_exception(request):
    raise Exception("This is a fake error: /induce-exception")


def another(request):
    return HttpResponse("Stan wuz here!")


def not_found(request):
    raise Http404("Nothing here")


def complex(request):
    with tracer.start_as_current_span("asteroid") as pspan:
        pspan.set_attribute("component", "Python simple example app")
        pspan.set_attribute("span.kind", SpanKind.CLIENT)
        pspan.set_attribute("peer.hostname", "localhost")
        pspan.set_attribute(SpanAttributes.HTTP_URL, "/python/simple/one")
        pspan.set_attribute(SpanAttributes.HTTP_METHOD, "GET")
        pspan.set_attribute(SpanAttributes.HTTP_STATUS_CODE, 200)
        pspan.add_event(name="complex_request", attributes={"foo": "bar"})
        time.sleep(0.2)

        with tracer.start_as_current_span("spacedust") as cspan:
            cspan.set_attribute("span.kind", SpanKind.CLIENT)
            cspan.set_attribute("peer.hostname", "localhost")
            cspan.set_attribute(SpanAttributes.HTTP_URL, "/python/simple/two")
            cspan.set_attribute(SpanAttributes.HTTP_METHOD, "POST")
            cspan.set_attribute(SpanAttributes.HTTP_STATUS_CODE, 204)
            time.sleep(0.1)

    return HttpResponse("Stan wuz here!")


def response_with_headers(request):
    headers = {"X-Capture-This-Too": "this too", "X-Capture-That-Too": "that too"}
    return HttpResponse("Stan wuz here with headers!", headers=headers)


extra_patterns = [
    re_path(r"^induce_exception$", induce_exception, name="induce_exception"),
]

urlpatterns = [
    re_path(r"^$", index, name="index"),
    re_path(r"^cause_error$", cause_error, name="cause_error"),
    re_path(r"^another$", another),
    re_path(r"^not_found$", not_found, name="not_found"),
    re_path(
        r"^response_with_headers$", response_with_headers, name="response_with_headers"
    ),
    re_path(r"^exception$", include(extra_patterns)),
    re_path(r"^complex$", complex, name="complex"),
]
