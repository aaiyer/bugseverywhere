#!/usr/bin/python
#
# Copyright (C) 2009-2010 W. Trevor King <wking@drexel.edu>
#
# This file is part of Bugs Everywhere.
#
# Bugs Everywhere is free software; you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by the
# Free Software Foundation, either version 2 of the License, or (at your
# option) any later version.
#
# Bugs Everywhere is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Bugs Everywhere.  If not, see <http://www.gnu.org/licenses/>.

"""Automatically update copyright boilerplate.

This script is adapted from one written for `Bugs Everywhere`_. and
later modified for `Hooke`_ before returning to `Bugs Everywhere`_.

.. _Bugs Everywhere: http://bugseverywhere.org/
.. _Hooke: http://code.google.com/p/hooke/
"""

import difflib
import email.utils
import os
import os.path
import re
import sys
import time


PROJECT_INFO = {
    'project': 'Bugs Everywhere',
    'vcs': 'Git',
    }

# Break "copyright" into "copy" and "right" to avoid matching the
# REGEXP.
COPY_RIGHT_TEXT="""
This file is part of %(project)s.

%(project)s is free software; you can redistribute it and/or modify it
under the terms of the GNU General Public License as published by the
Free Software Foundation, either version 2 of the License, or (at your
option) any later version.

%(project)s is distributed in the hope that it will be useful, but
WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
General Public License for more details.

You should have received a copy of the GNU General Public License
along with %(project)s.  If not, see <http://www.gnu.org/licenses/>.
""".strip()

COPY_RIGHT_TAG='-xyz-COPY' + '-RIGHT-zyx-' # unlikely to occur in the wild :p

# Convert author names to canonical forms.
# ALIASES[<canonical name>] = <list of aliases>
# for example,
# ALIASES = {
#     'John Doe <jdoe@a.com>':
#         ['John Doe', 'jdoe', 'J. Doe <j@doe.net>'],
#     }
# Git-based projects are encouraged to use .mailmap instead of
# ALIASES.  See git-shortlog(1) for details.
ALIASES = {
    'Aaron Bentley <abentley@panoramicfeedback.com>':
        ['Aaron Bentley <aaron.bentley@utoronto.ca>'],
    'Panometrics, Inc.':
        ['Aaron Bentley and Panometrics, Inc.'],
    'Ben Finney <benf@cybersource.com.au>':
        ['Ben Finney <ben+python@benfinney.id.au>',
         'John Doe <jdoe@example.com>'],
    'Chris Ball <cjb@laptop.org>':
        ['Chris Ball <cjb@thunk.printf.net>'],
    'Gianluca Montecchi <gian@grys.it>':
        ['gian <gian@li82-39>',
         'gianluca <gian@galactica>'],
    'W. Trevor King <wking@drexel.edu>':
        ['wking <wking@mjolnir>',
         'wking <wking@thialfi>'],
    None:
        ['j^ <j@oil21.org>'],
    }

# List of paths that should not be scanned for copyright updates.
# IGNORED_PATHS = ['./.git/']
IGNORED_PATHS = ['./.be/', './.git/', './build/', './doc/.build/']
# List of files that should not be scanned for copyright updates.
# IGNORED_FILES = ['COPYING']
IGNORED_FILES = ['COPYING', 'catmutt']

# Work around missing author holes in the VCS history.
# AUTHOR_HACKS[<path tuple>] = [<missing authors]
# for example, if John Doe contributed to module.py but wasn't listed
# in the VCS history of that file:
# AUTHOR_HACKS = {
#     ('path', 'to', 'module.py'):['John Doe'],
#     }
AUTHOR_HACKS = {}

# Work around missing year holes in the VCS history.
# YEAR_HACKS[<path tuple>] = <original year>
# for example, if module.py was published in 2008 but the VCS history
# only goes back to 2010:
# YEAR_HACKS = {
#     ('path', 'to', 'module.py'):2008,
#     }
YEAR_HACKS = {}

# Helpers for VCS-specific commands

def splitpath(path):
    """Recursively split a path into elements.

    Examples
    --------

    >>> splitpath(os.path.join('a', 'b', 'c'))
    ('a', 'b', 'c')
    >>> splitpath(os.path.join('.', 'a', 'b', 'c'))
    ('a', 'b', 'c')
    """
    path = os.path.normpath(path)
    elements = []
    while True:
        dirname,basename = os.path.split(path)
        elements.insert(0,basename)
        if dirname in ['', '.']:
            break
        path = dirname
    return tuple(elements)

# VCS-specific commands

