# coding: utf-8
import sys
from os import path
from distutils.version import LooseVersion
from setuptools import find_packages, setup

VERSION = '1.25.1'

# Import README.md into long_description
pwd = path.abspath(path.dirname(__file__))

if sys.version_info[0] > 2:
    with open(path.join(pwd, 'README.md'), encoding='utf-8') as f:
        long_description = f.read()
else:
    with open(path.join(pwd, 'README.md')) as f:
        long_description = f.read()


def check_setuptools():
    """ Validate that we have min version required of setuptools """
    import pkg_resources
    st_version = pkg_resources.get_distribution('setuptools').version
    if LooseVersion(st_version) < LooseVersion('20.2.2'):
        exit('The Instana sensor requires a newer verion of `setuptools` (>=20.2.2).\n'
             'Please run `pip install --upgrade setuptools` to upgrade. \n'
             '  and then try the install again.\n'
             'Also:\n'
             '  `pip show setuptools` - shows the current version\n'
             '  To see the setuptools releases: \n'
             '    https://setuptools.readthedocs.io/en/latest/history.html')


check_setuptools()

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
      packages=find_packages(exclude=['tests', 'examples']),
      long_description=long_description,
      long_description_content_type='text/markdown',
      zip_safe=False,
      install_requires=['autowrapt>=1.0',
                        'basictracer>=3.0.0',
                        'certifi>=2018.4.16',
                        'fysom>=2.1.2',
                        'opentracing>=2.0.0',
                        'requests>=2.8.0',
                        'six>=1.12.0',
                        'urllib3>=1.18.1'],
      entry_points={
                    'instana':  ['string = instana:load'],
                    'flask':    ['string = instana:load'],  # deprecated: use same as 'instana'
                    'runtime':  ['string = instana:load'],  # deprecated: use same as 'instana'
                    'django':   ['string = instana:load'],  # deprecated: use same as 'instana'
                    'django19': ['string = instana:load'],  # deprecated: use same as 'instana'
                    },
      extras_require={
          'test-gevent': [
              'flask>=0.12.2',
              'gevent>=1.4.0',
              'mock>=2.0.0',
              'nose>=1.0',
              'pyramid>=1.2',
              'pytest>=4.6',
              'urllib3[secure]>=1.15'
          ],
          'test-cassandra': [
              'cassandra-driver==3.20.2',
              'mock>=2.0.0',
              'nose>=1.0',
              'pytest>=4.6',
              'urllib3[secure]>=1.15'
          ],
          'test': [
              'aiohttp>=3.5.4;python_version>="3.5"',
              'asynqp>=0.4;python_version>="3.5"',
              'celery>=4.1.1',
              'couchbase==2.5.9',
              'django>=1.11,<2.2',
              'nose>=1.0',
              'flask>=0.12.2',
              'grpcio>=1.18.0',
              'lxml>=3.4',
              'mock>=2.0.0',
              'mysqlclient>=1.3.14;python_version>="3.5"',
              'MySQL-python>=1.2.5;python_version<="2.7"',
              'PyMySQL[rsa]>=0.9.1',
              'pyOpenSSL>=16.1.0;python_version<="2.7"',
              'psycopg2>=2.7.1',
              'pymongo>=3.7.0',
              'pyramid>=1.2',
              'pytest>=4.6',
              'redis>3.0.0',
              'requests>=2.17.1',
              'sqlalchemy>=1.1.15',
              'spyne>=2.9,<=2.12.14',
              'suds-jurko>=0.6',
              'tornado>=4.5.3,<6.0',
              'urllib3[secure]>=1.15'
          ],
      },
      test_suite='nose.collector',
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
          'Programming Language :: Python :: 2.7',
          'Programming Language :: Python :: 3',
          'Programming Language :: Python :: 3.4',
          'Programming Language :: Python :: 3.5',
          'Programming Language :: Python :: 3.6',
          'Topic :: Internet :: WWW/HTTP :: WSGI :: Middleware',
          'Topic :: System :: Monitoring',
          'Topic :: System :: Networking :: Monitoring',
          'Topic :: Software Development :: Libraries :: Python Modules'])
