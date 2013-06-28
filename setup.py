#!/usr/bin/env python

import setuptools # so we can `./setup.py develop`
from distutils.core import setup
import os.path

from libbe import version


_this_dir = os.path.dirname(__file__)

rev_id = version.version_info['revision']
rev_date = version.version_info['date']

data_files = []

man_path = os.path.join('doc', 'man', 'be.1')
if os.path.exists(man_path):
    data_files.append(('share/man/man1', [man_path]))

setup(
    name='bugs-everywhere',
    version='{}'.format(version.version()),
    author='W. Trevor King',
    author_email='wking@tremily.us',
    maintainer='Thomas Levine',
    maintainer_email='wildebeest@thomaslevine.com',
    url='http://bugseverywhere.org/',
    download_url=(
        'http://downloads.bugseverywhere.org/releases/be-{}.tar.gz'.format(
            version.version())),
    license='GNU General Public License (GPL)',
    platforms=['all'],
    description='Bugtracker supporting distributed revision control',
    long_description=open(os.path.join(_this_dir, 'README'), 'r').read(),
    classifiers=[
        'Development Status :: 4 - Beta',
        'Environment :: Console',
        'Environment :: Web Environment',
        'Framework :: CherryPy',
        'Intended Audience :: Customer Service',
        'Intended Audience :: Developers',
        'Intended Audience :: End Users/Desktop',
        'License :: OSI Approved :: GNU General Public License (GPL)',
        'License :: OSI Approved :: GNU General Public License v2 (GPLv2)',
        'License :: OSI Approved :: GNU General Public License v2 or later (GPLv2+)',
        'License :: OSI Approved :: GNU General Public License v3 (GPLv3)'
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2.7',
        'Topic :: Software Development :: Bug Tracking',
        ],
    packages=['libbe',
              'libbe.command',
              'libbe.storage',
              'libbe.storage.util',
              'libbe.storage.vcs',
              'libbe.ui',
              'libbe.ui.util',
              'libbe.util'],
    scripts=['be'],
    data_files=data_files,
    requires=[
        'Jinja2 (>=2.6)',
        'CherryPy (>=3.2)',
        ]
    )