if PROJECT_INFO['vcs'] == 'Git':

    import subprocess

    _MSWINDOWS = sys.platform == 'win32'
    _POSIX = not _MSWINDOWS

    def invoke(args, stdin=None, stdout=subprocess.PIPE, stderr=subprocess.PIPE, expect=(0,)):
        """
        expect should be a tuple of allowed exit codes.
        """
        try :
            if _POSIX:
                q = subprocess.Popen(args, stdin=subprocess.PIPE,
                                     stdout=stdout, stderr=stderr)
            else:
                assert _MSWINDOWS == True, 'invalid platform'
                # win32 don't have os.execvp() so run the command in a shell
                q = subprocess.Popen(args, stdin=subprocess.PIPE,
                                     stdout=stdout, stderr=stderr, shell=True)
        except OSError, e:
            raise ValueError([args, e])
        stdout,stderr = q.communicate(input=stdin)
        status = q.wait()
        if status not in expect:
            raise ValueError([args, status, stdout, stderr])
        return status, stdout, stderr

    def git_cmd(*args):
        status,stdout,stderr = invoke(['git'] + list(args))
        return stdout.rstrip('\n')

    version = git_cmd('--version').split(' ')[-1]
    if version.startswith('1.5.'):
        # Author name <author email>
        author_format = '--pretty=format:%an <%ae>'
        year_format = ['--pretty=format:%ai']  # Author date
        # YYYY-MM-DD HH:MM:SS Z
        # Earlier versions of Git don't seem to recognize --date=short
    else:
        author_format = '--pretty=format:%aN <%aE>'
        year_format = ['--pretty=format:%ad',  # Author date
                       '--date=short']         # YYYY-MM-DD

    def original_year(filename, year_hacks=YEAR_HACKS):
        output = git_cmd(*(['log', '--follow']
                           + year_format
                           + [filename]))
        if version.startswith('1.5.'):
            output = '\n'.join([x.split()[0] for x in output.splitlines()])
        years = [int(line.split('-', 1)[0]) for line in output.splitlines()]
        if splitpath(filename) in year_hacks:
            years.append(year_hacks[splitpath(filename)])
        years.sort()
        return years[0]

    def authors(filename, author_hacks=AUTHOR_HACKS):
        output = git_cmd('log', '--follow', author_format,
                         filename)
        ret = list(set(output.splitlines()))
        if splitpath(filename) in author_hacks:
            ret.extend(author_hacks[splitpath(filename)])
        return ret

    def authors_list(author_hacks=AUTHOR_HACKS):
        output = git_cmd('log', author_format)
        ret = list(set(output.splitlines()))
        for path,authors in author_hacks.items():
            ret.extend(authors)
        return ret

    def is_versioned(filename):
        output = git_cmd('log', '--follow', filename)
        if len(output) == 0:
            return False
        return True

elif PROJECT_INFO['vcs'] == 'Mercurial':

    import StringIO
    import mercurial
    import mercurial.dispatch

    def mercurial_cmd(*args):
        cwd = os.getcwd()
        stdout = sys.stdout
        stderr = sys.stderr
        tmp_stdout = StringIO.StringIO()
        tmp_stderr = StringIO.StringIO()
        sys.stdout = tmp_stdout
        sys.stderr = tmp_stderr
        try:
            mercurial.dispatch.dispatch(list(args))
        finally:
            os.chdir(cwd)
            sys.stdout = stdout
            sys.stderr = stderr
        return (tmp_stdout.getvalue().rstrip('\n'),
                tmp_stderr.getvalue().rstrip('\n'))

    def original_year(filename, year_hacks=YEAR_HACKS):
        # shortdate filter: YEAR-MONTH-DAY
        output,error = mercurial_cmd('log', '--follow',
                                     '--template', '{date|shortdate}\n',
                                     filename)
        years = [int(line.split('-', 1)[0]) for line in output.splitlines()]
        if splitpath(filename) in year_hacks:
            years.append(year_hacks[splitpath(filename)])
        years.sort()
        return years[0]

    def authors(filename, author_hacks=AUTHOR_HACKS):
        output,error = mercurial_cmd('log', '--follow',
                                     '--template', '{author}\n',
                                     filename)
        ret = list(set(output.splitlines()))
        if splitpath(filename) in author_hacks:
            ret.extend(author_hacks[splitpath(filename)])
        return ret

    def authors_list(author_hacks=AUTHOR_HACKS):
        output,error = mercurial_cmd('log', '--template', '{author}\n')
        ret = list(set(output.splitlines()))
        for path,authors in author_hacks.items():
            ret.extend(authors)
        return ret

    def is_versioned(filename):
        output,error = mercurial_cmd('log', '--follow', filename)
        if len(error) > 0:
            return False
        return True

