# Copyright (C) 2009-2012 Chris Ball <cjb@laptop.org>
#                         Gianluca Montecchi <gian@grys.it>
#                         Mathieu Clabaut <mathieu.clabaut@gmail.com>
#                         W. Trevor King <wking@drexel.edu>
#
# This file is part of Bugs Everywhere.
#
# Bugs Everywhere is free software: you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by the Free
# Software Foundation, either version 2 of the License, or (at your option) any
# later version.
#
# Bugs Everywhere is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or
# FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General Public License for
# more details.
#
# You should have received a copy of the GNU General Public License along with
# Bugs Everywhere.  If not, see <http://www.gnu.org/licenses/>.

import codecs
import htmlentitydefs
import os
import os.path
import re
import string
import time
import xml.sax.saxutils

from jinja2 import Environment, FileSystemLoader, DictLoader, ChoiceLoader

import libbe
import libbe.command
import libbe.command.util
import libbe.comment
import libbe.util.encoding
import libbe.util.id
import libbe.command.depend


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
    >>> os.path.exists(os.path.join(bd.storage.repo, 'html_export', 'bugs', 'a', 'index.html'))
    True
    >>> os.path.exists(os.path.join(bd.storage.repo, 'html_export', 'bugs', 'b', 'index.html'))
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
                        default='Bugs Everywhere Issue Tracker')),
                libbe.command.Option(name='index-header',
                    help='Set the index page headers (%default)',
                    arg=libbe.command.Argument(
                        name='index-header', metavar='STRING',
                        default='Bugs Everywhere Bug List')),
                libbe.command.Option(name='export-template', short_name='e',
                    help='Export the default template and exit.'),
                libbe.command.Option(name='export-template-dir', short_name='d',
                    help='Set the directory for the template export (%default)',
                    arg=libbe.command.Argument(
                        name='export-template-dir', metavar='DIR',
                        default='./default-templates/',
                        completion_callback=libbe.command.util.complete_path)),
                libbe.command.Option(name='min-id-length', short_name='l',
                    help='Attempt to truncate bug and comment IDs to this length.  Set to -1 for non-truncated IDs (%default)',
                    arg=libbe.command.Argument(
                        name='min-id-length', metavar='INT',
                        default=-1, type='int')),
                libbe.command.Option(name='verbose', short_name='v',
                    help='Verbose output, default is %default'),
                ])

    def _run(self, **params):
        if params['export-template'] == True:
            bugdir = None
        else:
            bugdir = self._get_bugdir()
            bugdir.load_all_bugs()
        html_gen = HTMLGen(bugdir,
                           template_dir=params['template-dir'],
                           title=params['title'],
                           header=params['index-header'],
                           min_id_length=params['min-id-length'],
                           verbose=params['verbose'],
                           stdout=self.stdout)
        if params['export-template'] == True:
            html_gen.write_default_template(params['export-template-dir'])
        else:
            html_gen.run(params['output'])

    def _long_help(self):
        return """
Generate a set of html pages representing the current state of the bug
directory.
"""

Html = HTML # alias for libbe.command.base.get_command_class()

