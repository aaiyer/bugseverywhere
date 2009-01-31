#!/usr/bin/env python

import cherrypy
from libbe import bugdir
from jinja2 import Environment, FileSystemLoader

bug_root = '/Users/sjl/Documents/cherryflavoredbugseverywhere/.be'
bd = bugdir.BugDir(root=bug_root)
bd.load_all_bugs()

template_root = '/Users/sjl/Documents/cherryflavoredbugseverywhere/templates'
env = Environment(loader=FileSystemLoader(template_root))

class WebInterface:
    """The web interface to CFBE."""
    
    @cherrypy.expose
    def index(self, status='open'):
        bd.load_all_bugs()
        if status == 'open':
            status = ['open', 'assigned', 'test', 'unconfirmed', 'wishlist']
            label = 'Open'
        elif status == 'closed':
            status = ['closed', 'disabled', 'fixed', 'wontfix']
            label = 'Closed'
        template = env.get_template('list.html')
        bugs = [bug for bug in bd if bug.status in status]
        return template.render(bugs=bugs, bd=bd, label=label)
    

config = '/Users/sjl/Documents/cherryflavoredbugseverywhere/cfbe.config'
cherrypy.quickstart(WebInterface(), '/', config)
