from setuptools import setup, find_packages

setup(name='instana',
      version='0.0.1',
      url='https://github.com/instana/python-sensor',
      license='MIT',
      author='Instana Inc.',
      author_email='peter.lombardo@instana.com',
      description='Metrics sensor and trace collector for Instana',
      packages=find_packages(exclude=['tests', 'examples']),
      long_description=open('README.md').read(),
      zip_safe=False,
      setup_requires=['nose>=1.0',
                      'fysom>=2.1.2',
                      'opentracing>=1.2.1,<1.3',
                      'basictracer>=2.2.0',
                      'psutil>=5.1.3'],
      test_suite='nose.collector',
      keywords=['performance', 'opentracing', 'metrics', 'monitoring'])
