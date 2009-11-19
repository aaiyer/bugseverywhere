#! /usr/bin/make -f
# :vim: filetype=make : -*- makefile; coding: utf-8; -*-

# Makefile
# Part of Bugs Everywhere, a distributed bug tracking system.
#
# Copyright (C) 2008-2009 Ben Finney <benf@cybersource.com.au>
#                         Chris Ball <cjb@laptop.org>
#                         Gianluca Montecchi <gian@grys.it>
#                         W. Trevor King <wking@drexel.edu>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.

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

#PREFIX = /usr/local
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
#cp -v interfaces/xml/* ${PREFIX}/bin
#cp -v interfaces/email/catmutt ${PREFIX}/bin


.PHONY: clean
clean:
	$(RM) -rf ${GENERATED_FILES}

.PHONY: libbe/_version.py
libbe/_version.py:
	bzr version-info --format python > $@
