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
#from html_data import *
import codecs, os, re, string, time
import xml.sax.saxutils, htmlentitydefs

__desc__ = __doc__

def execute(args, manipulate_encodings=True):
    """
    >>> import os
    >>> bd = bugdir.SimpleBugDir()
    >>> os.chdir(bd.root)
    >>> execute([], manipulate_encodings=False)
    Creating the html output in html_export
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
    cmdutil.default_complete(options, args, parser,
                             bugid_args={0: lambda bug : bug.active==False})

    if len(args) == 0:
        out_dir = options.outdir
        template = options.template
        if template == None:
            _css_file = "default"
        else:
            _css_file = template
        if options.verbose == True:
            print "Creating the html output in %s using %s template"%(out_dir, _css_file)
    else:
        out_dir = args[0]
    if len(args) > 0:
        raise cmdutil.UsageError, "Too many arguments."
    
    bd = bugdir.BugDir(from_disk=True,
                       manipulate_encodings=manipulate_encodings)
    bd.load_all_bugs()
    status_list = bug.status_values
    severity_list = bug.severity_values
    st = {}
    se = {}
    stime = {}
    bugs_active = []
    bugs_inactive = []
    for s in status_list:
        st[s] = 0
    for b in sorted(bd, reverse=True):
        stime[b.uuid]  = b.time
        if b.active == True:
            bugs_active.append(b)
        else:
            bugs_inactive.append(b)
        st[b.status] += 1
    ordered_bug_list = sorted([(value,key) for (key,value) in stime.items()])
    ordered_bug_list_in = sorted([(value,key) for (key,value) in stime.items()])
    #open_bug_list = sorted([(value,key) for (key,value) in bugs.items()])
    
    html_gen = BEHTMLGen(bd, template, options.verbose)
    html_gen.create_index_file(out_dir,  st, bugs_active, ordered_bug_list, "active", bd.encoding)
    html_gen.create_index_file(out_dir,  st, bugs_inactive, ordered_bug_list, "inactive", bd.encoding)
    
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
    def __init__(self, bd, template, verbose):
        self.index_value = ""    
        self.bd = bd
        self.verbose = verbose
        if template == None:
            self.template = "default"
        else:
            self.template = template

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
        
        self.index_first = """
            <!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Strict//EN"
            "http://www.w3.org/TR/xhtml1/DTD/xhtml1-strict.dtd">
            <html xmlns="http://www.w3.org/1999/xhtml" xml:lang="en" lang="en">
            <head>
            <title>BugsEverywhere Issue Tracker</title>
            <meta http-equiv="Content-Type" content="text/html; charset=%s" />
            <link rel="stylesheet" href="style.css" type="text/css" />
            </head>
            <body>
            
            
            <div class="main">
            <h1>BugsEverywhere Bug List</h1>
            <p></p>
            <table>
            
            <tr>
            <td class="%%s"><a href="index.html">Active Bugs</a></td>
            <td class="%%s"><a href="index_inactive.html">Inactive Bugs</a></td>
            </tr>
            
            </table>
            <table class="table_bug">
            <tbody>
        """ % self.bd.encoding
        
        self.bug_line ="""
        <tr class="%s-row">
        <td ><a href="bugs/%s.html">%s</a></td>
        <td ><a href="bugs/%s.html">%s</a></td>
        <td><a href="bugs/%s.html">%s</a></td>
        <td><a href="bugs/%s.html">%s</a></td>
        <td><a href="bugs/%s.html">%s</a></td>
        </tr>
        """
        
        self.detail_first = """
        <!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Strict//EN"
          "http://www.w3.org/TR/xhtml1/DTD/xhtml1-strict.dtd">
        <html xmlns="http://www.w3.org/1999/xhtml" xml:lang="en" lang="en">
        <head>
        <title>BugsEverywhere Issue Tracker</title>
        <meta http-equiv="Content-Type" content="text/html; charset=%s" />
        <link rel="stylesheet" href="../style.css" type="text/css" />
        </head>
        <body>
        
        
        <div class="main">
        <h1>BugsEverywhere Bug List</h1>
        <h5><a href="%%s">Back to Index</a></h5>
        <h2>Bug: _bug_id_</h2>
        <table >
        <tbody>
        """ % self.bd.encoding
        
        self.detail_line ="""
        <tr>
        <td align="right">%s</td><td>%s</td>
        </tr>
        """
        
        self.index_last = """
        </tbody>
        </table>
        
        </div>
        
        <div class="footer">Generated by <a href="http://www.bugseverywhere.org/">BugsEverywhere</a> on %s</div>
        
        </body>
        </html>
        """
        
        self.comment_section = """
        """
        
        self.begin_comment_section ="""
        <tr>
        <td align="right">Comments:
        </td>
        <td>
        """
        
        
        self.end_comment_section ="""
        </td>
        </tr>
        """
        
        self.detail_last = """
        </tbody>
        </table>
        </div>
        <h5><a href="%s">Back to Index</a></h5>
        <div class="footer">Generated by <a href="http://www.bugseverywhere.org/">BugsEverywhere</a>.</div>
        </body>
        </html>
        """ 
        
        if template != None:
            try:
                FI = open("%s/style.css"%self.template)
                self.css_file = FI.read()
                FI.close()
            except:
                pass
            try:
                FI = open("%s/index_first.tpl"%self.template)
                self.index_first = FI.read()
                FI.close()
            except:
                pass
            try:
                FI.open("%s/bug_line.tpl"%self.template)
                self.bug_line = FI.read()
                FI.close()
            except:
                pass
            try:
                FI.open("%s/detail_first.tpl"%self.template)
                self.detail_first = FI.read()
                FI.close()
            except:
                pass
            try:
                FI = open("%s/index_last.tpl"%self.template)
                self.index_last = FI.read()
                FI.close()
            except:
                pass
             try:
                FI = open("%s/detail_last.tpl"%self.template)
                self.d_last = FI.read()
                FI.close()
            except:
                pass
           
            
        
    def create_index_file(self, out_dir_path,  summary,  bugs, ordered_bug, fileid, encoding):
        try:
            os.stat(out_dir_path)
        except:
            try:
                os.mkdir(out_dir_path)
            except:
                raise  cmdutil.UsageError, "Cannot create output directory."
        try:
            FO = codecs.open(out_dir_path+"/style.css", "w", encoding)
            FO.write(self.css_file)
            FO.close()
        except:
            raise  cmdutil.UsageError, "Cannot create the style.css file."
        
        try:
            os.mkdir(out_dir_path+"/bugs")
        except:
            pass
        
        try:
            if fileid == "active":
                if self.verbose:
                    print "Creating active bug index..."
                FO = codecs.open(out_dir_path+"/index.html", "w", encoding)
                FO.write(self.index_first%('td_sel','td_nsel'))
            if fileid == "inactive":
                if self.verbose:
                    print "Creating inactive bug index..."
                FO = codecs.open(out_dir_path+"/index_inactive.html", "w", encoding)
                FO.write(self.index_first%('td_nsel','td_sel'))
        except:
            raise  cmdutil.UsageError, "Cannot create the index.html file."
        
        c = 0
        t = len(bugs) - 1
        for l in range(t,  -1,  -1):
            if self.verbose:
                print "Creating bug entry: %s"%escape(bugs[l].uuid[0:3])
            line = self.bug_line%(escape(bugs[l].severity),
                                  escape(bugs[l].uuid), escape(bugs[l].uuid[0:3]),
                                  escape(bugs[l].uuid), escape(bugs[l].status),
                                  escape(bugs[l].uuid), escape(bugs[l].severity),
                                  escape(bugs[l].uuid), escape(bugs[l].summary),
                                  escape(bugs[l].uuid), escape(bugs[l].time_string)
                                  )
            FO.write(line)
            c += 1
            if self.verbose:
                print "\tCreating detail entry for bug: %s"%escape(bugs[l].uuid[0:3])
            self.create_detail_file(bugs[l], out_dir_path, fileid, encoding)
        when = time.ctime()
        FO.write(self.index_last%when)


    def create_detail_file(self, bug, out_dir_path, fileid, encoding):
        f = "%s.html"%bug.uuid
        p = out_dir_path+"/bugs/"+f
        try:
            FD = codecs.open(p, "w", encoding)
        except:
            raise  cmdutil.UsageError, "Cannot create the detail html file."

        detail_first_ = re.sub('_bug_id_', bug.uuid[0:3], self.detail_first)
        if fileid == "active":
            FD.write(detail_first_%"../index.html")
        if fileid == "inactive":
            FD.write(detail_first_%"../index_inactive.html")
            
        
         
        bug_ = self.bd.bug_from_shortname(bug.uuid)
        bug_.load_comments(load_full=True)
        
        FD.write(self.detail_line%("ID : ", bug.uuid))
        FD.write(self.detail_line%("Short name : ", escape(bug.uuid[0:3])))
        FD.write(self.detail_line%("Severity : ", escape(bug.severity)))
        FD.write(self.detail_line%("Status : ", escape(bug.status)))
        FD.write(self.detail_line%("Assigned : ", escape(bug.assigned)))
        FD.write(self.detail_line%("Target : ", escape(bug.target)))
        FD.write(self.detail_line%("Reporter : ", escape(bug.reporter)))
        FD.write(self.detail_line%("Creator : ", escape(bug.creator)))
        FD.write(self.detail_line%("Created : ", escape(bug.time_string)))
        FD.write(self.detail_line%("Summary : ", escape(bug.summary)))
        FD.write("<tr><td colspan=\"2\"><hr /></td></tr>")
        FD.write(self.begin_comment_section)
        tr = []
        b = ''
        level = 0
        stack = []
        for depth,comment in bug_.comment_root.thread(flatten=False):
            while len(stack) > depth:
                stack.pop(-1)      # pop non-parents off the stack
                FD.write("</div>\n") # close non-parent <div class="comment...
            assert len(stack) == depth
            stack.append(comment)
            lines = ["--------- Comment ---------",
                     "Name: %s" % comment.uuid,
                     "From: %s" % escape(comment.author),
                     "Date: %s" % escape(comment.date),
                     ""]
            lines.extend(escape(comment.body).splitlines())
            if depth == 0:
                FD.write('<div class="commentF">')
            else:
                FD.write('<div class="comment">')
            FD.write("<br />\n".join(lines)+"<br />\n")
        while len(stack) > 0:
            stack.pop(-1)
            FD.write("</div>\n") # close every remaining <div class="comment...
        FD.write(self.end_comment_section)
        if fileid == "active":
            FD.write(self.detail_last%"../index.html")
        if fileid == "inactive":
            FD.write(self.detail_last%"../index_inactive.html")
        FD.close()
        
   
