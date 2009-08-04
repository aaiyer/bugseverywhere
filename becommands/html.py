# Copyright (C) 2005-2009 Aaron Bentley and Panometrics, Inc.
#                         Marien Zwart <marienz@gentoo.org>
#                         Thomas Gerigk <tgerigk@gmx.de>
#                         W. Trevor King <wking@drexel.edu>
# <abentley@panoramicfeedback.com>
#
#    This program is free software; you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation; either version 2 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program; if not, write to the Free Software
#    Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
"""Re-open a bug"""
from libbe import cmdutil, bugdir, bug
#from html_data import *
import os,  re,  time, string

__desc__ = __doc__

def execute(args, test=False):
    """
    >>> import os
    >>> bd = bugdir.simple_bug_dir()
    >>> os.chdir(bd.root)
    >>> print bd.bug_from_shortname("b").status
    closed
    >>> execute(["b"], test=True)
    >>> bd._clear_bugs()
    >>> print bd.bug_from_shortname("b").status
    open
    """
    parser = get_parser()
    options, args = parser.parse_args(args)
    complete(options, args, parser)
    cmdutil.default_complete(options, args, parser,
                             bugid_args={0: lambda bug : bug.active==False})
    
    if len(args) == 0:
        out_dir = options.outdir
        print "Creating the html output in %s"%out_dir
    else:
        out_dir = args[0]
    if len(args) > 0:
        raise cmdutil.UsageError, "Too many arguments."
    
    bd = bugdir.BugDir(from_disk=True, manipulate_encodings=not test)
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
    for b in bd:
        stime[b.uuid]  = b.time
        if b.status in ["open", "test", "unconfirmed", "assigned"]:
            bugs_active.append(b)
        else:
            bugs_inactive.append(b)
        st[b.status] += 1
    ordered_bug_list = sorted([(value,key) for (key,value) in stime.items()])
    ordered_bug_list_in = sorted([(value,key) for (key,value) in stime.items()])
    #open_bug_list = sorted([(value,key) for (key,value) in bugs.items()])
    
    html_gen = BEHTMLGen(bd)
    html_gen.create_index_file(out_dir,  st, bugs_active, ordered_bug_list, "active")
    html_gen.create_index_file(out_dir,  st, bugs_inactive, ordered_bug_list, "inactive")
    
def get_parser():
    parser = cmdutil.CmdOptionParser("be open OUTPUT_DIR")
    parser.add_option("-o", "--output", metavar="export_dir", dest="outdir",
        help="Set the output path, default is ./html_export", default="html_export")    
    return parser

longhelp="""
Generate a set of html pages.
"""

def help():
    return get_parser().help_str() + longhelp

def complete(options, args, parser):
    for option, value in cmdutil.option_value_pairs(options, parser):
        if "--complete" in args:
            raise cmdutil.GetCompletions() # no positional arguments for list
        
    
