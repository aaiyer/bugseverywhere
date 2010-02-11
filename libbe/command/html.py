# Copyright (C) 2009-2010 Gianluca Montecchi <gian@grys.it>
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

import codecs
import htmlentitydefs
import os
import os.path
import re
import string
import time
import xml.sax.saxutils

import libbe
import libbe.command
import libbe.command.util
import libbe.comment
import libbe.util.encoding
import libbe.util.id


class HTML (libbe.command.Command):
    """Generate a static HTML dump of the current repository status

    >>> import sys
    >>> import libbe.bugdir
    >>> bd = libbe.bugdir.SimpleBugDir(memory=False)
    >>> io = libbe.command.StringInputOutput()
    >>> io.stdout = sys.stdout
    >>> ui = libbe.command.UserInterface(io=io)
    >>> ui.storage_callbacks.set_storage(bd.storage)
    >>> cmd = HTML(ui=ui)

    >>> ret = ui.run(cmd, {'output':os.path.join(bd.storage.repo, 'html_export')})
    >>> os.path.exists(os.path.join(bd.storage.repo, 'html_export'))
    True
    >>> os.path.exists(os.path.join(bd.storage.repo, 'html_export', 'index.html'))
    True
    >>> os.path.exists(os.path.join(bd.storage.repo, 'html_export', 'index_inactive.html'))
    True
    >>> os.path.exists(os.path.join(bd.storage.repo, 'html_export', 'bugs'))
    True
    >>> os.path.exists(os.path.join(bd.storage.repo, 'html_export', 'bugs', 'a.html'))
    True
    >>> os.path.exists(os.path.join(bd.storage.repo, 'html_export', 'bugs', 'b.html'))
    True
    >>> ui.cleanup()
    >>> bd.cleanup()
    """
    name = 'html'

    def __init__(self, *args, **kwargs):
        libbe.command.Command.__init__(self, *args, **kwargs)
        self.options.extend([
                libbe.command.Option(name='output', short_name='o',
                    help='Set the output path (%default)',
                    arg=libbe.command.Argument(
                        name='output', metavar='DIR', default='./html_export',
                        completion_callback=libbe.command.util.complete_path)),
                libbe.command.Option(name='template-dir', short_name='t',
                    help='Use a different template.  Defaults to internal templates',
                    arg=libbe.command.Argument(
                        name='template-dir', metavar='DIR',
                        completion_callback=libbe.command.util.complete_path)),
                libbe.command.Option(name='title',
                    help='Set the bug repository title (%default)',
                    arg=libbe.command.Argument(
                        name='title', metavar='STRING',
                        default='BugsEverywhere Issue Tracker')),
                libbe.command.Option(name='index-header',
                    help='Set the index page headers (%default)',
                    arg=libbe.command.Argument(
                        name='index-header', metavar='STRING',
                        default='BugsEverywhere Bug List')),
                libbe.command.Option(name='export-template', short_name='e',
                    help='Export the default template and exit.'),
                libbe.command.Option(name='export-template-dir', short_name='d',
                    help='Set the directory for the template export (%default)',
                    arg=libbe.command.Argument(
                        name='export-template-dir', metavar='DIR',
                        default='./default-templates/',
                        completion_callback=libbe.command.util.complete_path)),
                libbe.command.Option(name='verbose', short_name='v',
                    help='Verbose output, default is %default'),
                ])

    def _run(self, **params):
        if params['export-template'] == True:
            html_gen.write_default_template(params['export-template-dir'])
            return 0
        bugdir = self._get_bugdir()
        bugdir.load_all_bugs()
        html_gen = HTMLGen(bugdir,
                           template=params['template-dir'],
                           title=params['title'],
                           index_header=params['index-header'],
                           verbose=params['verbose'],
                           stdout=self.stdout)
        html_gen.run(params['output'])
        return 0

    def _long_help(self):
        return """
Generate a set of html pages representing the current state of the bug
directory.
"""

Html = HTML # alias for libbe.command.base.get_command_class()

