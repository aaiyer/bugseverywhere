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

def execute(args, manipulate_encodings=True):
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

    if len(args) == 0:
        out_dir = options.outdir
        template = options.template
        if template == None:
            _css_file = "default"
        else:
            _css_file = template
        if options.verbose == True:
            print "Creating the html output in %s using %s template"%(out_dir, _css_file)
    if len(args) > 0:
        raise cmdutil.UsageError, "Too many arguments."

    bd = bugdir.BugDir(from_disk=True,
                       manipulate_encodings=manipulate_encodings)
    bd.load_all_bugs()
    bugs_active = []
    bugs_inactive = []
    bugs = [b for b in bd]
    bugs.sort()
    bugs_active = [b for b in bugs if b.active == True]
    bugs_inactive = [b for b in bugs if b.active != True]

    html_gen = BEHTMLGen(bd, template, options.verbose, bd.encoding)
    html_gen.create_output_directories(out_dir)
    html_gen.write_css_file()
    for b in bugs:
        if b.active:
            up_link = "../index.html"
        else:
            up_link = "../index_inactive.html"
        html_gen.write_detail_file(b, up_link)
    html_gen.write_index_file(bugs_active, "active")
    html_gen.write_index_file(bugs_inactive, "inactive")

def get_parser():
    parser = cmdutil.CmdOptionParser("be html [options]")
    parser.add_option("-o", "--output", metavar="export_dir", dest="outdir",
        help="Set the output path, default is ./html_export", default="html_export")
    parser.add_option("-t", "--template-dir", metavar="template", dest="template",
        help="Use a different template, default is empty", default=None)
    parser.add_option("-v", "--verbose",  action="store_true", metavar="verbose", dest="verbose",
        help="Verbose output, default is no", default=False)
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


def escape(string):
    if string == None:
        return ""
    chars = []
    for char in xml.sax.saxutils.escape(string):
        codepoint = ord(char)
        if codepoint in htmlentitydefs.codepoint2name:
            char = "&%s;" % htmlentitydefs.codepoint2name[codepoint]
        chars.append(char)
    return "".join(chars)

