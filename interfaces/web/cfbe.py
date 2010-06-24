#!/usr/bin/env python

import cherrypy
import web
from optparse import OptionParser
from os import path

module_dir = path.dirname(path.abspath(web.__file__))
template_dir = path.join(module_dir, 'templates')

def build_parser():
    """Builds and returns the command line option parser."""
    
    usage = 'usage: %prog bug_directory'
    parser = OptionParser(usage)
    return parser

def parse_arguments():
    """Parse the command line arguments."""
    
    parser = build_parser()
    (options, args) = parser.parse_args()
    
    if len(args) != 1:
        parser.error('You need to specify a bug directory.')
    
    return { 'bug_root': args[0], }


config = path.join(module_dir, 'cfbe.config')
options = parse_arguments()

WebInterface = web.WebInterface(path.abspath(options['bug_root']), template_dir)

cherrypy.config.update({'tools.staticdir.root': path.join(module_dir, 'static')})
app_config = { '/static': { 'tools.staticdir.on': True,
                            'tools.staticdir.dir': '', } }
cherrypy.quickstart(WebInterface, '/', app_config)