elif PROJECT_INFO['vcs'] == 'Bazaar':

    import StringIO
    import bzrlib
    import bzrlib.builtins
    import bzrlib.log

    class LogFormatter (bzrlib.log.LogFormatter):
        supports_merge_revisions = True
        preferred_levels = 0
        supports_deta = False
        supports_tags = False
        supports_diff = False

        def log_revision(self, revision):
            raise NotImplementedError

    class YearLogFormatter (LogFormatter):
        def log_revision(self, revision):
            self.to_file.write(
                time.strftime('%Y', time.gmtime(revision.rev.timestamp))
                +'\n')

    class AuthorLogFormatter (LogFormatter):
        def log_revision(self, revision):
            authors = revision.rev.get_apparent_authors()
            self.to_file.write('\n'.join(authors)+'\n')

    def original_year(filename, year_hacks=YEAR_HACKS):
        cmd = bzrlib.builtins.cmd_log()
        cmd.outf = StringIO.StringIO()
        cmd.run(file_list=[filename], log_format=YearLogFormatter, levels=0)
        years = [int(year) for year in set(cmd.outf.getvalue().splitlines())]
        if splitpath(filename) in year_hacks:
            years.append(year_hacks[splitpath(filename)])
        years.sort()
        return years[0]

    def authors(filename, author_hacks=AUTHOR_HACKS):
        cmd = bzrlib.builtins.cmd_log()
        cmd.outf = StringIO.StringIO()
        cmd.run(file_list=[filename], log_format=AuthorLogFormatter, levels=0)
        ret = list(set(cmd.outf.getvalue().splitlines()))
        if splitpath(filename) in author_hacks:
            ret.extend(author_hacks[splitpath(filename)])
        return ret

    def authors_list(author_hacks=AUTHOR_HACKS):
        cmd = bzrlib.builtins.cmd_log()
        cmd.outf = StringIO.StringIO()
        cmd.run(log_format=AuthorLogFormatter, levels=0)
        output = cmd.outf.getvalue()
        ret = list(set(cmd.outf.getvalue().splitlines()))
        for path,authors in author_hacks.items():
            ret.extend(authors)
        return ret

    def is_versioned(filename):
        cmd = bzrlib.builtins.cmd_log()
        cmd.outf = StringIO.StringIO()
        cmd.run(file_list=[filename])
        return True

else:
    raise NotImplementedError('Unrecognized VCS: %(vcs)s' % PROJECT_INFO)

# General utility commands

def _strip_email(*args):
    """Remove email addresses from a series of names.

    Examples
    --------

    >>> _strip_email('J Doe <jdoe@a.com>')
    ['J Doe']
    >>> _strip_email('J Doe <jdoe@a.com>', 'JJJ Smith <jjjs@a.com>')
    ['J Doe', 'JJJ Smith']
    """
    args = list(args)
    for i,arg in enumerate(args):
        if arg == None:
            continue
        author,addr = email.utils.parseaddr(arg)
        args[i] = author
    return args

def _reverse_aliases(aliases):
    """Reverse an `aliases` dict.

    Input:   key: canonical name,  value: list of aliases
    Output:  key: alias,           value: canonical name

    Examples
    --------

    >>> aliases = {
    ...     'J Doe <jdoe@a.com>':['Johnny <jdoe@b.edu>', 'J'],
    ...     'JJJ Smith <jjjs@a.com>':['Jingly <jjjs@b.edu>'],
    ...     None:['Anonymous <a@a.com>'],
    ...     }
    >>> r = _reverse_aliases(aliases)
    >>> for item in sorted(r.items()):
    ...     print item
    ('Anonymous <a@a.com>', None)
    ('J', 'J Doe <jdoe@a.com>')
    ('Jingly <jjjs@b.edu>', 'JJJ Smith <jjjs@a.com>')
    ('Johnny <jdoe@b.edu>', 'J Doe <jdoe@a.com>')
    """
    output = {}
    for canonical_name,_aliases in aliases.items():
        for alias in _aliases:
            output[alias] = canonical_name
    return output