class BEHTMLGen():
    def __init__(self, bd):
        self.index_value = ""    
        self.bd = bd
        
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
        <html xmlns="http://www.w3.org/1999/xhtml" xml:lang="en" lang="en">
        <head>
        <title>BugsEverywhere Issue Tracker</title>
        <meta http-equiv="Content-Type" content="text/html; charset=utf-8" />
        <link rel="stylesheet" href="style.css" type="text/css" />
        </head>
        <body>
        
        
        <div class="main">
        <h1>BugsEverywhere Bug List</h1>
        <p></p>
        <table>
        
        <tr>
        <td class=%s><a href="index.html">Active Bugs</a></td>
        <td class=%s><a href="index_inactive.html">Inactive Bugs</a></td>
        </tr>
        
        </table>
        <table class=table_bug>
        <tbody>
        """    
        
        self.bug_line ="""
        <tr class=%s-row cellspacing=1>
        <td ><a href="bugs/%s.html">%s</a></td>
        <td ><a href="bugs/%s.html">%s</a></td>
        <td><a href="bugs/%s.html">%s</a></td>
        <td><a href="bugs/%s.html">%s</a></td>
        <td><a href="bugs/%s.html">%s</a></td>
        </tr>
        """
        
        self.detail_first = """
        <html xmlns="http://www.w3.org/1999/xhtml" xml:lang="en" lang="en">
        <head>
        <title>BugsEverywhere Issue Tracker</title>
        <meta http-equiv="Content-Type" content="text/html; charset=utf-8" />
        <link rel="stylesheet" href="../style.css" type="text/css" />
        </head>
        <body>
        
        
        <div class="main">
        <h1>BugsEverywhere Bug List</h1>
        <h5><a href="%s">Back to Index</a></h5>
        <h2>Bug: _bug_id_</h2>
        <table >
        <tbody>
        """   
        
        
        
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
        <td align=right>Comments:
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
        
        
    def create_index_file(self, out_dir_path,  summary,  bugs, ordered_bug, fileid):
        try:
            os.stat(out_dir_path)
        except:
            try:
                os.mkdir(out_dir_path)
            except:
                raise  cmdutil.UsageError, "Cannot create output directory."
        try:
            FO = open(out_dir_path+"/style.css", "w")
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
                FO = open(out_dir_path+"/index.html", "w")
                FO.write(self.index_first%('td_sel','td_nsel'))
            if fileid == "inactive":
                FO = open(out_dir_path+"/index_inactive.html", "w")
                FO.write(self.index_first%('td_nsel','td_sel'))
        except:
            raise  cmdutil.UsageError, "Cannot create the index.html file."
        
        c = 0
        t = len(bugs) - 1
        for l in range(t,  -1,  -1):
            line = self.bug_line%(bugs[l].severity,
            bugs[l].uuid, bugs[l].uuid[0:3],
            bugs[l].uuid,  bugs[l].status,
            bugs[l].uuid,  bugs[l].severity,
            bugs[l].uuid,  bugs[l].summary,
            bugs[l].uuid,  bugs[l].time_string
            )
            FO.write(line)
            c += 1
            self.create_detail_file(bugs[l], out_dir_path, fileid)
        when = time.ctime()
        FO.write(self.index_last%when)


    def create_detail_file(self, bug, out_dir_path, fileid):
        f = "%s.html"%bug.uuid
        p = out_dir_path+"/bugs/"+f
        try:
            FD = open(p, "w")
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
        FD.write(self.detail_line%("Short name : ", bug.uuid[0:3]))
        FD.write(self.detail_line%("Severity : ", bug.severity))
        FD.write(self.detail_line%("Status : ", bug.status))
        FD.write(self.detail_line%("Assigned : ", bug.assigned))
        FD.write(self.detail_line%("Target : ", bug.target))
        FD.write(self.detail_line%("Reporter : ", bug.reporter))
        FD.write(self.detail_line%("Creator : ", bug.creator))
        FD.write(self.detail_line%("Created : ", bug.time_string))
        FD.write(self.detail_line%("Summary : ", bug.summary))
        FD.write("<tr><td colspan=2><hr></td></tr>")
        FD.write(self.begin_comment_section)
        tr = []
        b = ''
        level = 0
        for i in bug_.comments():
            if not isinstance(i.in_reply_to,str):
                first = True
                a = i.string_thread(flatten=False)
                d = re.split('\n',a)
                for x in range(0,len(d)):
                    hr = ""
                    if re.match(" *--------- Comment ---------",d[x]):
                        com = """
                        %s<br>
                        %s<br>
                        %s<br>
                        %s<br>
                        %s<br>
                        """%(d[x+1],d[x+2],d[x+3],d[x+4],d[x+5])
                        l = re.sub("--------- Comment ---------", "", d[x])
                        ll = l.split("  ")
                        la = l
                        ba = ""
                        if len(la) > level:
                            FD.write("<div class='comment'>")
                        if len(la) < level:
                            FD.write("</div>")
                        if len(la) == 0:
                            if not first :
                                FD.write("</div>")
                                first = False
                            FD.write("<div class='commentF'>")
                        level = len(la)
                        x += 5
                        FD.write("--------- Comment ---------<p />")
                        FD.write(com)
                FD.write("</div>")
        FD.write(self.end_comment_section)
        if fileid == "active":
            FD.write(self.detail_last%"../index.html")
        if fileid == "inactive":
            FD.write(self.detail_last%"../index_inactive.html")
        FD.close()
        
   