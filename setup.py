from setuptools import setup, find_packages

setup(name='instana',
      version='0.0.1',
      url='https://github.com/instana/python-sensor',
      license='MIT',
      author='Instana Inc.',
      author_email='pavlo.baron@instana.com',
      description='Metrics sensor and trace collector for Instana',
      packages=find_packages(exclude=['tests', 'examples']),
      long_description=open('README.md').read(),
      zip_safe=False,
      setup_requires=['nose>=1.0',
                      'fysom>=2.1.2'],
      test_suite='nose.collector')