class HTMLGen (object):
    def __init__(self, bd, template=None,
                 title="Site Title", index_header="Index Header",
                 verbose=False, encoding=None, stdout=None,
                 ):
        self.generation_time = time.ctime()
        self.bd = bd
        if template == None:
            self.template = "default"
        else:
            self.template = os.path.abspath(os.path.expanduser(template))
        self.title = title
        self.index_header = index_header
        self.verbose = verbose
        self.stdout = stdout
        if encoding != None:
            self.encoding = encoding
        else:
            self.encoding = libbe.util.encoding.get_filesystem_encoding()
        self._load_default_templates()
        if template != None:
            self._load_user_templates()
        self.bug_list_dict = {}
        
    def run(self, out_dir):
        if self.verbose == True:
            print >> self.stdout, \
                'Creating the html output in %s using templates in %s' \
                % (out_dir, self.template)

        bugs_active = []
        bugs_inactive = []
        bugs = [b for b in self.bd]
        bugs.sort()
        bugs_active = [b for b in bugs if b.active == True]
        bugs_inactive = [b for b in bugs if b.active != True]

        self._create_output_directories(out_dir)
        self._write_css_file()
        for b in bugs:
            if b.active:
                up_link = '../index.html'
            else:
                up_link = '../index_inactive.html'
            fname = self._create_file_name(b.uuid)
            self._write_bug_file(b, up_link, fname)
        self._write_index_file(
            bugs_active, title=self.title,
            index_header=self.index_header, bug_type='active')
        self._write_index_file(
            bugs_inactive, title=self.title,
            index_header=self.index_header, bug_type='inactive')

    def _create_file_name(self, bugid):
        s = 4
        if not self.bug_list_dict.has_key(bugid[0:3]):
            self.bug_list_dict[bugid[0:3]] = bugid
            fname = bugid[0:3]
        else:
            for i in range(s, s+6):
                if not self.bug_list_dict.has_key(bugid[0:s]):
                    self.bug_list_dict[bugid[0:s]] = bugid
                    fname = bugid[0:s]
                    break
                if s == 8:
                    self.bug_list_dict[bugid] = bugid
                    fname = bugid
        fpath = os.path.join(self.out_dir_bugs, fname)
        return fpath
        
    def _find_file_name(self, bugid):
        name = ""
        for k in self.bug_list_dict:
            if self.bug_list_dict[k] == bugid:
                name = k
                self.bug_list_dict.pop(k)
                break
        return name 

    def _create_output_directories(self, out_dir):
        if self.verbose:
            print >> self.stdout, 'Creating output directories'
        self.out_dir = self._make_dir(out_dir)
        self.out_dir_bugs = self._make_dir(
            os.path.join(self.out_dir, 'bugs'))

    def _write_css_file(self):
        if self.verbose:
            print >> self.stdout, 'Writing css file'
        assert hasattr(self, 'out_dir'), \
            'Must run after ._create_output_directories()'
        self._write_file(self.css_file,
                         [self.out_dir,'style.css'])

    def _write_bug_file(self, bug, up_link, fname):
        if self.verbose:
            print >> self.stdout, '\tCreating bug file for %s' % bug.id.user()
        assert hasattr(self, 'out_dir_bugs'), \
            'Must run after ._create_output_directories()'

        bug.load_comments(load_full=True)
        comment_entries = self._generate_bug_comment_entries(bug)
        filename = '%s.html' % fname
        fullpath = os.path.join(self.out_dir_bugs, filename)
        template_info = {'title':self.title,
                         'charset':self.encoding,
                         'up_link':up_link,
                         'shortname':bug.id.user(),
                         'comment_entries':comment_entries,
                         'generation_time':self.generation_time}
        for attr in ['uuid', 'severity', 'status', 'assigned',
                     'reporter', 'creator', 'time_string', 'summary']:
            template_info[attr] = self._escape(getattr(bug, attr))
        self._write_file(self.bug_file % template_info, [fullpath])

    def _generate_bug_comment_entries(self, bug):
        assert hasattr(self, 'out_dir_bugs'), \
            'Must run after ._create_output_directories()'

        stack = []
        comment_entries = []
        bug.comment_root.sort(cmp=libbe.comment.cmp_time, reverse=True)
        for depth,comment in bug.comment_root.thread(flatten=False):
            while len(stack) > depth:
                # pop non-parents off the stack
                stack.pop(-1)
                # close non-parent <div class="comment...
                comment_entries.append('</div>\n')
            assert len(stack) == depth
            stack.append(comment)
            if depth == 0:
                comment_entries.append('<div class="comment root">')
            else:
                comment_entries.append(
                    '<div class="comment" id="%s">' % comment.uuid)
            template_info = {'shortname': comment.id.user()}
            for attr in ['uuid', 'author', 'date', 'body']:
                value = getattr(comment, attr)
                if attr == 'body':
                    link_long_ids = False
                    save_body = False
                    if comment.content_type == 'text/html':
                        link_long_ids = True
                    elif comment.content_type.startswith('text/'):
                        value = '<pre>\n'+self._escape(value)+'\n</pre>'
                        link_long_ids = True
                    elif comment.content_type.startswith('image/'):
                        save_body = True
                        value = '<img src="./%s/%s" />' \
                            % (bug.uuid, comment.uuid)
                    else:
                        save_body = True
                        value = '<a href="./%s/%s">Link to %s file</a>.' \
                            % (bug.uuid, comment.uuid, comment.content_type)
                    if link_long_ids == True:
                        value = self._long_to_linked_user(value)
                    if save_body == True:
                        per_bug_dir = os.path.join(self.out_dir_bugs, bug.uuid)
                        if not os.path.exists(per_bug_dir):
                            os.mkdir(per_bug_dir)
                        comment_path = os.path.join(per_bug_dir, comment.uuid)
                        self._write_file(
                            '<Files %s>\n  ForceType %s\n</Files>' \
                                % (comment.uuid, comment.content_type),
                            [per_bug_dir, '.htaccess'], mode='a')
                        self._write_file(comment.body,
                            [per_bug_dir, comment.uuid], mode='wb')
                else:
                    value = self._escape(value)
                template_info[attr] = value
            comment_entries.append(self.bug_comment_entry % template_info)
        while len(stack) > 0:
            stack.pop(-1)
            comment_entries.append('</div>\n') # close every remaining <div class='comment...
        return '\n'.join(comment_entries)

    def _long_to_linked_user(self, text):
        """
        >>> import libbe.bugdir
        >>> bd = libbe.bugdir.SimpleBugDir(memory=False)
        >>> h = HTMLGen(bd)
        >>> h._long_to_linked_user('A link #abc123/a#, and a non-link #x#y#.')
        'A link <a href="./a.html">abc/a</a>, and a non-link #x#y#.'
        >>> bd.cleanup()
        """
        replacer = libbe.util.id.IDreplacer(
            [self.bd], self._long_to_linked_user_replacer, wrap=False)
        return re.sub(
            libbe.util.id.REGEXP, replacer, text)

    def _long_to_linked_user_replacer(self, bugdirs, long_id):
        """
        >>> import libbe.bugdir
        >>> import libbe.util.id
        >>> bd = libbe.bugdir.SimpleBugDir(memory=False)
        >>> a = bd.bug_from_uuid('a')
        >>> uuid_gen = libbe.util.id.uuid_gen
        >>> libbe.util.id.uuid_gen = lambda : '0123'
        >>> c = a.new_comment('comment for link testing')
        >>> libbe.util.id.uuid_gen = uuid_gen
        >>> c.uuid
        '0123'
        >>> h = HTMLGen(bd)
        >>> h._long_to_linked_user_replacer([bd], 'abc123')
        '#abc123#'
        >>> h._long_to_linked_user_replacer([bd], 'abc123/a')
        '<a href="./a.html">abc/a</a>'
        >>> h._long_to_linked_user_replacer([bd], 'abc123/a/0123')
        '<a href="./a.html#0123">abc/a/012</a>'
        >>> h._long_to_linked_user_replacer([bd], 'x')
        '#x#'
        >>> h._long_to_linked_user_replacer([bd], '')
        '##'
        >>> bd.cleanup()
        """
        try:
            p = libbe.util.id.parse_user(bugdirs[0], long_id)
            short_id = libbe.util.id.long_to_short_user(bugdirs, long_id)
        except (libbe.util.id.MultipleIDMatches,
                libbe.util.id.NoIDMatches,
                libbe.util.id.InvalidIDStructure), e:
            return '#%s#' % long_id # re-wrap failures
        if p['type'] == 'bugdir':
            return '#%s#' % long_id
        elif p['type'] == 'bug':
            return '<a href="./%s.html">%s</a>' \
                % (p['bug'], short_id)
        elif p['type'] == 'comment':
            return '<a href="./%s.html#%s">%s</a>' \
                % (p['bug'], p['comment'], short_id)
        raise Exception('Invalid id type %s for "%s"'
                        % (p['type'], long_id))

    def _write_index_file(self, bugs, title, index_header, bug_type='active'):
        if self.verbose:
            print >> self.stdout, 'Writing %s index file for %d bugs' % (bug_type, len(bugs))
        assert hasattr(self, 'out_dir'), 'Must run after ._create_output_directories()'
        esc = self._escape

        bug_entries = self._generate_index_bug_entries(bugs)

        if bug_type == 'active':
            filename = 'index.html'
        elif bug_type == 'inactive':
            filename = 'index_inactive.html'
        else:
            raise Exception, 'Unrecognized bug_type: "%s"' % bug_type
        template_info = {'title':title,
                         'index_header':index_header,
                         'charset':self.encoding,
                         'active_class':'tab sel',
                         'inactive_class':'tab nsel',
                         'bug_entries':bug_entries,
                         'generation_time':self.generation_time}
        if bug_type == 'inactive':
            template_info['active_class'] = 'tab nsel'
            template_info['inactive_class'] = 'tab sel'

        self._write_file(self.index_file % template_info,
                         [self.out_dir, filename])

    def _generate_index_bug_entries(self, bugs):
        bug_entries = []
        for bug in bugs:
            if self.verbose:
                print >> self.stdout, '\tCreating bug entry for %s' % bug.id.user()
            template_info = {'shortname':bug.id.user()}
            fn = self._find_file_name(bug.uuid)
            for attr in ['uuid', 'severity', 'status', 'assigned',
                         'reporter', 'creator', 'time_string', 'summary']:
                template_info[attr] = self._escape(getattr(bug, attr))
            template_info['uuid'] = fn
            bug_entries.append(self.index_bug_entry % template_info)
        return '\n'.join(bug_entries)

    def _escape(self, string):
        if string == None:
            return ''
        return xml.sax.saxutils.escape(string)

    def _load_user_templates(self):
        for filename,attr in [('style.css','css_file'),
                              ('index_file.tpl','index_file'),
                              ('index_bug_entry.tpl','index_bug_entry'),
                              ('bug_file.tpl','bug_file'),
                              ('bug_comment_entry.tpl','bug_comment_entry')]:
            fullpath = os.path.join(self.template, filename)
            if os.path.exists(fullpath):
                setattr(self, attr, self._read_file([fullpath]))

    def _make_dir(self, dir_path):
        dir_path = os.path.abspath(os.path.expanduser(dir_path))
        if not os.path.exists(dir_path):
            try:
                os.makedirs(dir_path)
            except:
                raise libbe.command.UserError(
                    'Cannot create output directory "%s".' % dir_path)
        return dir_path

    def _write_file(self, content, path_array, mode='w'):
        return libbe.util.encoding.set_file_contents(
            os.path.join(*path_array), content, mode, self.encoding)

    def _read_file(self, path_array, mode='r'):
        return libbe.util.encoding.get_file_contents(
            os.path.join(*path_array), mode, self.encoding, decode=True)

    def write_default_template(self, out_dir):
        if self.verbose:
            print >> self.stdout, 'Creating output directories'
        self.out_dir = self._make_dir(out_dir)
        if self.verbose:
            print >> self.stdout, 'Creating css file'
        self._write_css_file()
        if self.verbose:
            print >> self.stdout, 'Creating index_file.tpl file'
        self._write_file(self.index_file,
                         [self.out_dir, 'index_file.tpl'])
        if self.verbose:
            print >> self.stdout, 'Creating index_bug_entry.tpl file'
        self._write_file(self.index_bug_entry,
                         [self.out_dir, 'index_bug_entry.tpl'])
        if self.verbose:
            print >> self.stdout, 'Creating bug_file.tpl file'
        self._write_file(self.bug_file,
                         [self.out_dir, 'bug_file.tpl'])
        if self.verbose:
            print >> self.stdout, 'Creating bug_comment_entry.tpl file'
        self._write_file(self.bug_comment_entry,
                         [self.out_dir, 'bug_comment_entry.tpl'])

    def _load_default_templates(self):
        self.css_file = """
            body {
              font-family: "lucida grande", "sans serif";
              color: #333;
              width: auto;
              margin: auto;
            }

            div.main {
              padding: 20px;
              margin: auto;
              padding-top: 0;
              margin-top: 1em;
              background-color: #fcfcfc;
            }

            div.footer {
              font-size: small;
              padding-left: 20px;
              padding-right: 20px;
              padding-top: 5px;
              padding-bottom: 5px;
              margin: auto;
              background: #305275;
              color: #fffee7;
            }

            table {
              border-style: solid;
              border: 10px #313131;
              border-spacing: 0;
              width: auto;
            }

            tb { border: 1px; }

            tr {
              vertical-align: top;
              width: auto;
            }

            td {
              border-width: 0;
              border-style: none;
              padding-right: 0.5em;
              padding-left: 0.5em;
              width: auto;
            }

            img { border-style: none; }

            h1 {
              padding: 0.5em;
              background-color: #305275;
              margin-top: 0;
              margin-bottom: 0;
              color: #fff;
              margin-left: -20px;
              margin-right: -20px;
            }

            ul {
              list-style-type: none;
              padding: 0;
            }

            p { width: auto; }

            a, a:visited {
              background: inherit;
              text-decoration: none;
            }

            a { color: #003d41; }
            a:visited { color: #553d41; }
            .footer a { color: #508d91; }

            /* bug index pages */

            td.tab {
              padding-right: 1em;
              padding-left: 1em;
            }

            td.sel.tab {
              background-color: #afafaf;
              border: 1px solid #afafaf;
              font-weight:bold;
            }

            td.nsel.tab { border: 0px; }

            table.bug_list {
              background-color: #afafaf;
              border: 2px solid #afafaf;
            }

            .bug_list tr { width: auto; }
            tr.wishlist { background-color: #B4FF9B; }
            tr.minor { background-color: #FCFF98; }
            tr.serious { background-color: #FFB648; }
            tr.critical { background-color: #FF752A; }
            tr.fatal { background-color: #FF3300; }

            /* bug detail pages */

            td.bug_detail_label { text-align: right; }
            td.bug_detail { }
            td.bug_comment_label { text-align: right; vertical-align: top; }
            td.bug_comment { }

            div.comment {
              padding: 20px;
              padding-top: 20px;
              margin: auto;
              margin-top: 0;
            }

            div.root.comment {
              padding: 0px;
              /* padding-top: 0px; */
              padding-bottom: 20px;
            }
       """

        self.index_file = """
            <!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Strict//EN"
              "http://www.w3.org/TR/xhtml1/DTD/xhtml1-strict.dtd">
            <html xmlns="http://www.w3.org/1999/xhtml" xml:lang="en" lang="en">
            <head>
            <title>%(title)s</title>
            <meta http-equiv="Content-Type" content="text/html; charset=%(charset)s" />
            <link rel="stylesheet" href="style.css" type="text/css" />
            </head>
            <body>

            <div class="main">
            <h1>%(index_header)s</h1>
            <p></p>
            <table>

            <tr>
            <td class="%(active_class)s"><a href="index.html">Active Bugs</a></td>
            <td class="%(inactive_class)s"><a href="index_inactive.html">Inactive Bugs</a></td>
            </tr>

            </table>
            <table class="bug_list">
            <tbody>

            %(bug_entries)s

            </tbody>
            </table>
            </div>

            <div class="footer">
            <p>Generated by <a href="http://www.bugseverywhere.org/">
            BugsEverywhere</a> on %(generation_time)s</p>
            <p>
            <a href="http://validator.w3.org/check?uri=referer">Validate XHTML</a>&nbsp;|&nbsp;
            <a href="http://jigsaw.w3.org/css-validator/check?uri=referer">Validate CSS</a>
            </p>
            </div>

            </body>
            </html>
        """

        self.index_bug_entry ="""
            <tr class="%(severity)s">
              <td><a href="bugs/%(uuid)s.html">%(shortname)s</a></td>
              <td><a href="bugs/%(uuid)s.html">%(status)s</a></td>
              <td><a href="bugs/%(uuid)s.html">%(severity)s</a></td>
              <td><a href="bugs/%(uuid)s.html">%(summary)s</a></td>
              <td><a href="bugs/%(uuid)s.html">%(time_string)s</a></td>
            </tr>
        """

        self.bug_file = """
            <!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Strict//EN"
              "http://www.w3.org/TR/xhtml1/DTD/xhtml1-strict.dtd">
            <html xmlns="http://www.w3.org/1999/xhtml" xml:lang="en" lang="en">
            <head>
            <title>%(title)s</title>
            <meta http-equiv="Content-Type" content="text/html; charset=%(charset)s" />
            <link rel="stylesheet" href="../style.css" type="text/css" />
            </head>
            <body>

            <div class="main">
            <h1>BugsEverywhere Bug List</h1>
            <h5><a href="%(up_link)s">Back to Index</a></h5>
            <h2>Bug: %(shortname)s</h2>
            <table>
            <tbody>

            <tr><td class="bug_detail_label">ID :</td>
                <td class="bug_detail">%(uuid)s</td></tr>
            <tr><td class="bug_detail_label">Short name :</td>
                <td class="bug_detail">%(shortname)s</td></tr>
            <tr><td class="bug_detail_label">Status :</td>
                <td class="bug_detail">%(status)s</td></tr>
            <tr><td class="bug_detail_label">Severity :</td>
                <td class="bug_detail">%(severity)s</td></tr>
            <tr><td class="bug_detail_label">Assigned :</td>
                <td class="bug_detail">%(assigned)s</td></tr>
            <tr><td class="bug_detail_label">Reporter :</td>
                <td class="bug_detail">%(reporter)s</td></tr>
            <tr><td class="bug_detail_label">Creator :</td>
                <td class="bug_detail">%(creator)s</td></tr>
            <tr><td class="bug_detail_label">Created :</td>
                <td class="bug_detail">%(time_string)s</td></tr>
            <tr><td class="bug_detail_label">Summary :</td>
                <td class="bug_detail">%(summary)s</td></tr>
            </tbody>
            </table>

            <hr/>

            %(comment_entries)s

            </div>
            <h5><a href="%(up_link)s">Back to Index</a></h5>

            <div class="footer">
            <p>Generated by <a href="http://www.bugseverywhere.org/">
            BugsEverywhere</a> on %(generation_time)s</p>
            <p>
            <a href="http://validator.w3.org/check?uri=referer">Validate XHTML</a>&nbsp;|&nbsp;
            <a href="http://jigsaw.w3.org/css-validator/check?uri=referer">Validate CSS</a>
            </p>
            </div>

            </body>
            </html>
        """

        self.bug_comment_entry ="""
            <table>
            <tr>
              <td class="bug_comment_label">Comment:</td>
              <td class="bug_comment">
            --------- Comment ---------<br/>
            ID: %(uuid)s<br/>
            Short name: %(shortname)s<br/>
            From: %(author)s<br/>
            Date: %(date)s<br/>
            <br/>
            %(body)s
              </td>
            </tr>
            </table>
        """

        # strip leading whitespace
        for attr in ['css_file', 'index_file', 'index_bug_entry', 'bug_file',
                     'bug_comment_entry']:
            value = getattr(self, attr)
            value = value.replace('\n'+' '*12, '\n')
            setattr(self, attr, value.strip()+'\n')
