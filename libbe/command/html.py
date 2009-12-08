# Copyright (C) 2009 Gianluca Montecchi <gian@grys.it>
#                    W. Trevor King <wking@drexel.edu>
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
"""Generate a static HTML dump of the current repository status"""
from libbe import cmdutil, bugdir, bug
import codecs, os, os.path, re, string, time
import xml.sax.saxutils, htmlentitydefs

__desc__ = __doc__

def execute(args, manipulate_encodings=True, restrict_file_access=False,
            dir="."):
    """
    >>> import os
    >>> bd = bugdir.SimpleBugDir()
    >>> os.chdir(bd.root)
    >>> execute([], manipulate_encodings=False)
    >>> os.path.exists("./html_export")
    True
    >>> os.path.exists("./html_export/index.html")
    True
    >>> os.path.exists("./html_export/index_inactive.html")
    True
    >>> os.path.exists("./html_export/bugs")
    True
    >>> os.path.exists("./html_export/bugs/a.html")
    True
    >>> os.path.exists("./html_export/bugs/b.html")
    True
    >>> bd.cleanup()
    """
    parser = get_parser()
    options, args = parser.parse_args(args)
    complete(options, args, parser)
    cmdutil.default_complete(options, args, parser)

    if len(args) > 0:
        raise cmdutil.UsageError, 'Too many arguments.'

    bd = bugdir.BugDir(from_disk=True,
                       manipulate_encodings=manipulate_encodings,
                       root=dir)
    bd.load_all_bugs()

    html_gen = HTMLGen(bd, template=options.template, verbose=options.verbose,
                       title=options.title, index_header=options.index_header)
    if options.exp_template == True:
        html_gen.write_default_template(options.exp_template_dir)
        return
    html_gen.run(options.out_dir)

def get_parser():
    parser = cmdutil.CmdOptionParser('be html [options]')
    parser.add_option('-o', '--output', metavar='DIR', dest='out_dir',
        help='Set the output path (%default)', default='./html_export')
    parser.add_option('-t', '--template-dir', metavar='DIR', dest='template',
        help='Use a different template, defaults to internal templates',
        default=None)
    parser.add_option('--title', metavar='STRING', dest='title',
        help='Set the bug repository title (%default)',
        default='BugsEverywhere Issue Tracker')
    parser.add_option('--index-header', metavar='STRING', dest='index_header',
        help='Set the index page headers (%default)',
        default='BugsEverywhere Bug List')
    parser.add_option('-v', '--verbose',  action='store_true',
        metavar='verbose', dest='verbose',
        help='Verbose output, default is %default', default=False)
    parser.add_option('-e', '--export-template',  action='store_true',
        dest='exp_template',
        help='Export the default template and exit.', default=False)
    parser.add_option('-d', '--export-template-dir', metavar='DIR',
        dest='exp_template_dir', default='./default-templates/',
        help='Set the directory for the template export (%default)')
    return parser

longhelp="""
Generate a set of html pages representing the current state of the bug
directory.
"""

def help():
    return get_parser().help_str() + longhelp

def complete(options, args, parser):
    for option, value in cmdutil.option_value_pairs(options, parser):
        if "--complete" in args:
            raise cmdutil.GetCompletions() # no positional arguments for list

