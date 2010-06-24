#!/usr/bin/env python

from distutils.core import setup
from libbe import _version

rev_id = _version.version_info["revision"]
rev_date = _version.version_info["date"]

setup(
    name='Bugs Everywhere',
    version=rev_date,
    description='Bugtracker supporting distributed revision control',
    url='http://bugseverywhere.org/',
    packages=['libbe',
              'libbe.command',
              'libbe.storage',
              'libbe.storage.util',
              'libbe.storage.vcs',
              'libbe.ui',
              'libbe.ui.util',
              'libbe.util'],
    scripts=['be'],
    data_files=[
        ('share/man/man1', ['doc/man/be.1']),
        ]
    )
