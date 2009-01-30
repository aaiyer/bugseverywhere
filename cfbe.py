#!/usr/bin/env python

import cherrypy
from libbe import bugdir
from jinja2 import Environment, FileSystemLoader

bug_root = '/Users/sjl/Documents/stevelosh/.be'
bd = bugdir.BugDir(root=bug_root)
bd.load_all_bugs()

template_root = '/Users/sjl/Documents/cherryflavoredbugseverywhere/templates'
env = Environment(loader=FileSystemLoader(template_root))

class WebInterface:
    """The web interface to CFBE."""
    
    @cherrypy.expose
    def index(self):
        template = env.get_template('list.html')
        return template.render(bugs=bd)
    

config = '/Users/sjl/Documents/cherryflavoredbugseverywhere/cfbe.config'
cherrypy.quickstart(WebInterface(), '/', config)
