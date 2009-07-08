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
    for s in status_list:
        st[s] = 0
    for s in severity_list:
        se[s] = 0
    
    for b in bd:
        stime[b.uuid]  = b.time
        st[b.status] += 1
        se[b.severity] += 1
    stime_sorted = sorted([(value,key) for (key,value) in stime.items()])

    html_gen = BEHTMLGen()
    html_gen.create_index_file(out_dir,  st,  se,  stime_sorted)
    
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
        
    def create_index_file(self, out_dir_path,  summary,  severity,  last_bug):
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
        value = html_index
        for stat in summary:
            rep = "_"+stat+"_"
            val = str(summary[stat])
            value = re.sub(rep,  val,  value)
        for sev in severity:
            rep = "_"+sev+"_"
            val = str(severity[sev])
            value = re.sub(rep,  val, value)
        
        c = 0
        t = len(last_bug)-1
        for l in range(t,  0,  -1):
            line = ""
            line = re.sub('_BUG_ID_', last_bug[l][1], last_activity)
            line1 = re.sub('_BUG_', last_bug[l][1][0:3], line)
            line2 = re.sub('_DATE_',  time.ctime(last_bug[l][0]),  line1)
            if c%2 == 0:
                linef = re.sub('_ROW_',  "even-row",  line2)
            else:
                linef = re.sub('_ROW_',  "odd-row",  line2)
            self.index_value += linef
            c += 1
            if c == 10:
                break
        
        value = re.sub("_LAST_ACTVITY_", self.index_value, value)

        try:
            FO = open(out_dir_path+"/index.html", "w")
            FO.write(value)
            FO.close()
        except:
            raise  cmdutil.UsageError, "Cannot create the index.html file."
            
