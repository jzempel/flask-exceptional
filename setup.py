"""
Flask-Exceptional
-----------------

Adds `Exceptional`_ support to Flask applications.

Links
`````

* `documentation <http://packages.python.org/Flask-Exceptional>`_
* `development version
  <http://github.com/jzempel/flask-exceptional/zipball/master#egg=Flask-Exceptional-dev>`_

.. _Exceptional: http://www.exceptional.io/

"""

from setuptools import setup
from sys import version_info

if version_info < (2, 6):
    install_requires = ['Flask', 'simplejson >= 1.9.1']
else:
    install_requires = ['Flask']

setup(
    name='Flask-Exceptional',
    version='0.4.8',
    url='http://github.com/jzempel/flask-exceptional',
    license='BSD',
    author='Jonathan Zempel',
    author_email='jzempel@gmail.com',
    description='Adds Exceptional support to Flask applications',
    long_description=__doc__,
    packages=['flaskext'],
    namespace_packages=['flaskext'],
    zip_safe=False,
    platforms='any',
    install_requires=install_requires,
    test_suite='tests',
    classifiers=[
        'Development Status :: 4 - Beta',
        'Environment :: Web Environment',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: BSD License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Topic :: Internet :: WWW/HTTP :: Dynamic Content',
        'Topic :: Software Development :: Libraries :: Python Modules'
    ]
)
