DRF Multi Lookup
================
[![Build Status](https://travis-ci.org/dishq/drf-multi-lookup.svg?branch=master)](https://travis-ci.org/dishq/drf-multi-lookup)
[![codecov](https://codecov.io/gh/dishq/drf-multi-lookup/branch/master/graph/badge.svg)](https://codecov.io/gh/dishq/drf-multi-lookup)
[![pypi](https://img.shields.io/pypi/v/drf-multi-lookup.svg)](https://pypi.python.org/pypi/drf-multi-lookup)
[![pyversions](https://img.shields.io/pypi/pyversions/drf-multi-lookup.svg)](https://pypi.python.org/pypi/drf-multi-lookup)


This is a package written on top of
[drf-writable-nested](https://github.com/beda-software/drf-writable-nested)
inorder to make calls to serializer without knowing exact Primary Key
but using candidate keys.

Requirements
============

- Python (2.7, 3.5, 3.6, 3.7)
- Django (1.9, 1.10, 1.11, 2.0, 2.1, 2.2)
- djangorestframework (3.5+)
- drf-writable-nested (0.5.1)

Installation
============

```
pip install drf-multi-lookup
```


Development
===========


Deployment
==========

Change version in __init__.py

python setup.py sdist bdist_wheel

twine upload dist/*

Authors
=======
2020, Spoonshot
