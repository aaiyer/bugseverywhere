# Copyright (C) 2005-2012 Aaron Bentley <abentley@panoramicfeedback.com>
#                         Chris Ball <cjb@laptop.org>
#                         Gianluca Montecchi <gian@grys.it>
#                         Marien Zwart <marien.zwart@gmail.com>
#                         Mathieu Clabaut <mathieu.clabaut@gmail.com>
#                         Thomas Gerigk <tgerigk@gmx.de>
#                         W. Trevor King <wking@tremily.us>
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
import email.utils
import htmlentitydefs
import itertools
import os
import os.path
import re
import string
import time
import xml.sax.saxutils

from jinja2 import Environment, FileSystemLoader, DictLoader, ChoiceLoader

import libbe
import libbe.command
import libbe.command.depend
import libbe.command.target
import libbe.command.util
import libbe.comment
import libbe.util.encoding
import libbe.util.id
import libbe.util.wsgi
import libbe.version


class ServerApp (libbe.util.wsgi.WSGI_AppObject,
                 libbe.util.wsgi.WSGI_DataObject):
    """WSGI server for a BE Storage instance over HTML.

    Serve browsable HTML for public consumption.  Currently everything
    is read-only.
    """
    server_version = 'BE-html-server/' + libbe.version.version()

    def __init__(self, bugdirs={}, template_dir=None, title='Site Title',
                 header='Header', index_file='', min_id_length=-1,
                 strip_email=False, generation_time=None, **kwargs):
        super(ServerApp, self).__init__(
            urls=[
                (r'^{0}$'.format(index_file), self.index),
                (r'^style.css$', self.style),
                (r'^([^/]+)/([^/]+)/{0}'.format(index_file), self.bug),
                ],
            **kwargs)
        self.bugdirs = bugdirs
        self.title = title
        self.header = header
        self._index_file = index_file
        self.min_id_length = min_id_length
        self.strip_email = strip_email
        self.generation_time = generation_time
        self._refresh = 0
        self._load_templates(template_dir=template_dir)
        self._filters = {
            'active': lambda bug: bug.active and bug.severity != 'target',
            'inactive': lambda bug: not bug.active and bug.severity !='target',
            'target': lambda bug: bug.severity == 'target'
            }

    # handlers
    def style(self, environ, start_response): 
        template = self.template.get_template('style.css')
        content = template.render()
        return self.ok_response(
            environ, start_response, content, content_type='text/css')

    def index(self, environ, start_response):
        data = self.query_data(environ)
        source = 'query'
        bug_type = self.data_get_string(
            data, 'type', default='active', source=source)
        assert bug_type in ['active', 'inactive', 'target'], bug_type
        self.refresh()
        filter_ = self._filters.get(bug_type, self._filters['active'])
        bugs = list(itertools.chain(*list(
                    [bug for bug in bugdir if filter_(bug)]
                    for bugdir in self.bugdirs.values())))
        bugs.sort()
        if self.logger:
            self.logger.log(
                self.log_level, 'generate {0} index file for {1} bugs'.format(
                    bug_type, len(bugs)))
        template_info = {
            'title': self.title,
            'charset': 'UTF-8',
            'stylesheet': 'style.css',
            'header': self.header,
            'active_class': 'tab nsel',
            'inactive_class': 'tab nsel',
            'target_class': 'tab nsel',
            'bugs': bugs,
            'bug_entry': self.template.get_template('index_bug_entry.html'),
            'bug_dir': self.bug_dir,
            'index_file': self._index_file,
            'generation_time': self._generation_time(),
            }
        template_info['{0}_class'.format(bug_type)] = 'tab sel'
        if bug_type == 'target':
            template = self.template.get_template('target_index.html')
            template_info['targets'] = [
                (target, sorted(libbe.command.depend.get_blocked_by(
                            self.bugdirs, target)))
                for target in bugs]
        else:
            template = self.template.get_template('standard_index.html')           
        content = template.render(template_info)+'\n'
        return self.ok_response(
            environ, start_response, content, content_type='text/html')

    def bug(self, environ, start_response):
        try:
            bugdir_id,bug_id = environ['be-server.url_args']
        except:
            raise libbe.util.wsgi.HandlerError(404, 'Not Found')
        user_id = '{0}/{1}'.format(bugdir_id, bug_id)
        bugdir,bug,comment = (
            libbe.command.util.bugdir_bug_comment_from_user_id(
                self.bugdirs, user_id))
        if self.logger:
            self.logger.log(
                self.log_level, 'generate bug file for {0}/{1}'.format(
                    bugdir.uuid, bug.uuid))
        if bug.severity == 'target':
            index_type = 'target'
        elif bug.active:
            index_type = 'active'
        else:
            index_type = 'inactive'
        target = libbe.command.target.bug_target(self.bugdirs, bug)
        if target == bug:  # e.g. when bug.severity == 'target'
            target = None
        up_link = '../../{0}?type={1}'.format(self._index_file, index_type)
        bug.load_comments(load_full=True)
        bug.comment_root.sort(cmp=libbe.comment.cmp_time, reverse=True)
        template_info = {
            'title': self.title,
            'charset': 'UTF-8',
            'stylesheet': '../../style.css',
            'header': self.header,
            'backlinks': self.template.get_template('bug_backlinks.html'),
            'up_link': up_link,
            'index_type': index_type.capitalize(),
            'index_file': self._index_file,
            'bug': bug,
            'target': target,
            'comment_entry': self.template.get_template(
                'bug_comment_entry.html'),
            'comments': [(depth,comment) for depth,comment
                         in bug.comment_root.thread(flatten=False)],
            'bug_dir': self.bug_dir,
            'comment_dir': self._truncated_comment_id,
            'format_body': self._format_comment_body,
            'div_close': _DivCloser(),
            'strip_email': self._strip_email,
            'generation_time': self._generation_time(),
            }
        template = self.template.get_template('bug.html')
        content = template.render(template_info)
        return self.ok_response(
            environ, start_response, content, content_type='text/html')

    # helper functions
    def refresh(self):
        if time.time() > self._refresh:
            if self.logger:
                self.logger.log(self.log_level, 'refresh bugdirs')
            for bugdir in self.bugdirs.values():
                bugdir.load_all_bugs()
            self._refresh = time.time() + 60

    def _truncated_bugdir_id(self, bugdir):
        return libbe.util.id._truncate(
            bugdir.uuid, self.bugdirs.keys(),
            min_length=self.min_id_length)

    def _truncated_bug_id(self, bug):
        return libbe.util.id._truncate(
            bug.uuid, bug.sibling_uuids(),
            min_length=self.min_id_length)

    def _truncated_comment_id(self, comment):
        return libbe.util.id._truncate(
            comment.uuid, comment.sibling_uuids(),
            min_length=self.min_id_length)

    def bug_dir(self, bug):
        return '{0}/{1}'.format(
            self._truncated_bugdir_id(bug.bugdir),
            self._truncated_bug_id(bug))

    def _long_to_linked_user(self, text):
        """
        >>> import libbe.bugdir
        >>> bugdir = libbe.bugdir.SimpleBugDir(memory=False)
        >>> a = ServerApp(bugdirs={bugdir.uuid: bugdir})
        >>> a._long_to_linked_user('A link #abc123/a#, and a non-link #x#y#.')
        'A link <a href="./a/">abc/a</a>, and a non-link #x#y#.'
        >>> bugdir.cleanup()
        """
        replacer = libbe.util.id.IDreplacer(
            self.bugdirs, self._long_to_linked_user_replacer, wrap=False)
        return re.sub(
            libbe.util.id.REGEXP, replacer, text)

    def _long_to_linked_user_replacer(self, bugdirs, long_id):
        """
        >>> import libbe.bugdir
        >>> import libbe.util.id
        >>> bugdir = libbe.bugdir.SimpleBugDir(memory=False)
        >>> bugdirs = {bugdir.uuid: bugdir}
        >>> a = bugdir.bug_from_uuid('a')
        >>> uuid_gen = libbe.util.id.uuid_gen
        >>> libbe.util.id.uuid_gen = lambda : '0123'
        >>> c = a.new_comment('comment for link testing')
        >>> libbe.util.id.uuid_gen = uuid_gen
        >>> c.uuid
        '0123'
        >>> a = ServerApp(bugdirs=bugdirs)
        >>> a._long_to_linked_user_replacer(bugdirs, 'abc123')
        '#abc123#'
        >>> a._long_to_linked_user_replacer(bugdirs, 'abc123/a')
        '<a href="./a/">abc/a</a>'
        >>> a._long_to_linked_user_replacer(bugdirs, 'abc123/a/0123')
        '<a href="./a/#0123">abc/a/012</a>'
        >>> a._long_to_linked_user_replacer(bugdirs, 'x')
        '#x#'
        >>> a._long_to_linked_user_replacer(bugdirs, '')
        '##'
        >>> bugdir.cleanup()
        """
        try:
            p = libbe.util.id.parse_user(bugdirs, long_id)
        except (libbe.util.id.MultipleIDMatches,
                libbe.util.id.NoIDMatches,
                libbe.util.id.InvalidIDStructure), e:
            return '#%s#' % long_id # re-wrap failures
        if p['type'] == 'bugdir':
            return '#%s#' % long_id
        elif p['type'] == 'bug':
            bugdir,bug,comment = (
                libbe.command.util.bugdir_bug_comment_from_user_id(
                    bugdirs, long_id))
            return '<a href="./%s/">%s</a>' \
                % (self._truncated_bug_id(bug), bug.id.user())
        elif p['type'] == 'comment':
            bugdir,bug,comment = (
                libbe.command.util.bugdir_bug_comment_from_user_id(
                    bugdirs, long_id))
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

    def _generation_time(self):
        if self.generation_time:
            return self.generation_time
        return time.ctime()

    def _escape(self, string):
        if string == None:
            return ''
        return xml.sax.saxutils.escape(string)

    def _strip_email(self, string):
        if self.strip_email:
            name,address = email.utils.parseaddr(string)
            if name:
                return name
            return address
        return string

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
  border-radius: 10px;
  
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
  border-radius: 10px;
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
    border-radius: 10px;
}