class HTMLGen (object):
    def __init__(self, bd, template=None, verbose=False, encoding=None,
                 title="Site Title", index_header="Index Header",
                 ):
        self.generation_time = time.ctime()
        self.bd = bd
        self.verbose = verbose
        self.title = title
        self.index_header = index_header
        if encoding != None:
            self.encoding = encoding
        else:
            self.encoding = self.bd.encoding
        if template == None:
            self.template = "default"
        else:
            self.template = os.path.abspath(os.path.expanduser(template))
        self._load_default_templates()

        if template != None:
            self._load_user_templates()

    def run(self, out_dir):
        if self.verbose == True:
            print "Creating the html output in %s using templates in %s" \
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
                up_link = "../index.html"
            else:
                up_link = "../index_inactive.html"
            self._write_bug_file(b, up_link)
        self._write_index_file(
            bugs_active, title=self.title,
            index_header=self.index_header, bug_type="active")
        self._write_index_file(
            bugs_inactive, title=self.title,
            index_header=self.index_header, bug_type="inactive")

    def _create_output_directories(self, out_dir):
        if self.verbose:
            print "Creating output directories"
        self.out_dir = self._make_dir(out_dir)
        self.out_dir_bugs = self._make_dir(
            os.path.join(self.out_dir, "bugs"))

    def _write_css_file(self):
        if self.verbose:
            print "Writing css file"
        assert hasattr(self, "out_dir"), \
            "Must run after ._create_output_directories()"
        self._write_file(self.css_file,
                         [self.out_dir,"style.css"])

    def _write_bug_file(self, bug, up_link):
        if self.verbose:
            print "\tCreating bug file for %s" % self.bd.bug_shortname(bug)
        assert hasattr(self, "out_dir_bugs"), \
            "Must run after ._create_output_directories()"

        bug.load_comments(load_full=True)
        comment_entries = self._generate_bug_comment_entries(bug)
        filename = "%s.html" % bug.uuid
        fullpath = os.path.join(self.out_dir_bugs, filename)
        template_info = {'title':self.title,
                         'charset':self.encoding,
                         'up_link':up_link,
                         'shortname':self.bd.bug_shortname(bug),
                         'comment_entries':comment_entries,
                         'generation_time':self.generation_time}
        for attr in ['uuid', 'severity', 'status', 'assigned',
                     'reporter', 'creator', 'time_string', 'summary']:
            template_info[attr] = self._escape(getattr(bug, attr))
        self._write_file(self.bug_file % template_info, [fullpath])

    def _generate_bug_comment_entries(self, bug):
        assert hasattr(self, "out_dir_bugs"), \
            "Must run after ._create_output_directories()"

        stack = []
        comment_entries = []
        for depth,comment in bug.comment_root.thread(flatten=False):
            while len(stack) > depth:
                # pop non-parents off the stack
                stack.pop(-1)
                # close non-parent <div class="comment...
                comment_entries.append("</div>\n")
            assert len(stack) == depth
            stack.append(comment)
            if depth == 0:
                comment_entries.append('<div class="comment root">')
            else:
                comment_entries.append('<div class="comment">')
            template_info = {}
            for attr in ['uuid', 'author', 'date', 'body']:
                value = getattr(comment, attr)
                if attr == 'body':
                    save_body = False
                    if comment.content_type == 'text/html':
                        pass # no need to escape html...
                    elif comment.content_type.startswith('text/'):
                        value = '<pre>\n'+self._escape(value)+'\n</pre>'
                    elif comment.content_type.startswith('image/'):
                        save_body = True
                        value = '<img src="./%s/%s" />' \
                            % (bug.uuid, comment.uuid)
                    else:
                        save_body = True
                        value = '<a href="./%s/%s">Link to %s file</a>.' \
                            % (bug.uuid, comment.uuid, comment.content_type)
                    if save_body == True:
                        per_bug_dir = os.path.join(self.out_dir_bugs, bug.uuid)
                        if not os.path.exists(per_bug_dir):
                            os.mkdir(per_bug_dir)
                        comment_path = os.path.join(per_bug_dir, comment.uuid)
                        self._write_file(
                            '<Files %s>\n  ForceType %s\n</Files>' \
                                % (comment.uuid, comment.content_type),
                            [per_bug_dir, '.htaccess'], mode='a')
                        self._write_file(
                            comment.body,
                            [per_bug_dir, comment.uuid], mode='wb')
                else:
                    value = self._escape(value)
                template_info[attr] = value
            comment_entries.append(self.bug_comment_entry % template_info)
        while len(stack) > 0:
            stack.pop(-1)
            comment_entries.append("</div>\n") # close every remaining <div class="comment...
        return '\n'.join(comment_entries)

    def _write_index_file(self, bugs, title, index_header, bug_type="active"):
        if self.verbose:
            print "Writing %s index file for %d bugs" % (bug_type, len(bugs))
        assert hasattr(self, "out_dir"), "Must run after ._create_output_directories()"
        esc = self._escape

        bug_entries = self._generate_index_bug_entries(bugs)

        if bug_type == "active":
            filename = "index.html"
        elif bug_type == "inactive":
            filename = "index_inactive.html"
        else:
            raise Exception, "Unrecognized bug_type: '%s'" % bug_type
        template_info = {'title':title,
                         'index_header':index_header,
                         'charset':self.encoding,
                         'active_class':'tab sel',
                         'inactive_class':'tab nsel',
                         'bug_entries':bug_entries,
                         'generation_time':self.generation_time}
        if bug_type == "inactive":
            template_info['active_class'] = 'tab nsel'
            template_info['inactive_class'] = 'tab sel'

        self._write_file(self.index_file % template_info,
                         [self.out_dir, filename])

    def _generate_index_bug_entries(self, bugs):
        bug_entries = []
        for bug in bugs:
            if self.verbose:
                print "\tCreating bug entry for %s" % self.bd.bug_shortname(bug)
            template_info = {'shortname':self.bd.bug_shortname(bug)}
            for attr in ['uuid', 'severity', 'status', 'assigned',
                         'reporter', 'creator', 'time_string', 'summary']:
                template_info[attr] = self._escape(getattr(bug, attr))
            bug_entries.append(self.index_bug_entry % template_info)
        return '\n'.join(bug_entries)

    def _escape(self, string):
        if string == None:
            return ""
        chars = []
        for char in string:
            codepoint = ord(char)
            if codepoint in htmlentitydefs.codepoint2name:
                char = "&%s;" % htmlentitydefs.codepoint2name[codepoint]
            #else: xml.sax.saxutils.escape(char)
            chars.append(char)
        return "".join(chars)

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
                raise cmdutil.UsageError, "Cannot create output directory '%s'." % dir_path
        return dir_path

    def _write_file(self, content, path_array, mode='w'):
        f = codecs.open(os.path.join(*path_array), mode, self.encoding)
        f.write(content)
        f.close()

    def _read_file(self, path_array, mode='r'):
        f = codecs.open(os.path.join(*path_array), mode, self.encoding)
        content = f.read()
        f.close()
        return content

    def write_default_template(self, out_dir):
        if self.verbose:
            print "Creating output directories"
        self.out_dir = self._make_dir(out_dir)
        if self.verbose:
            print "Creating css file"
        self._write_css_file()
        if self.verbose:
            print "Creating index_file.tpl file"
        self._write_file(self.index_file,
                         [self.out_dir, "index_file.tpl"])
        if self.verbose:
            print "Creating index_bug_entry.tpl file"
        self._write_file(self.index_bug_entry,
                         [self.out_dir, "index_bug_entry.tpl"])
        if self.verbose:
            print "Creating bug_file.tpl file"
        self._write_file(self.bug_file,
                         [self.out_dir, "bug_file.tpl"])
        if self.verbose:
            print "Creating bug_comment_entry.tpl file"
        self._write_file(self.bug_comment_entry,
                         [self.out_dir, "bug_comment_entry.tpl"])

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
            Name: %(uuid)s<br/>
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
