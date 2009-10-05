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
    parser.add_option("-t", "--template", metavar="template", dest="template",
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
        FI = open("./templates/%s/style.css"%self.template)
        self.css_file = FI.read()
        FI.close()
        
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
        
   
