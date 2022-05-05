# coding: utf-8
# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2016

import os
import sys
from os import path

from pkg_resources import get_distribution
from setuptools import find_packages, setup

os.environ["INSTANA_DISABLE"] = "true"

# pylint: disable=wrong-import-position
from instana.version import VERSION

# Import README.md into long_description
pwd = path.abspath(path.dirname(__file__))

with open(path.join(pwd, 'README.md'), encoding='utf-8') as f:
    long_description = f.read()


setup(name='instana',
      version=VERSION,
      url='https://www.instana.com/',
      project_urls={
          'CI: CircleCI': 'https://circleci.com/gh/instana/python-sensor',
          'Documentation': 'https://docs.instana.io/ecosystem/python/',
          'GitHub: issues': 'https://github.com/instana/python-sensor/issues',
          'GitHub: repo': 'https://github.com/instana/python-sensor',
          'Support': 'https://support.instana.com',
      },
      license='MIT',
      author='Instana Inc.',
      author_email='peter.lombardo@instana.com',
      description='🐍 Python Distributed Tracing & Metrics Sensor for Instana',
      options={"bdist_wheel": {"universal": True}},
      packages=find_packages(exclude=['tests', 'examples']),
      long_description=long_description,
      long_description_content_type='text/markdown',
      zip_safe=False,
      install_requires=['autowrapt>=1.0',
                        'basictracer>=3.1.0',
                        'certifi>=2018.4.16',
                        'fysom>=2.1.2',
                        'opentracing>=2.3.0',
                        'protobuf<5.0.0',
                        'requests>=2.6.0',
                        'six>=1.12.0',
                        'urllib3<1.27,>=1.26.5',],
      entry_points={
                    'instana':  ['string = instana:load'],
                    'flask':    ['string = instana:load'],  # deprecated: use same as 'instana'
                    'runtime':  ['string = instana:load'],  # deprecated: use same as 'instana'
                    'django':   ['string = instana:load'],  # deprecated: use same as 'instana'
                    'django19': ['string = instana:load'],  # deprecated: use same as 'instana'
                    },
      keywords=['performance', 'opentracing', 'metrics', 'monitoring',
                'tracing', 'distributed-tracing'],
      classifiers=[
          'Development Status :: 5 - Production/Stable',
          'Framework :: Django',
          'Framework :: Flask',
          'Framework :: Pyramid',
          'Intended Audience :: Developers',
          'Intended Audience :: Information Technology',
          'Intended Audience :: Science/Research',
          'Intended Audience :: System Administrators',
          'License :: OSI Approved :: MIT License',
          'Operating System :: OS Independent',
          'Programming Language :: Python',
          'Programming Language :: Python :: 3',
          'Programming Language :: Python :: 3.7',
          'Programming Language :: Python :: 3.8',
          'Programming Language :: Python :: 3.9',
          'Programming Language :: Python :: 3.10',
          'Topic :: Internet :: WWW/HTTP :: WSGI :: Middleware',
          'Topic :: System :: Monitoring',
          'Topic :: System :: Networking :: Monitoring',
          'Topic :: Software Development :: Libraries :: Python Modules'])