class HTMLGen (object):
    def __init__(self, bd, template_dir=None,
                 title="Site Title", header="Header",
                 min_id_length=-1,
                 verbose=False, encoding=None, stdout=None,
                 ):
        self.generation_time = time.ctime()
        self.bd = bd
        self.title = title
        self.header = header
        self.verbose = verbose
        self.stdout = stdout
        if encoding != None:
            self.encoding = encoding
        else:
            self.encoding = libbe.util.encoding.get_text_file_encoding()
        self._load_templates(template_dir)
        self.min_id_length = min_id_length

    def run(self, out_dir):
        if self.verbose == True:
            print >> self.stdout, \
                'Creating the html output in %s using templates in %s' \
                % (out_dir, self.template)

        bugs_active = []
        bugs_inactive = []
        bugs_target = []
        bugs = [b for b in self.bd]
        bugs.sort()
        
        for b in bugs:
            if  b.active == True and b.severity != 'target':
                bugs_active.append(b)
            if b.active != True and b.severity != 'target':
                bugs_inactive.append(b)
            if b.severity == 'target':
                bugs_target.append(b)
        
        self._create_output_directories(out_dir)
        self._write_css_file()
        for b in bugs:
            if b.severity == 'target':
                up_link = '../../index_target.html'
            elif b.active:
                up_link = '../../index.html'
            else:
                up_link = '../../index_inactive.html'                
            self._write_bug_file(
                b, title=self.title, header=self.header,
                up_link=up_link)
        self._write_index_file(
            bugs_active, title=self.title,
            header=self.header, bug_type='active')
        self._write_index_file(
            bugs_inactive, title=self.title,
            header=self.header, bug_type='inactive')
        self._write_index_file(
            bugs_target, title=self.title,
            header=self.header, bug_type='target')

    def _truncated_bug_id(self, bug):
        return libbe.util.id._truncate(
            bug.uuid, bug.sibling_uuids(),
            min_length=self.min_id_length)

    def _truncated_comment_id(self, comment):
        return libbe.util.id._truncate(
            comment.uuid, comment.sibling_uuids(),
            min_length=self.min_id_length)

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
        template = self.template.get_template('style.css')
        self._write_file(template.render(), [self.out_dir, 'style.css'])

    def _write_bug_file(self, bug, title, header, up_link):
        if self.verbose:
            print >> self.stdout, '\tCreating bug file for %s' % bug.id.user()
        assert hasattr(self, 'out_dir_bugs'), \
            'Must run after ._create_output_directories()'
        index_type = ''
            
        if bug.active == True:
            index_type = 'Active'
        else:
            index_type = 'Inactive'
        if bug.severity == 'target':
            index_type = 'Target'
                
        bug.load_comments(load_full=True)
        bug.comment_root.sort(cmp=libbe.comment.cmp_time, reverse=True)
        dirname = self._truncated_bug_id(bug)
        fullpath = os.path.join(self.out_dir_bugs, dirname, 'index.html')
        template_info = {
            'title': title,
            'charset': self.encoding,
            'stylesheet': '../../style.css',
            'header': header,
            'backlinks': self.template.get_template('bug_backlinks.html'),
            'up_link': up_link,
            'index_type': index_type,
            'bug': bug,
            'comment_entry': self.template.get_template(
                'bug_comment_entry.html'),
            'comments': [(depth,comment) for depth,comment
                         in bug.comment_root.thread(flatten=False)],
            'comment_dir': self._truncated_comment_id,
            'format_body': self._format_comment_body,
            'div_close': _DivCloser(),
            'generation_time': self.generation_time,
            }
        fulldir = os.path.join(self.out_dir_bugs, dirname)
        if not os.path.exists(fulldir):
            os.mkdir(fulldir)
        template = self.template.get_template('bug.html')
        self._write_file(template.render(template_info), [fullpath])

    def _write_index_file(self, bugs, title, header, bug_type='active'):
        if self.verbose:
            print >> self.stdout, 'Writing %s index file for %d bugs' % (bug_type, len(bugs))
        assert hasattr(self, 'out_dir'), 'Must run after ._create_output_directories()'

        if bug_type == 'active':
            filename = 'index.html'
        elif bug_type == 'inactive':
            filename = 'index_inactive.html'
        elif bug_type == 'target':
            filename = 'index_by_target.html'
        else:
            raise ValueError('unrecognized bug_type: "%s"' % bug_type)

        template_info = {
            'title': title,
            'charset': self.encoding,
            'stylesheet': 'style.css',
            'header': header,
            'active_class': 'tab nsel',
            'inactive_class': 'tab nsel',
            'target_class': 'tab nsel',
            'bugs': bugs,
            'bug_entry': self.template.get_template('index_bug_entry.html'),
            'bug_dir': self._truncated_bug_id,
            'generation_time': self.generation_time,
            }
        template_info['%s_class' % bug_type] = 'tab sel'
        if bug_type == 'target':
            template = self.template.get_template('target_index.html')
            template_info['targets'] = [
                (target, sorted(libbe.command.depend.get_blocked_by(
                            self.bd, target)))
                for target in bugs]
        else:
            template = self.template.get_template('standard_index.html')           
        self._write_file(
            template.render(template_info)+'\n', [self.out_dir,filename])

    def _long_to_linked_user(self, text):
        """
        >>> import libbe.bugdir
        >>> bd = libbe.bugdir.SimpleBugDir(memory=False)
        >>> h = HTMLGen(bd)
        >>> h._long_to_linked_user('A link #abc123/a#, and a non-link #x#y#.')
        'A link <a href="./a/">abc/a</a>, and a non-link #x#y#.'
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
        '<a href="./a/">abc/a</a>'
        >>> h._long_to_linked_user_replacer([bd], 'abc123/a/0123')
        '<a href="./a/#0123">abc/a/012</a>'
        >>> h._long_to_linked_user_replacer([bd], 'x')
        '#x#'
        >>> h._long_to_linked_user_replacer([bd], '')
        '##'
        >>> bd.cleanup()
        """
        try:
            p = libbe.util.id.parse_user(bugdirs[0], long_id)
        except (libbe.util.id.MultipleIDMatches,
                libbe.util.id.NoIDMatches,
                libbe.util.id.InvalidIDStructure), e:
            return '#%s#' % long_id # re-wrap failures
        if p['type'] == 'bugdir':
            return '#%s#' % long_id
        elif p['type'] == 'bug':
            bug,comment = libbe.command.util.bug_comment_from_user_id(
                bugdirs[0], long_id)
            return '<a href="./%s/">%s</a>' \
                % (self._truncated_bug_id(bug), bug.id.user())
        elif p['type'] == 'comment':
            bug,comment = libbe.command.util.bug_comment_from_user_id(
                bugdirs[0], long_id)
            return '<a href="./%s/#%s">%s</a>' \
                % (self._truncated_bug_id(bug),
                   self._truncated_comment_id(comment),
                   comment.id.user())
        raise Exception('Invalid id type %s for "%s"'
                        % (p['type'], long_id))

    def _format_comment_body(self, bug, comment):
        link_long_ids = False
        save_body = False
        value = comment.body
        if comment.content_type == 'text/html':
            link_long_ids = True
        elif comment.content_type.startswith('text/'):
            value = '<pre>\n'+self._escape(value)+'\n</pre>'
            link_long_ids = True
        elif comment.content_type.startswith('image/'):
            save_body = True
            value = '<img src="./%s/%s" />' % (
                self._truncated_bug_id(bug),
                self._truncated_comment_id(comment))
        else:
            save_body = True
            value = '<a href="./%s/%s">Link to %s file</a>.' % (
                self._truncated_bug_id(bug),
                self._truncated_comment_id(comment),
                comment.content_type)
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
        return value

    def _escape(self, string):
        if string == None:
            return ''
        return xml.sax.saxutils.escape(string)

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
        for filename,text in self.template_dict.iteritems():
            if self.verbose:
                print >> self.stdout, 'Creating %s file'
            self._write_file(text, [self.out_dir, filename])

    def _load_templates(self, template_dir=None):
        if template_dir is not None:
            template_dir = os.path.abspath(os.path.expanduser(template_dir))

        self.template_dict = {
##
            'style.css':
"""body {
  font-family: "lucida grande", "sans serif";
  font-size: 14px;
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
  -moz-border-radius: 10px;
  
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
  -moz-border-radius: 10px;
}

div.header {
    font-size: xx-large;
    padding-left: 20px;
    padding-right: 20px;
    padding-top: 10px;
    font-weight:bold;
    padding-bottom: 10px;
    background: #305275;
    color: #fffee7;
    -moz-border-radius: 10px;
}

th.target_name {
    text-align:left;
    border: 1px solid;
    border-color: #305275;
    background-color: #305275;
    color: #fff;
    width: auto%;
    -moz-border-radius-topleft: 8px;
    -moz-border-radius-topright: 8px;
    padding-left: 5px;
    padding-right: 5px;
}

table {
  border-style: solid;
  border: 1px #c3d9ff;
  border-spacing: 0px 0px;
  width: auto;
  padding: 0px;
  
  }

tb { border: 1px; }

tr {
  vertical-align: top;
  border: 1px #c3d9ff;
  border-style: dotted;
  width: auto;
  padding: 0px;
}

th {
    border-width: 1px;
    border-style: solid;
    border-color: #c3d9ff;
    border-collapse: collapse;
    padding-left: 5px;
    padding-right: 5px;
}


td {
    border-width: 1px;
    border-color: #c3d9ff;
    border-collapse: collapse;
    padding-left: 5px;
    padding-right: 5px;
    width: auto%;
}

img { border-style: none; }

ul {
  list-style-type: none;
  padding: 0;
}

p { width: auto; }

p.backlink {
  width: auto;
  font-weight: bold;
}

a {
  background: inherit;
  text-decoration: none;
}

a { color: #553d41; }
a:hover { color: #003d41; }
a:visited { color: #305275; }
.footer a { color: #508d91; }

/* bug index pages */

td.tab {
  padding-right: 1em;
  padding-left: 1em;
}

td.sel.tab {
    background-color: #c3d9ff ;
    border: 1px solid #c3d9ff;
    font-weight:bold;    
    -moz-border-radius-topleft: 15px;
    -moz-border-radius-topright: 15px;
}

td.nsel.tab { 
    border: 1px solid #c3d9ff;
    font-weight:bold;    
    -moz-border-radius-topleft: 5px;
    -moz-border-radius-topright: 5px;
}

table.bug_list {
    border-width: 1px;
    border-style: solid;
    border-color: #c3d9ff;
    padding: 0px;
    width: 100%;            
    border: 1px solid #c3d9ff;
}

table.target_list {
    padding: 0px;
    width: 100%;
    margin-bottom: 10px;
}

table.target_list.td {
    border-width: 1px;
}

tr.wishlist { background-color: #DCFAFF;}
tr.wishlist:hover { background-color: #C2DCE1; }

tr.minor { background-color: #FFFFA6; }
tr.minor:hover { background-color: #E6E696; }

tr.serious { background-color: #FF9077;}
tr.serious:hover { background-color: #E6826B; }

tr.critical { background-color: #FF752A; }
tr.critical:hover { background-color: #D63905;}

tr.fatal { background-color: #FF3300;}
tr.fatal:hover { background-color: #D60000;}

td.uuid { width: 5%; border-style: dotted;}
td.status { width: 5%; border-style: dotted;}
td.severity { width: 5%; border-style: dotted;}
td.summary { border-style: dotted;}
td.date { width: 25%; border-style: dotted;}

/* bug detail pages */

td.bug_detail_label { text-align: right; border: none;}
td.bug_detail { border: none;}
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
""",
##
            'base.html':
"""<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Strict//EN"
  "http://www.w3.org/TR/xhtml1/DTD/xhtml1-strict.dtd">
<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="en" lang="en">
  <head>
    <title>{{ title }}</title>
    <meta http-equiv="Content-Type" content="text/html; charset={{ charset }}" />
    <link rel="stylesheet" href="{{ stylesheet }}" type="text/css" />
  </head>
  <body>
    <div class="header">{{ header }}</div>
    <div class="main">
      {% block content %}{% endblock %}
    </div>
    <div class="footer">
      <p>Generated by <a href="http://www.bugseverywhere.org/">
      Bugs Everywhere</a> on {{ generation_time }}</p>
      <p>
        <a href="http://validator.w3.org/check?uri=referer">
          Validate XHTML</a>&nbsp;|&nbsp;
        <a href="http://jigsaw.w3.org/css-validator/check?uri=referer">
          Validate CSS</a>
      </p>
    </div>
  </body>
</html>
""",
            'index.html':
"""{% extends "base.html" %}

{% block content %}
<table>
  <tbody>
    <tr>
      <td class="{{ active_class }}"><a href="index.html">Active Bugs</a></td>
      <td class="{{ inactive_class }}"><a href="index_inactive.html">Inactive Bugs</a></td>
      <td class="{{ target_class }}"><a href="index_by_target.html">Divided by target</a></td>
    </tr>
  </tbody>
</table>
{% if bugs %}
{% block bug_table %}{% endblock %}
{% else %}
<p>No bugs.</p>
{% endif %}
{% endblock %}
""",
##
            'standard_index.html':
"""{% extends "index.html" %}

{% block bug_table %}
<table class="bug_list">
  <thead>
    <tr>
      <th>UUID</th>
      <th>Status</th>
      <th>Severity</th>
      <th>Summary</th>
      <th>Date</th>
    </tr>
  </thead>
  <tbody>
    {% for bug in bugs %}
    {{ bug_entry.render({'bug':bug, 'dir':bug_dir(bug)}) }}
    {% endfor %}
  </tbody>
</table>
{% endblock %}
""",
##
        'target_index.html':
"""{% extends "index.html" %}

{% block bug_table %}
{% for target,bugs in targets %}
<table class="target_list">
  <thead>
    <tr>
      <th class="target_name" colspan="5">
        Target: {{ target.summary|e }} ({{ target.status|e }})
      </th>
    </tr>
    <tr>
      <th>UUID</th>
      <th>Status</th>
      <th>Severity</th>
      <th>Summary</th>
      <th>Date</th>
    </tr>
  </thead>
  <tbody>
    {% for bug in bugs %}
    {{ bug_entry.render({'bug':bug, 'dir':bug_dir(bug)}) }}
    {% endfor %}
  </tbody>
</table>
{% endfor %}
{% endblock %}
""",
##
            'index_bug_entry.html':
"""<tr class="{{ bug.severity }}">
  <td class="uuid"><a href="bugs/{{ dir }}/index.html">{{ bug.id.user()|e }}</a></td>
  <td class="status"><a href="bugs/{{ dir }}/index.html">{{ bug.status|e }}</a></td>
  <td class="severity"><a href="bugs/{{ dir }}/index.html">{{ bug.severity|e }}</a></td>
  <td class="summary"><a href="bugs/{{ dir }}/index.html">{{ bug.summary|e }}</a></td>
  <td class="date"><a href="bugs/{{ dir }}/index.html">{{ (bug.time_string or '')|e }}</a></td>
</tr>
""",
##
        'bug.html':
"""{% extends "base.html" %}

{% block content %}
{{ backlinks.render({'up_link': up_link, 'index_type':index_type}) }}
<h1>Bug: {{ bug.id.user()|e }}</h1>

<table>
  <tbody>
    <tr><td class="bug_detail_label">ID :</td>
        <td class="bug_detail">{{ bug.uuid|e }}</td></tr>
    <tr><td class="bug_detail_label">Short name :</td>
        <td class="bug_detail">{{ bug.id.user()|e }}</td></tr>
    <tr><td class="bug_detail_label">Status :</td>
        <td class="bug_detail">{{ bug.status|e }}</td></tr>
    <tr><td class="bug_detail_label">Severity :</td>
        <td class="bug_detail">{{ bug.severity|e }}</td></tr>
    <tr><td class="bug_detail_label">Assigned :</td>
        <td class="bug_detail">{{ (bug.assigned or '')|e }}</td></tr>
    <tr><td class="bug_detail_label">Reporter :</td>
        <td class="bug_detail">{{ (bug.reporter or '')|e }}</td></tr>
    <tr><td class="bug_detail_label">Creator :</td>
        <td class="bug_detail">{{ (bug.creator or '')|e }}</td></tr>
    <tr><td class="bug_detail_label">Created :</td>
        <td class="bug_detail">{{ (bug.time_string or '')|e }}</td></tr>
    <tr><td class="bug_detail_label">Summary :</td>
        <td class="bug_detail">{{ bug.summary|e }}</td></tr>
  </tbody>
</table>

<hr/>

{% if comments %}
{% for depth,comment in comments %}
{% if depth == 0 %}
<div class="comment root" id="C{{ comment_dir(comment) }}">
{% else %}
<div class="comment" id="C{{ comment_dir(comment) }}">
{% endif %}
{{ comment_entry.render({
       'depth':depth, 'bug': bug, 'comment':comment, 'comment_dir':comment_dir,
       'format_body': format_body, 'div_close': div_close}) }}
{{ div_close(depth) }}
{% endfor %}
{% if comments[-1][0] > 0 %}
{{ div_close(0) }}
{% endif %}
{% else %}
<p>No comments.</p>
{% endif %}
{{ backlinks.render({'up_link': up_link, 'index_type': index_type}) }}
{% endblock %}
""",
##
            'bug_backlinks.html':
"""<p class="backlink"><a href="{{ up_link }}">Back to {{ index_type }} Index</a></p>
<p class="backlink"><a href="../../index_by_target.html">Back to Target Index</a></p>
""",
##
            'bug_comment_entry.html':
"""<table>
  <tbody>
    <tr>
      <td class="bug_comment_label">Comment:</td>
      <td class="bug_comment">
        --------- Comment ---------<br/>
        ID: {{ comment.uuid }}<br/>
        Short name: {{ comment.id.user() }}<br/>
        From: {{ (comment.author or '')|e }}<br/>
        Date: {{ (comment.date or '')|e }}<br/>
        <br/>
        {{ format_body(bug, comment) }}
      </td>
    </tr>
  </tbody>
</table>
""",
            }

        loader = DictLoader(self.template_dict)

        if template_dir:
            file_system_loader = FileSystemLoader(template_dir)
            loader = ChoiceLoader([file_system_loader, loader])

        self.template = Environment(loader=loader)


class _DivCloser (object):
    def __init__(self, depth=0):
        self.depth = depth

    def __call__(self, depth):
        ret = []
        while self.depth >= depth:
            self.depth -= 1
            ret.append('</div>')
        self.depth = depth
        return '\n'.join(ret)