th.target_name {
    text-align:left;
    border: 1px solid;
    border-color: #305275;
    background-color: #305275;
    color: #fff;
    width: auto;
    border-top-left-radius: 8px;
    border-top-right-radius: 8px;
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
    width: auto;
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
    border-top-left-radius: 15px;
    border-top-right-radius: 15px;
}

td.nsel.tab { 
    border: 1px solid #c3d9ff;
    font-weight:bold;    
    border-top-left-radius: 5px;
    border-top-right-radius: 5px;
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
##
            'bugdirs.html':
"""{% extends "base.html" %}

{% block content %}
{% if bugdirss %}
{% block bugdir_table %}{% endblock %}
{% else %}
<p>No bugdirs.</p>
{% endif %}
{% endblock %}
""",
##
            'index.html':
"""{% extends "base.html" %}

{% block content %}
<table>
  <tbody>
    <tr>
      <td class="{{ active_class }}"><a href="{% if index_file %}{{ index_file }}{% else %}.{% endif %}">Active Bugs</a></td>
      <td class="{{ inactive_class }}"><a href="{{ index_file }}?type=inactive">Inactive Bugs</a></td>
      <td class="{{ target_class }}"><a href="{{ index_file }}?type=target">Divided by target</a></td>
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
    {{ bug_entry.render({'bug':bug, 'dir':bug_dir(bug), 'index_file':index_file}) }}
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
    {{ bug_entry.render({'bug':bug, 'dir':bug_dir(bug), 'index_file':index_file}) }}
    {% endfor %}
  </tbody>
</table>
{% endfor %}
{% endblock %}
""",
##
            'index_bug_entry.html':
"""<tr class="{{ bug.severity }}">
  <td class="uuid"><a href="{{ dir }}/{{ index_file }}">{{ bug.id.user()|e }}</a></td>
  <td class="status"><a href="{{ dir }}/{{ index_file }}">{{ bug.status|e }}</a></td>
  <td class="severity"><a href="{{ dir }}/{{ index_file }}">{{ bug.severity|e }}</a></td>
  <td class="summary"><a href="{{ dir }}/{{ index_file }}">{{ bug.summary|e }}</a></td>
  <td class="date"><a href="{{ dir }}/{{ index_file }}">{{ (bug.time_string or '')|e }}</a></td>
</tr>
""",
##
        'bug.html':
"""{% extends "base.html" %}

{% block content %}
{{ backlinks.render({'up_link': up_link, 'index_type':index_type, 'index_file':index_file}) }}
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
        <td class="bug_detail">{{ strip_email(bug.assigned or '')|e }}</td></tr>
    <tr><td class="bug_detail_label">Reporter :</td>
        <td class="bug_detail">{{ strip_email(bug.reporter or '')|e }}</td></tr>
    <tr><td class="bug_detail_label">Creator :</td>
        <td class="bug_detail">{{ strip_email(bug.creator or '')|e }}</td></tr>
    <tr><td class="bug_detail_label">Created :</td>
        <td class="bug_detail">{{ (bug.time_string or '')|e }}</td></tr>
{% if target %}
    <tr><td class="bug_detail_label">Target :</td>
        <td class="bug_detail"><a href="../../{{ bug_dir(target) }}/{{ index_file }}">{{ target.summary }}</a></td></tr>
{% endif %}
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
       'format_body': format_body, 'div_close': div_close,
       'strip_email': strip_email}) }}
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
<p class="backlink"><a href="../../{{ index_file }}?type=target">Back to Target Index</a></p>
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
        From: {{ strip_email(comment.author or '')|e }}<br/>
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


class HTML (libbe.util.wsgi.ServerCommand):
    """Serve or dump browsable HTML for the current repository

    >>> import sys
    >>> import libbe.bugdir
    >>> bugdir = libbe.bugdir.SimpleBugDir(memory=False)
    >>> io = libbe.command.StringInputOutput()
    >>> io.stdout = sys.stdout
    >>> ui = libbe.command.UserInterface(io=io)
    >>> ui.storage_callbacks.set_storage(bugdir.storage)
    >>> cmd = HTML(ui=ui)

    >>> export_path = os.path.join(bugdir.storage.repo, 'html_export')
    >>> ret = ui.run(cmd, {'output': export_path, 'export-html': True})
    >>> os.path.exists(export_path)
    True
    >>> os.path.exists(os.path.join(export_path, 'index.html'))
    True
    >>> os.path.exists(os.path.join(export_path, 'index_inactive.html'))
    True
    >>> os.path.exists(os.path.join(export_path, bugdir.uuid))
    True
    >>> for bug in sorted(bugdir):
    ...     if os.path.exists(os.path.join(
    ...             export_path, bugdir.uuid, bug.uuid, 'index.html')):
    ...         print('got {0}'.format(bug.uuid))
    ...     else:
    ...         print('missing {0}'.format(bug.uuid))
    got a
    got b

    >>> ui.cleanup()
    >>> bugdir.cleanup()
    """
    name = 'html'

    def __init__(self, *args, **kwargs):
        super(HTML, self).__init__(*args, **kwargs)
        # ServerApp cannot write, so drop some security options
        self.options = [
            option for option in self.options
            if option.name not in [
                'read-only',
                'notify',
                'auth',
                ]]

        self.options.extend([
                libbe.command.Option(name='template-dir', short_name='t',
                    help=('Use different templates.  Defaults to internal '
                          'templates'),
                    arg=libbe.command.Argument(
                        name='template-dir', metavar='DIR',
                        completion_callback=libbe.command.util.complete_path)),
                libbe.command.Option(name='title',
                    help='Set the bug repository title',
                    arg=libbe.command.Argument(
                        name='title', metavar='STRING',
                        default='Bugs Everywhere Issue Tracker')),
                libbe.command.Option(name='index-header',
                    help='Set the index page headers',
                    arg=libbe.command.Argument(
                        name='index-header', metavar='STRING',
                        default='Bugs Everywhere Bug List')),
                libbe.command.Option(name='min-id-length', short_name='l',
                    help=('Attempt to truncate bug and comment IDs to this '
                          'length.  Set to -1 for non-truncated IDs'),
                    arg=libbe.command.Argument(
                        name='min-id-length', metavar='INT',
                        default=-1, type='int')),
                libbe.command.Option(name='strip-email',
                    help='Strip email addresses from person fields.'),
                libbe.command.Option(name='export-html', short_name='e',
                    help='Export all HTML pages and exit.'),
                libbe.command.Option(name='output', short_name='o',
                    help='Set the output path for HTML export',
                    arg=libbe.command.Argument(
                        name='output', metavar='DIR', default='./html_export',
                        completion_callback=libbe.command.util.complete_path)),
                libbe.command.Option(name='export-template', short_name='E',
                    help='Export the default template and exit.'),
                libbe.command.Option(name='export-template-dir', short_name='d',
                    help='Set the directory for the template export',
                    arg=libbe.command.Argument(
                        name='export-template-dir', metavar='DIR',
                        default='./default-templates/',
                        completion_callback=libbe.command.util.complete_path)),
                ])

    def _run(self, **params):
        if True in [params['export-template'], params['export-html']]:
            app = self._get_app(
                logger=None, storage=None, index_file='index.html',
                generation_time=time.ctime(), **params)
            if params['export-template']:
                self._write_default_template(
                    template_dict=app.template_dict,
                    out_dir=params['export-template-dir'])
            elif params['export-html']:
                self._write_static_pages(app=app, out_dir=params['output'])
            return 0
        # provide defaults for the dropped options
        params['read-only'] = True
        params['notify'] = None
        params['auth'] = None
        return super(HTML, self)._run(**params)

    def _get_app(self, logger, storage, index_file='', generation_time=None,
                 **kwargs):
        return ServerApp(
            logger=logger, bugdirs=self._get_bugdirs(),
            template_dir=kwargs['template-dir'],
            title=kwargs['title'],
            header=kwargs['index-header'],
            index_file=index_file,
            min_id_length=kwargs['min-id-length'],
            strip_email=kwargs['strip-email'],
            generation_time=generation_time)

    def _long_help(self):
        return """
Example usage::

    $ be html

Then point your browser at ``http://localhost:8000/``.

If either ``--export-html`` or ``export-template`` is set, the command
will exit after the dump without serving anything over the wire.
"""

    def _write_default_template(self, template_dict, out_dir):
        out_dir = self._make_dir(out_dir)
        for filename,text in template_dict.iteritems():
            self._write_file(text, [out_dir, filename])

    def _write_static_pages(self, app, out_dir):
        url_mappings = [
            ('index.html?type=active', 'index.html'),
            ('index.html?type=inactive', 'index_inactive.html'),
            ('index.html?type=target', 'index_by_target.html'),
            ]
        out_dir = self._make_dir(out_dir)
        caller = libbe.util.wsgi.WSGICaller()
        self._write_file(
            content=self._get_content(caller, app, 'style.css'),
            path_array=[out_dir, 'style.css'])
        for url,data_dict,path in [
            ('index.html', {'type': 'active'}, 'index.html'),
            ('index.html', {'type': 'inactive'}, 'index_inactive.html'),
            ('index.html', {'type': 'target'}, 'index_by_target.html'),
            ]:
            content = self._get_content(caller, app, url, data_dict)
            for url_,path_ in url_mappings:
                content = content.replace(url_, path_)
            self._write_file(content=content, path_array=[out_dir, path])
        for bugdir in app.bugdirs.values():
            for bug in bugdir:
                bug_dir_url = app.bug_dir(bug=bug)
                segments = bug_dir_url.split('/')
                path_array = [out_dir]
                path_array.extend(segments)
                bug_dir_path = os.path.join(*path_array)
                path_array.append(app._index_file)
                url = '{0}/{1}'.format(bug_dir_url, app._index_file)
                content = self._get_content(caller, app, url)
                for url_,path_ in url_mappings:
                    content = content.replace(url_, path_)
                if not os.path.isdir(bug_dir_path):
                    self._make_dir(bug_dir_path)                    
                self._write_file(content=content, path_array=path_array)

    def _get_content(self, caller, app, path, data_dict=None):
        try:
            return caller.getURL(app=app, path=path, data_dict=data_dict)
        except libbe.util.wsgi.HandlerError:
            self.stdout.write(
                'error retrieving {0} with {1}\n'.format(path, data_dict))
            raise

    def _make_dir(self, dir_path):
        dir_path = os.path.abspath(os.path.expanduser(dir_path))
        if not os.path.exists(dir_path):
            try:
                os.makedirs(dir_path)
            except:
                raise libbe.command.UserError(
                    'Cannot create output directory "{0}".'.format(dir_path))
        return dir_path

    def _write_file(self, content, path_array, mode='w'):
        if not hasattr(self, 'encoding'):
            self.encoding = libbe.util.encoding.get_text_file_encoding()
        return libbe.util.encoding.set_file_contents(
            os.path.join(*path_array), content, mode, self.encoding)


Html = HTML # alias for libbe.command.base.get_command_class()


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
