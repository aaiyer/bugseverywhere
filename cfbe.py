#!/usr/bin/env python

import cherrypy
from libbe import bugdir
from jinja2 import Environment, FileSystemLoader

bug_root = '/Users/sjl/Documents/cherryflavoredbugseverywhere/.be'
bd = bugdir.BugDir(root=bug_root)
bd.load_all_bugs()
repository_name = bd.root.split('/')[-1]

template_root = '/Users/sjl/Documents/cherryflavoredbugseverywhere/templates'
env = Environment(loader=FileSystemLoader(template_root))

class WebInterface:
    """The web interface to CFBE."""
    
    @cherrypy.expose
    def index(self, status='open', assignee=''):
        bd.load_all_bugs()
        
        if status == 'open':
            status = ['open', 'assigned', 'test', 'unconfirmed', 'wishlist']
            label = 'All Open Bugs'
        elif status == 'closed':
            status = ['closed', 'disabled', 'fixed', 'wontfix']
            label = 'All Closed Bugs'
        if assignee != '':
            if assignee == 'None':
                label += ' Currently Unassigned'
            else:
                label += ' Assigned to %s' % (assignee,)
        
        
        template = env.get_template('list.html')
        
        possible_assignees = list(set([bug.assigned for bug in bd if bug.assigned != None]))
        possible_assignees.sort(key=unicode.lower)
        
        bugs = [bug for bug in bd if bug.status in status]
        
        if assignee != '':
            if assignee == 'None':
                assignee = None
            bugs = [bug for bug in bugs if bug.assigned == assignee]
        
        return template.render(bugs=bugs, bd=bd, label=label, 
                               assignees=possible_assignees,
                               repository_name=repository_name)
    

config = '/Users/sjl/Documents/cherryflavoredbugseverywhere/cfbe.config'
cherrypy.quickstart(WebInterface(), '/', config)
