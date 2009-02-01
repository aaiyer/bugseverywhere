#!/usr/bin/env python

import cherrypy
from libbe import bugdir
from jinja2 import Environment, FileSystemLoader
from datetime import datetime


def datetimeformat(value, format='%B %d, %Y at %I:%M %p'):
    return datetime.fromtimestamp(value).strftime(format)

template_root = '/Users/sjl/Documents/cherryflavoredbugseverywhere/templates'
env = Environment(loader=FileSystemLoader(template_root))
env.filters['datetimeformat'] = datetimeformat

class WebInterface:
    """The web interface to CFBE."""
    
    def __init__(self, bug_root):
        """Initialize the bug repository for this web interface."""
        self.bug_root = bug_root
        self.bd = bugdir.BugDir(root=self.bug_root)
        self.repository_name = self.bd.root.split('/')[-1]
    
    def get_common_information(self):
        possible_assignees = list(set([bug.assigned for bug in self.bd if bug.assigned != None]))
        possible_assignees.sort(key=unicode.lower)
        
        possible_targets = list(set([bug.target for bug in self.bd if bug.target != None]))
        possible_targets.sort(key=unicode.lower)
        
        possible_statuses = [u'open', u'assigned', u'test', u'unconfirmed', 
                             u'wishlist', u'closed', u'disabled', u'fixed', 
                             u'wontfix']
        
        return {'possible_assignees': possible_assignees,
                'possible_targets': possible_targets,
                'possible_statuses': possible_statuses,
                'repository_name': self.repository_name,}
    
    def filter_bugs(self, status, assignee, target):
        """Filter the list of bugs to return only those desired."""
        bugs = [bug for bug in self.bd if bug.status in status]
        
        if assignee != '':
            assignee = None if assignee == 'None' else assignee
            bugs = [bug for bug in bugs if bug.assigned == assignee]
        
        if target != '':
            target = None if target == 'None' else target
            bugs = [bug for bug in bugs if bug.target == target]
        
        return bugs
    
    
    @cherrypy.expose
    def index(self, status='open', assignee='', target=''):
        self.bd.load_all_bugs()
        
        if status == 'open':
            status = ['open', 'assigned', 'test', 'unconfirmed', 'wishlist']
            label = 'All Open Bugs'
        elif status == 'closed':
            status = ['closed', 'disabled', 'fixed', 'wontfix']
            label = 'All Closed Bugs'
        
        if assignee != '':
            label += ' Currently Unassigned' if assignee == 'None' else ' Assigned to %s' % (assignee,)
        if target != '':
            label += ' Currently Unschdeuled' if target == 'None' else ' Scheduled for %s' % (target,)
        
        template = env.get_template('list.html')
        bugs = self.filter_bugs(status, assignee, target)
        
        common_info = self.get_common_information()
        return template.render(bugs=bugs, bd=self.bd, label=label, 
                               assignees=common_info['possible_assignees'],
                               targets=common_info['possible_targets'],
                               statuses=common_info['possible_statuses'],
                               repository_name=common_info['repository_name'])
    
    
    @cherrypy.expose
    def bug(self, id=''):
        """The page for viewing a single bug."""
        
        self.bd.load_all_bugs()
        
        bug = self.bd.bug_from_shortname(id)
        
        template = env.get_template('bug.html')
        common_info = self.get_common_information()
        return template.render(bug=bug, bd=self.bd, 
                               assignees=common_info['possible_assignees'],
                               targets=common_info['possible_targets'],
                               statuses=common_info['possible_statuses'],
                               repository_name=common_info['repository_name'])
    
    
    @cherrypy.expose
    def create(self, summary):
        """The view that handles the creation of a new bug."""
        if summary.strip() != '':
            self.bd.new_bug(summary=summary).save()
        raise cherrypy.HTTPRedirect('/', status=302)
    
    
    @cherrypy.expose
    def comment(self, id, body):
        """The view that handles adding a comment."""
        bug = self.bd.bug_from_uuid(id)
        shortname = self.bd.bug_shortname(bug)
        
        if body.strip() != '':
            bug.comment_root.new_reply(body=body)
            bug.save()
        
        raise cherrypy.HTTPRedirect('/bug?id=%s' % (shortname,), status=302)
    

config = '/Users/sjl/Documents/cherryflavoredbugseverywhere/cfbe.config'
bug_root = '/Users/sjl/Desktop/be/.be'
cherrypy.quickstart(WebInterface(bug_root), '/', config)
