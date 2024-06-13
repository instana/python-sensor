# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2020

import importlib
import os
import unittest
import socket

import gevent
from gevent import monkey
from instana import apply_gevent_monkey_patch


class TestGEventAutoTrace(unittest.TestCase):
    def setUp(self):
        # Ensure that the test suite is operational even when Django is installed
        # but not running or configured
        os.environ['DJANGO_SETTINGS_MODULE'] = ''

        self.default_patched_modules = ('socket', 'time', 'select', 'os',
                'threading', 'ssl', 'subprocess', 'signal', 'queue',)

    def tearDown(self):
        if os.environ.get('INSTANA_GEVENT_MONKEY_OPTIONS'):
            os.environ.pop('INSTANA_GEVENT_MONKEY_OPTIONS')

        # Clean up after gevent monkey patches, by restore from the saved dict
        for modname in monkey.saved.keys():
            try:
                mod = __import__(modname)
                importlib.reload(mod)
                for key in monkey.saved[modname].keys():
                    setattr(mod, key, monkey.saved[modname][key])
            except ImportError:
                pass
        monkey.saved = {}


    def test_default_patch_all(self):
        apply_gevent_monkey_patch()
        for module_name in self.default_patched_modules:
            self.assertTrue(monkey.is_module_patched(module_name),
                            f"{module_name} is not patched")

    def test_instana_monkey_options_only_time(self):
        os.environ['INSTANA_GEVENT_MONKEY_OPTIONS'] = (
                'time,no-socket,no-select,no-os,no-select,no-threading,no-os,'
                'no-ssl,no-subprocess,''no-signal,no-queue')
        apply_gevent_monkey_patch()

        self.assertTrue(monkey.is_module_patched('time'), "time module is not patched")
        not_patched_modules = (m for m in self.default_patched_modules if m not in ('time', 'threading'))

        for module_name in not_patched_modules:
            self.assertFalse(monkey.is_module_patched(module_name),
                             f"{module_name} is patched, when it shouldn't be")


    def test_instana_monkey_options_only_socket(self):
        os.environ['INSTANA_GEVENT_MONKEY_OPTIONS'] = (
                '--socket, --no-time, --no-select, --no-os, --no-queue, --no-threading,'
                '--no-os, --no-ssl, no-subprocess, --no-signal, --no-select,')
        apply_gevent_monkey_patch()

        self.assertTrue(monkey.is_module_patched('socket'), "socket module is not patched")
        not_patched_modules = (m for m in self.default_patched_modules if m not in ('socket', 'threading'))

        for module_name in not_patched_modules:
            self.assertFalse(monkey.is_module_patched(module_name),
                             f"{module_name} is patched, when it shouldn't be")