def _replace_aliases(authors, with_email=True, aliases=None):
    """Consolidate and sort `authors`.

    Make the replacements listed in the `aliases` dict (key: canonical
    name, value: list of aliases).  If `aliases` is ``None``, default
    to ``ALIASES``.

    >>> aliases = {
    ...     'J Doe <jdoe@a.com>':['Johnny <jdoe@b.edu>'],
    ...     'JJJ Smith <jjjs@a.com>':['Jingly <jjjs@b.edu>'],
    ...     None:['Anonymous <a@a.com>'],
    ...     }
    >>> _replace_aliases(['JJJ Smith <jjjs@a.com>', 'Johnny <jdoe@b.edu>',
    ...                   'Jingly <jjjs@b.edu>', 'Anonymous <a@a.com>'],
    ...                  with_email=True, aliases=aliases)
    ['J Doe <jdoe@a.com>', 'JJJ Smith <jjjs@a.com>']
    >>> _replace_aliases(['JJJ Smith', 'Johnny', 'Jingly', 'Anonymous'],
    ...                  with_email=False, aliases=aliases)
    ['J Doe', 'JJJ Smith']
    >>> _replace_aliases(['JJJ Smith <jjjs@a.com>', 'Johnny <jdoe@b.edu>',
    ...                   'Jingly <jjjs@b.edu>', 'J Doe <jdoe@a.com>'],
    ...                  with_email=True, aliases=aliases)
    ['J Doe <jdoe@a.com>', 'JJJ Smith <jjjs@a.com>']
    """
    if aliases == None:
        aliases = ALIASES
    if with_email == False:
        aliases = dict([(_strip_email(author)[0], _strip_email(*_aliases))
                        for author,_aliases in aliases.items()])
    rev_aliases = _reverse_aliases(aliases)
    for i,author in enumerate(authors):
        if author in rev_aliases:
            authors[i] = rev_aliases[author]
    authors = sorted(list(set(authors)))
    if None in authors:
        authors.remove(None)
    return authors

def _copyright_string(original_year, final_year, authors, prefix=''):
    """
    >>> print _copyright_string(original_year=2005,
    ...                         final_year=2005,
    ...                         authors=['A <a@a.com>', 'B <b@b.edu>'],
    ...                         prefix='# '
    ...                        ) # doctest: +ELLIPSIS
    # Copyright (C) 2005 A <a@a.com>
    #                    B <b@b.edu>
    #
    # This file...
    >>> print _copyright_string(original_year=2005,
    ...                         final_year=2009,
    ...                         authors=['A <a@a.com>', 'B <b@b.edu>']
    ...                        ) # doctest: +ELLIPSIS
    Copyright (C) 2005-2009 A <a@a.com>
                            B <b@b.edu>
    <BLANKLINE>
    This file...
    """
    if original_year == final_year:
        date_range = '%s' % original_year
    else:
        date_range = '%s-%s' % (original_year, final_year)
    lines = ['Copyright (C) %s %s' % (date_range, authors[0])]
    for author in authors[1:]:
        lines.append(' '*(len('Copyright (C) ')+len(date_range)+1) +
                     author)
    lines.append('')
    lines.extend((COPY_RIGHT_TEXT % PROJECT_INFO).splitlines())
    for i,line in enumerate(lines):
        lines[i] = (prefix + line).rstrip()
    return '\n'.join(lines)

def _tag_copyright(contents):
    """
    >>> contents = '''Some file
    ... bla bla
    ... # Copyright (copyright begins)
    ... # (copyright continues)
    ... # bla bla bla
    ... (copyright ends)
    ... bla bla bla
    ... '''
    >>> print _tag_copyright(contents).replace('COPY-RIGHT', 'CR')
    Some file
    bla bla
    -xyz-CR-zyx-
    (copyright ends)
    bla bla bla
    <BLANKLINE>
    """
    lines = []
    incopy = False
    for line in contents.splitlines():
        if incopy == False and line.startswith('# Copyright'):
            incopy = True
            lines.append(COPY_RIGHT_TAG)
        elif incopy == True and not line.startswith('#'):
            incopy = False
        if incopy == False:
            lines.append(line.rstrip('\n'))
    return '\n'.join(lines)+'\n'

def _update_copyright(contents, original_year, authors):
    """
    >>> contents = '''Some file
    ... bla bla
    ... # Copyright (copyright begins)
    ... # (copyright continues)
    ... # bla bla bla
    ... (copyright ends)
    ... bla bla bla
    ... '''
    >>> print _update_copyright(contents, 2008, ['Jack', 'Jill']
    ...     ) # doctest: +ELLIPSIS, +REPORT_UDIFF
    Some file
    bla bla
    # Copyright (C) 2008-... Jack
    #                         Jill
    #
    # This file...
    (copyright ends)
    bla bla bla
    <BLANKLINE>
    """
    current_year = time.gmtime()[0]
    copyright_string = _copyright_string(
        original_year, current_year, authors, prefix='# ')
    contents = _tag_copyright(contents)
    return contents.replace(COPY_RIGHT_TAG, copyright_string)

