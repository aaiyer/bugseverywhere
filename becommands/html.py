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
        if b.status == "open":
            bugs.append(b)
        st[b.status] += 1
    ordered_bug_list = sorted([(value,key) for (key,value) in stime.items()])
    #open_bug_list = sorted([(value,key) for (key,value) in bugs.items()])
    
    html_gen = BEHTMLGen()
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
    def __init__(self):
        self.index_value = ""        
        
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
        for l in range(t,  0,  -1):
            line = bug_line
            line1 = re.sub('_bug_id_link_', bugs[l].uuid, line)
            line = line1
            line1 = re.sub('_bug_id_', bugs[l].uuid[0:3], line)
            line = line1
            line1 = re.sub('_status_', bugs[l].status, line)
            line = line1
            line1 = re.sub('_sev_', bugs[l].severity, line)
            line = line1
            line1 = re.sub('_descr_', bugs[l].summary, line)
            line = line1
            line2 = re.sub('_time_',  time.ctime(bugs[l].time),  line1)
            if c%2 == 0:
                linef = re.sub('_ROW_',  "even-row",  line2)
            else:
                linef = re.sub('_ROW_',  "odd-row",  line2)
            FO.write(linef)
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
        
        FD.write(index_first)
        
        FD.write(index_last)
        FD.close()