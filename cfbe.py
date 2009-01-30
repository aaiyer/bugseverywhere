#!/usr/bin/env python

import cherrypy
from libbe import bugdir
from jinja2 import Environment, FileSystemLoader

template_root = '/Users/sjl/Documents/cherryflavoredbugseverywhere/templates'
bug_root = '/Users/sjl/Documents/stevelosh/.be'
bd = bugdir.BugDir(root=bug_root)
bd.load_all_bugs()

env = Environment(loader=FileSystemLoader(template_root))

class WebInterface:
    """The web interface to CFBE."""
    
    @cherrypy.expose
    def index(self):
        template = env.get_template('base.html')
        return template.render(bugs=bd)
    

cherrypy.quickstart(WebInterface())
