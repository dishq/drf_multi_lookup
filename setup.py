#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Setup Script helps to build the project
"""
import os
import re
from io import open

from setuptools import setup


def get_version(package):
    """
    Return package version as listed in `__version__` in `init.py`.
    """
    init_py = open(os.path.join(package, '__init__.py')).read()
    return re.search("__version__ = ['\"]([^'\"]+)['\"]", init_py).group(1)


version = get_version('drf_multi_lookup')
with open('README.md') as f:
    long_description = f.read()


setup(
    name='drf-multi-lookup',
    version=version,
    url='http://github.com/dishq/drf_multi_lookup',
    license='MIT',
    description=(
        'Multi Field Lookup over pk for DRF Nested Serializers'),
    long_description=long_description,
    long_description_content_type='text/markdown',
    keywords=('drf restframework rest_framework django_rest_framework'
              ' serializers drf_multi_lookup'),
    author='Spoonshot',
    author_email='drfmultilookup@spoonshot.com',
    packages=['drf_multi_lookup'],
    zip_safe=False,
    classifiers=[
        'Development Status :: 4 - Beta',
        'Environment :: Web Environment',
        'Framework :: Django',
        'Framework :: Django :: 1.9',
        'Framework :: Django :: 1.10',
        'Framework :: Django :: 1.11',
        'Framework :: Django :: 2.0',
        'Framework :: Django :: 2.1',
        'Framework :: Django :: 2.2',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Topic :: Internet :: WWW/HTTP',
    ]
)
