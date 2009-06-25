#! /usr/bin/make -f
# :vim: filetype=make : -*- makefile; coding: utf-8; -*-

# Makefile
# Part of Bugs Everywhere, a distributed bug tracking system.
#
# Copyright © 2008 Ben Finney <ben+python@benfinney.id.au>
# This is free software; you may copy, modify and/or distribute this work
# under the terms of the GNU General Public License, version 2 or later.
# No warranty expressed or implied. See the file COPYING for details.

# Makefile for Bugs Everywhere project

SHELL = /bin/bash
PATH = /usr/bin:/bin

# Directories with semantic meaning
DOC_DIR := doc

# Variables that will be extended by module include files
GENERATED_FILES := libbe/_version.py build
CODE_MODULES :=
CODE_PROGRAMS :=

# List of modules (directories) that comprise our 'make' project
MODULES += ${DOC_DIR}

RM = rm

PREFIX = ${HOME}
INSTALL_OPTIONS = "--prefix=${PREFIX}"


.PHONY: all
all: build

# Include the make data for each module
include $(patsubst %,%/module.mk,${MODULES})


.PHONY: build
build: libbe/_version.py
	python setup.py build

.PHONY: install
install: doc build
	python setup.py install ${INSTALL_OPTIONS}
	cp -v xml/* ${PREFIX}/bin


.PHONY: clean
clean:
	$(RM) -rf ${GENERATED_FILES}

libbe/_version.py:
	bzr version-info --format python > $@
