# coding: utf-8
# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2016

import os
from os import path

from setuptools import find_packages, setup

from instana.version import VERSION

os.environ["INSTANA_DISABLE"] = "true"

# Import README.md into long_description
pwd = path.abspath(path.dirname(__file__))

with open(path.join(pwd, "README.md"), encoding="utf-8") as f:
    long_description = f.read()


setup(
    name="instana",
    version=VERSION,
    url="https://www.instana.com/",
    project_urls={
        "CI: CircleCI": "https://circleci.com/gh/instana/python-sensor",
        "Documentation": "https://docs.instana.io/ecosystem/python/",
        "GitHub: issues": "https://github.com/instana/python-sensor/issues",
        "GitHub: repo": "https://github.com/instana/python-sensor",
        "Support": "https://www.ibm.com/mysupport",
    },
    license="MIT",
    author="Instana Inc.",
    author_email="peter.lombardo@instana.com",
    description="🐍 Python Distributed Tracing & Metrics Sensor for Instana",
    options={"bdist_wheel": {"universal": True}},
    packages=find_packages(exclude=["tests", "examples"]),
    long_description=long_description,
    long_description_content_type="text/markdown",
    zip_safe=False,
    python_requires=">=3.8",
    install_requires=[
        "autowrapt>=1.0",
        "fysom>=2.1.2",
        "protobuf<5.0.0",
        "requests>=2.6.0",
        "six>=1.12.0",
        "urllib3>=1.26.5",
        "opentelemetry-api>=1.23.0",
    ],
    entry_points={
        "instana": ["string = instana:load"],
        "flask": ["string = instana:load"],  # deprecated: use same as 'instana'
        "runtime": ["string = instana:load"],  # deprecated: use same as 'instana'
        "django": ["string = instana:load"],  # deprecated: use same as 'instana'
        "django19": ["string = instana:load"],  # deprecated: use same as 'instana'
    },
    keywords=[
        "performance",
        "opentelemetry",
        "metrics",
        "monitoring",
        "tracing",
        "distributed-tracing",
    ],
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Framework :: Django",
        "Framework :: Flask",
        "Framework :: Pyramid",
        "Intended Audience :: Developers",
        "Intended Audience :: Information Technology",
        "Intended Audience :: Science/Research",
        "Intended Audience :: System Administrators",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Internet :: WWW/HTTP :: WSGI :: Middleware",
        "Topic :: System :: Monitoring",
        "Topic :: System :: Networking :: Monitoring",
        "Topic :: Software Development :: Libraries :: Python Modules",
    ],
)
