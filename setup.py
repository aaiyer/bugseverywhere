#!/usr/bin/env python

from distutils.core import setup

setup(
    name='Bugs Everywhere',
    version='0.0.193',
    description='Bugtracker built on distributed revision control',
    url='http://panoramicfeedback.com/opensource/',
    packages=['becommands', 'libbe'],
    scripts=['be'],
    )
