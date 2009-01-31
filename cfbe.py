#!/usr/bin/env python

import cherrypy
from libbe import bugdir
from jinja2 import Environment, FileSystemLoader


template_root = '/Users/sjl/Documents/cherryflavoredbugseverywhere/templates'
env = Environment(loader=FileSystemLoader(template_root))

class WebInterface:
    """The web interface to CFBE."""
    
    def __init__(self, bug_root):
        """Initialize the bug repository for this web interface."""
        self.bug_root = bug_root
        self.bd = bugdir.BugDir(root=self.bug_root)
        self.repository_name = self.bd.root.split('/')[-1]
    
    def get_common_information(self, assignee, target):
        possible_assignees = list(set([bug.assigned for bug in self.bd if bug.assigned != None]))
        possible_assignees.sort(key=unicode.lower)
        
        possible_targets = list(set([bug.target for bug in self.bd if bug.target != None]))
        possible_targets.sort(key=unicode.lower)
        
        return {'possible_assignees': possible_assignees,
                'possible_targets': possible_targets,}
    
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
        
        common_info = self.get_common_information(assignee, target)
        return template.render(bugs=bugs, bd=self.bd, label=label, 
                               assignees=common_info['possible_assignees'],
                               targets=common_info['possible_targets'],
                               repository_name=self.repository_name)
    

config = '/Users/sjl/Documents/cherryflavoredbugseverywhere/cfbe.config'
bug_root = '/Users/sjl/Documents/cherryflavoredbugseverywhere/.be'
cherrypy.quickstart(WebInterface(bug_root), '/', config)
