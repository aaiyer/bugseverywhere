# :vim: filetype=make : -*- makefile; coding: utf-8; -*-

# doc/module.mk
# Part of Bugs Everywhere, a distributed bug tracking system.
#
# Copyright (C) 2008-2009 Chris Ball <cjb@laptop.org>
# This is free software; you may copy, modify and/or distribute this work
# under the terms of the GNU General Public License, version 2 or later.
# No warranty expressed or implied. See the file COPYING for details.

# Makefile module for documentation

MODULE_DIR := doc

MANPAGES = be.1
manpage_files = $(patsubst %,${MODULE_DIR}/%,${MANPAGES})

GENERATED_FILES += ${manpage_files}


.PHONY: doc
doc: man

build: doc


.PHONY: man
man: ${manpage_files}

%.1: %.1.sgml
	docbook-to-man $< > $@
