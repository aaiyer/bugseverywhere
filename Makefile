#! /usr/bin/make -f
# -*- makefile; coding: utf-8 -*-

# Makefile
# Part of Bugs Everywhere, a distributed bug tracking system.
#
# Copyright © 2008 Ben Finney <ben+python@benfinney.id.au>
# This is free software; you may copy, modify and/or distribute this work
# under the terms of the GNU General Public License, version 2 or later.
# No warranty expressed or implied. See the file LICENSE for details.

# Makefile for Bugs Everywhere project

SHELL = /bin/bash
PATH = /usr/bin:/bin

# Variables that will be extended by module include files
GENERATED_FILES :=
CODE_MODULES :=
CODE_PROGRAMS :=

RM = rm


.PHONY: clean
clean:
	$(RM) -rf ${GENERATED_FILES}
