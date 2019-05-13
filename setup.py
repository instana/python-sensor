# coding: utf-8
from distutils.version import LooseVersion

from setuptools import find_packages, setup


def check_setuptools():
    import pkg_resources
    st_version = pkg_resources.get_distribution('setuptools').version
    if LooseVersion(st_version) < LooseVersion('20.2.2'):
        exit('The Instana sensor requires a newer verion of `setuptools` (>=20.2.2).\n'
             'Please run `pip install --upgrade setuptools` to upgrade. \n'
             '  and then try the install again.\n'
             'Also:\n'
             '  `pip show setuptools` - shows the current version\n'
             '  To see the setuptool releases: \n'
             '    https://setuptools.readthedocs.io/en/latest/history.html')


check_setuptools()

setup(name='instana',
      version='1.11.0',
      url='https://www.instana.com/',
      project_urls={
          'CI: Travis': 'https://travis-ci.org/instana/python-sensor',
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
      long_description="The instana package collects and reports Python metrics and distributed \
traces to your Instana dashboard.",
      zip_safe=False,
      install_requires=['autowrapt>=1.0',
                        'basictracer>=3.0.0',
                        'certifi>=2018.4.16',
                        'fysom>=2.1.2',
                        'opentracing>=2.0.0',
                        'requests>=2.8.0',
                        'urllib3>=1.18.1'],
      entry_points={
                    'instana':  ['string = instana:load'],
                    'flask':    ['flask = instana.flaskana:hook'],
                    'runtime':  ['string = instana:load'],  # deprecated: use same as 'instana'
                    'django':   ['string = instana:load'],  # deprecated: use same as 'instana'
                    'django19': ['string = instana:load'],  # deprecated: use same as 'instana'
                    },
      extras_require={
        'test': [
            'aiohttp>=3.5.4;python_version>="3.5"',
            'asynqp>=0.4;python_version>="3.5"',
            'django>=1.11,<2.2',
            'nose>=1.0',
            'flask>=0.12.2',
            'lxml>=3.4',
            'mock>=2.0.0',
            'MySQL-python>=1.2.5;python_version<="2.7"',
            'psycopg2>=2.7.1',
            'pyOpenSSL>=16.1.0;python_version<="2.7"',
            'pytest>=3.0.1',
            'redis<3.0.0',
            'requests>=2.17.1',
            'sqlalchemy>=1.1.15',
            'spyne>=2.9,<=2.12.14',
            'suds-jurko>=0.6',
            'tornado>=4.5.3,<6.0',
            'urllib3[secure]>=1.15'
        ],
      },
      test_suite='nose.collector',
      keywords=['performance', 'opentracing', 'metrics', 'monitoring', 'tracing', 'distributed-tracing'],
      classifiers=[
        'Development Status :: 5 - Production/Stable',
        'Framework :: Django',
        'Framework :: Flask',
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
