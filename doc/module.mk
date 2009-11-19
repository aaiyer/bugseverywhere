# :vim: filetype=make : -*- makefile; coding: utf-8; -*-

# doc/module.mk
# Part of Bugs Everywhere, a distributed bug tracking system.
#
# Copyright (C) 2008-2009 Chris Ball <cjb@laptop.org>
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