def ignored_file(filename, ignored_paths=None, ignored_files=None,
                 check_disk=True, check_vcs=True):
    """
    >>> ignored_paths = ['./a/', './b/']
    >>> ignored_files = ['x', 'y']
    >>> ignored_file('./a/z', ignored_paths, ignored_files, False, False)
    True
    >>> ignored_file('./ab/z', ignored_paths, ignored_files, False, False)
    False
    >>> ignored_file('./ab/x', ignored_paths, ignored_files, False, False)
    True
    >>> ignored_file('./ab/xy', ignored_paths, ignored_files, False, False)
    False
    >>> ignored_file('./z', ignored_paths, ignored_files, False, False)
    False
    """
    if ignored_paths == None:
        ignored_paths = IGNORED_PATHS
    if ignored_files == None:
        ignored_files = IGNORED_FILES
    if check_disk == True and os.path.isfile(filename) == False:
        return True
    for path in ignored_paths:
        if filename.startswith(path):
            return True
    if os.path.basename(filename) in ignored_files:
        return True
    if check_vcs == True and is_versioned(filename) == False:
        return True
    return False

def _set_contents(filename, contents, original_contents=None, dry_run=False,
                  verbose=0):
    if original_contents == None and os.path.isfile(filename):
        f = open(filename, 'r')
        original_contents = f.read()
        f.close()
    if verbose > 0:
        print "checking %s ... " % filename,
    if contents != original_contents:
        if verbose > 0:
            if original_contents == None:
                print "[creating]"
            else:
                print "[updating]"
        if verbose > 1 and original_contents != None:
            print '\n'.join(
                difflib.unified_diff(
                    original_contents.splitlines(), contents.splitlines(),
                    fromfile=os.path.normpath(os.path.join('a', filename)),
                    tofile=os.path.normpath(os.path.join('b', filename)),
                    n=3, lineterm=''))
        if dry_run == False:
            f = file(filename, 'w')
            f.write(contents)
            f.close()
    elif verbose > 0:
        print "[no change]"

# Update commands

def update_authors(authors_fn=authors_list, dry_run=False, verbose=0):
    authors = authors_fn()
    authors = _replace_aliases(authors, with_email=True, aliases=ALIASES)
    new_contents = '%s was written by:\n%s\n' % (
        PROJECT_INFO['project'],
        '\n'.join(authors)
        )
    _set_contents('AUTHORS', new_contents, dry_run=dry_run, verbose=verbose)

def update_file(filename, original_year_fn=original_year, authors_fn=authors,
                dry_run=False, verbose=0):
    f = file(filename, 'r')
    contents = f.read()
    f.close()

    original_year = original_year_fn(filename)
    authors = authors_fn(filename)
    authors = _replace_aliases(authors, with_email=True, aliases=ALIASES)

    new_contents = _update_copyright(contents, original_year, authors)
    _set_contents(filename, contents=new_contents, original_contents=contents,
                  dry_run=dry_run, verbose=verbose)

def update_files(files=None, dry_run=False, verbose=0):
    if files == None or len(files) == 0:
        files = []
        for dirpath,dirnames,filenames in os.walk('.'):
            for filename in filenames:
                files.append(os.path.join(dirpath, filename))

    for filename in files:
        if ignored_file(filename) == True:
            continue
        update_file(filename, dry_run=dry_run, verbose=verbose)

def test():
    import doctest
    doctest.testmod()

if __name__ == '__main__':
    import optparse
    import sys

    usage = """%%prog [options] [file ...]

Update copyright information in source code with information from
the %(vcs)s repository.  Run from the %(project)s repository root.

Replaces every line starting with '^# Copyright' and continuing with
'^#' with an auto-generated copyright blurb.  If you want to add
#-commented material after a copyright blurb, please insert a blank
line between the blurb and your comment, so the next run of
``update_copyright.py`` doesn't clobber your comment.

If no files are given, a list of files to update is generated
automatically.
""" % PROJECT_INFO
    p = optparse.OptionParser(usage)
    p.add_option('--test', dest='test', default=False,
                 action='store_true', help='Run internal tests and exit')
    p.add_option('--dry-run', dest='dry_run', default=False,
                 action='store_true', help="Don't make any changes")
    p.add_option('-v', '--verbose', dest='verbose', default=0,
                 action='count', help='Increment verbosity')
    options,args = p.parse_args()

    if options.test == True:
        test()
        sys.exit(0)

    update_authors(dry_run=options.dry_run, verbose=options.verbose)
    update_files(files=args, dry_run=options.dry_run, verbose=options.verbose)