class BEHTMLGen():
    def __init__(self, bd, template, verbose, encoding):
        self.index_value = ""
        self.bd = bd
        self.verbose = verbose
        self.encoding = encoding
        if template == None:
            self.template = "default"
        else:
            self.template = os.path.abspath(os.path.expanduser(template))

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

            .comment {
            padding: 20px;
            margin: auto;
            padding-top: 20px;
            margin-top: 0;
            }

            .commentF {
            padding: 0px;
            margin: auto;
            padding-top: 0px;
            paddin-bottom: 20px;
            margin-top: 0;
            }

            tb {
            border = 1;
            }

            .wishlist-row {
            background-color: #B4FF9B;
            width: auto;
            }

            .minor-row {
            background-color: #FCFF98;
            width: auto;
            }


            .serious-row {
            background-color: #FFB648;
            width: auto;
            }

            .critical-row {
            background-color: #FF752A;
            width: auto;
            }

            .fatal-row {
            background-color: #FF3300;
            width: auto;
            }

            .person {
            font-family: courier;
            }

            a, a:visited {
            background: inherit;
            text-decoration: none;
            }

            a {
            color: #003d41;
            }

            a:visited {
            color: #553d41;
            }

            ul {
            list-style-type: none;
            padding: 0;
            }

            p {
            width: auto;
            }

            .inline-status-image {
            position: relative;
            top: 0.2em;
            }

            .dimmed {
            color: #bbb;
            }

            table {
            border-style: 10px solid #313131;
            border-spacing: 0;
            width: auto;
            }

            table.log {
            }

            td {
            border-width: 0;
            border-style: none;
            padding-right: 0.5em;
            padding-left: 0.5em;
            width: auto;
            }

            .td_sel {
            background-color: #afafaf;
            border: 1px solid #afafaf;
            font-weight:bold;
            padding-right: 1em;
            padding-left: 1em;

            }

            .td_nsel {
            border: 0px;
            padding-right: 1em;
            padding-left: 1em;
            }

            tr {
            vertical-align: top;
            width: auto;
            }

            h1 {
            padding: 0.5em;
            background-color: #305275;
            margin-top: 0;
            margin-bottom: 0;
            color: #fff;
            margin-left: -20px;
            margin-right: -20px;
            }

            wid {
            text-transform: uppercase;
            font-size: smaller;
            margin-top: 1em;
            margin-left: -0.5em;
            /*background: #fffbce;*/
            /*background: #628a0d;*/
            padding: 5px;
            color: #305275;
            }

            .attrname {
            text-align: right;
            font-size: smaller;
            }

            .attrval {
            color: #222;
            }

            .issue-closed-fixed {
            background-image: "green-check.png";
            }

            .issue-closed-wontfix {
            background-image: "red-check.png";
            }

            .issue-closed-reorg {
            background-image: "blue-check.png";
            }

            .inline-issue-link {
            text-decoration: underline;
            }

            img {
            border: 0;
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

            .footer a {
            color: #508d91;
            }


            .header {
            font-family: "lucida grande", "sans serif";
            font-size: smaller;
            background-color: #a9a9a9;
            text-align: left;

            padding-right: 0.5em;
            padding-left: 0.5em;

            }


            .selected-cell {
            background-color: #e9e9e2;
            }

            .plain-cell {
            background-color: #f9f9f9;
            }


            .logcomment {
            padding-left: 4em;
            font-size: smaller;
            }

            .id {
            font-family: courier;
            }

            .table_bug {
            background-color: #afafaf;
            border: 2px solid #afafaf;
            }

            .message {
            }

            .progress-meter-done {
            background-color: #03af00;
            }

            .progress-meter-undone {
            background-color: #ddd;
            }

            .progress-meter {
            }
        """

        self.index_file = """
            <!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Strict//EN"
            "http://www.w3.org/TR/xhtml1/DTD/xhtml1-strict.dtd">
            <html xmlns="http://www.w3.org/1999/xhtml" xml:lang="en" lang="en">
            <head>
            <title>BugsEverywhere Issue Tracker</title>
            <meta http-equiv="Content-Type" content="text/html; charset=%(charset)s" />
            <link rel="stylesheet" href="style.css" type="text/css" />
            </head>
            <body>


            <div class="main">
            <h1>BugsEverywhere Bug List</h1>
            <p></p>
            <table>

            <tr>
            <td class="%(active_class)s"><a href="index.html">Active Bugs</a></td>
            <td class="%(inactive_class)s"><a href="index_inactive.html">Inactive Bugs</a></td>
            </tr>

            </table>
            <table class="table_bug">
            <tbody>

            %(bug_table)s

            </tbody>
            </table>

            </div>

            <div class="footer">
            <p>Generated by <a href="http://www.bugseverywhere.org/">
            BugsEverywhere</a> on %(generation_time)s</p>
            </div>

            </body>
            </html>
        """

        self.bug_line ="""
        <tr class="%(severity)s-row">
        <td ><a href="bugs/%(uuid)s.html">%(shortname)s</a></td>
        <td ><a href="bugs/%(uuid)s.html">%(status)s</a></td>
        <td><a href="bugs/%(uuid)s.html">%(severity)s</a></td>
        <td><a href="bugs/%(uuid)s.html">%(summary)s</a></td>
        <td><a href="bugs/%(uuid)s.html">%(time_string)s</a></td>
        </tr>
        """

        self.detail_file = """
        <!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Strict//EN"
          "http://www.w3.org/TR/xhtml1/DTD/xhtml1-strict.dtd">
        <html xmlns="http://www.w3.org/1999/xhtml" xml:lang="en" lang="en">
        <head>
        <title>BugsEverywhere Issue Tracker</title>
        <meta http-equiv="Content-Type" content="text/html; charset=%(charset)s" />
        <link rel="stylesheet" href="../style.css" type="text/css" />
        </head>
        <body>


        <div class="main">
        <h1>BugsEverywhere Bug List</h1>
        <h5><a href="%(up_link)s">Back to Index</a></h5>
        <h2>Bug: %(shortname)s</h2>
        <table >
        <tbody>

        %(bug_lines)s

        %(comment_lines)s
        </tbody>
        </table>
        </div>
        <h5><a href="%(up_link)s">Back to Index</a></h5>
        <div class="footer">Generated by <a href="http://www.bugseverywhere.org/">BugsEverywhere</a>.</div>
        </body>
        </html>

        """

        self.detail_line ="""
        <tr>
        <td align="right">%(label)s :</td><td>%(value)s</td>
        </tr>
        """


        self.comment_section ="""
        <tr>
        <td align="right">Comments:
        </td>
        <td>
        %(comment)s
        </td>
        </tr>
        """

        if template != None:
            for filename,attr in [('style.css','css_file'),
                                  ('index_file.tpl','index_file'),
                                  ('detail_file.tpl','detail_file'),
                                  ('comment_section.tpl','comment_section')]:
                fullpath = os.path.join(self.template, filename)
                if os.path.exists(fullpath):
                    f = codecs.open(fullpath, "r", self.encoding)
                    setattr(self, attr, f.read())
                    f.close()

    def create_output_directories(self, out_dir):
        if self.verbose:
            print "Creating output directories"
        self.out_dir = os.path.abspath(os.path.expanduser(out_dir))
        if not os.path.exists(self.out_dir):
            try:
                os.mkdir(self.out_dir)
            except:
                raise cmdutil.UsageError, "Cannot create output directory '%s'." % self.out_dir
        self.out_dir_bugs = os.path.join(self.out_dir, "bugs")
        if not os.path.exists(self.out_dir_bugs):
            os.mkdir(self.out_dir_bugs)

    def write_css_file(self):
        if self.verbose:
            print "Writing css file"
        assert hasattr(self, "out_dir"), "Must run after ._create_output_directories()"
        f = codecs.open(os.path.join(self.out_dir,"style.css"), "w", self.encoding)
        f.write(self.css_file)
        f.close()

    def write_detail_file(self, bug, up_link):
        if self.verbose:
            print "\tCreating detail entry for bug: %s" % escape(self.bd.bug_shortname(bug))
        assert hasattr(self, "out_dir_bugs"), "Must run after ._create_output_directories()"
        detail_file_ = re.sub('_bug_id_', bug.uuid[0:3], self.detail_file)

        bug_ = self.bd.bug_from_shortname(bug.uuid)
        bug_.load_comments(load_full=True)
        detail_lines = []
        for label,value in [('ID', bug.uuid),
                            ('Short name', escape(self.bd.bug_shortname(bug))),
                            ('Severity', escape(bug.severity)),
                            ('Status', escape(bug.status)),
                            ('Assigned', escape(bug.assigned)),
                            ('Target', escape(bug.target)),
                            ('Reporter', escape(bug.reporter)),
                            ('Creator', escape(bug.creator)),
                            ('Created', escape(bug.time_string)),
                            ('Summary', escape(bug.summary)),
                            ]:
            detail_lines.append(self.detail_line % {'label':label, 'value':value})
        detail_lines.append('<tr><td colspan="2"><hr /></td></tr>')

        stack = []
        comment_lines = []
        for depth,comment in bug_.comment_root.thread(flatten=False):
            while len(stack) > depth:
                stack.pop(-1)      # pop non-parents off the stack
                comment_lines.append("</div>\n") # close non-parent <div class="comment...
            assert len(stack) == depth
            stack.append(comment)
            lines = ["--------- Comment ---------",
                     "Name: %s" % comment.uuid,
                     "From: %s" % escape(comment.author),
                     "Date: %s" % escape(comment.date),
                     ""]
            lines.extend(escape(comment.body).splitlines())
            if depth == 0:
                comment_lines.append('<div class="commentF">')
            else:
                comment_lines.append('<div class="comment">')
            comment_lines.append("<br />\n".join(lines)+"<br />\n")
        while len(stack) > 0:
            stack.pop(-1)
            comment_lines.append("</div>\n") # close every remaining <div class="comment...
        comments = self.comment_section % {'comment':'\n'.join(comment_lines)}

        filename = "%s.html" % bug.uuid
        fullpath = os.path.join(self.out_dir_bugs, filename)
        template_info = {'charset':self.encoding,
                         'shortname':self.bd.bug_shortname(bug),
                         'up_link':up_link,
                         'bug_lines':'\n'.join(detail_lines),
                         'comment_lines':comments}
        f = codecs.open(fullpath, "w", self.encoding)
        f.write(detail_file_ % template_info)
        f.close()

    def write_index_file(self, bugs, fileid):
        if self.verbose:
            print "Writing %s index file for %d bugs" % (fileid, len(bugs))
        assert hasattr(self, "out_dir"), "Must run after ._create_output_directories()"

        bug_lines = []
        for b in bugs:
            if self.verbose:
                print "Creating bug entry: %s" % escape(self.bd.bug_shortname(b))
            template_info = {'uuid':b.uuid,
                             'shortname':self.bd.bug_shortname(b),
                             'status':b.status,
                             'severity':b.severity,
                             'summary':b.summary,
                             'time_string':b.time_string}
            bug_lines.append(self.bug_line % template_info)

        if fileid == "active":
            filename = "index.html"
        elif fileid == "inactive":
            filename = "index_inactive.html"
        else:
            raise Exception, "Unrecognized fileid: '%s'" % fileid
        template_info = {'charset':self.encoding,
                         'active_class':'td_sel',
                         'inactive_class':'td_nsel',
                         'bug_table':'\n'.join(bug_lines),
                         'generation_time':time.ctime()}
        if fileid == "inactive":
            template_info['active_class'] = 'td_nsel'
            template_info['inactive_class'] = 'td_sel'

        f = codecs.open(os.path.join(self.out_dir, filename), "w", self.encoding)
        f.write(self.index_file % template_info)
        f.close()
