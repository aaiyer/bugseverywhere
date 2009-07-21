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
from html_data import *
import os,  re,  time

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
    cmdutil.default_complete(options, args, parser,
                             bugid_args={0: lambda bug : bug.active==False})
    if len(args) == 0:
        out_dir = './html_export'
        print "Creating the html output in ./html_export"
    else:
        out_dir = args[0]
    if len(args) > 1:
        raise cmdutil.UsageError, "Too many arguments."
    
    bd = bugdir.BugDir(from_disk=True, manipulate_encodings=not test)
    bd.load_all_bugs()
    status_list = bug.status_values
    severity_list = bug.severity_values
    st = {}
    se = {}
    stime = {}
    bugs = []
    for s in status_list:
        st[s] = 0
    for b in bd:
        stime[b.uuid]  = b.time
        if b.status in ["open", "test", "unconfirmed", "assigned"]:
            bugs.append(b)
        st[b.status] += 1
    ordered_bug_list = sorted([(value,key) for (key,value) in stime.items()])
    #open_bug_list = sorted([(value,key) for (key,value) in bugs.items()])
    
    html_gen = BEHTMLGen(bd)
    html_gen.create_index_file(out_dir,  st, bugs, ordered_bug_list)
    
def get_parser():
    parser = cmdutil.CmdOptionParser("be open OUTPUT_DIR")
    return parser

longhelp="""
Generate a set of html pages.
"""

def help():
    return get_parser().help_str() + longhelp
    
    
class BEHTMLGen():
    def __init__(self, bd):
        self.index_value = ""    
        self.bd = bd
        
    def create_index_file(self, out_dir_path,  summary,  bugs, ordered_bug):
        try:
            os.stat(out_dir_path)
        except:
            try:
                os.mkdir(out_dir_path)
            except:
                raise  cmdutil.UsageError, "Cannot create output directory."
        try:
            FO = open(out_dir_path+"/style.css", "w")
            FO.write(css_file)
            FO.close()
        except:
            raise  cmdutil.UsageError, "Cannot create the style.css file."
        
        try:
            os.mkdir(out_dir_path+"/bugs")
        except:
            pass
        
        try:
            FO = open(out_dir_path+"/index.html", "w")
        except:
            raise  cmdutil.UsageError, "Cannot create the index.html file."
        
        FO.write(index_first)
        c = 0
        t = len(bugs) - 1
        for l in range(t,  -1,  -1):
            line = bug_line%(bugs[l].status,
            bugs[l].uuid, bugs[l].uuid[0:3],
            bugs[l].uuid,  bugs[l].status,
            bugs[l].uuid,  bugs[l].severity,
            bugs[l].uuid,  bugs[l].summary,
            bugs[l].uuid,  bugs[l].time_string
            )
            FO.write(line)
            c += 1
            self.CreateDetailFile(bugs[l], out_dir_path)
        FO.write(index_last)


    def CreateDetailFile(self, bug, out_dir_path):
        f = "%s.html"%bug.uuid
        p = out_dir_path+"/bugs/"+f
        try:
            FD = open(p, "w")
        except:
            raise  cmdutil.UsageError, "Cannot create the detail html file."

        detail_first_ = re.sub('_bug_id_', bug.uuid[0:3], detail_first)
        FD.write(detail_first_)
        
        
        
        bug_ = self.bd.bug_from_shortname(bug.uuid[0:3])
        bug_.load_comments(load_full=True)
        for i in bug_.comments():
            print i.uuid, i.in_reply_to
        
        FD.write(detail_line%("ID : ", bug.uuid))
        FD.write(detail_line%("Short name : ", bug.uuid[0:3]))
        FD.write(detail_line%("Severity : ", bug.severity))
        FD.write(detail_line%("Status : ", bug.status))
        FD.write(detail_line%("Assigned : ", bug.assigned))
        FD.write(detail_line%("Target : ", bug.target))
        FD.write(detail_line%("Reporter : ", bug.reporter))
        FD.write(detail_line%("Creator : ", bug.creator))
        FD.write(detail_line%("Created : ", bug.time_string))
        FD.write(detail_line%("Summary : ", bug.summary))
        FD.write("<tr></tr>")
        FD.write(detail_last)
        FD.close()