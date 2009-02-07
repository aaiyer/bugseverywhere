#!/usr/bin/env python

import cherrypy
from cherryflavoredbugseverywhere import web
from jinja2 import Environment, FileSystemLoader
from datetime import datetime
from optparse import OptionParser
from os import path

module_dir = path.dirname(path.abspath(web.__file__))

def datetimeformat(value, format='%B %d, %Y at %I:%M %p'):
    """Takes a timestamp and revormats it into a human-readable string."""
    return datetime.fromtimestamp(value).strftime(format)


template_root = path.join(module_dir, 'templates')
env = Environment(loader=FileSystemLoader(template_root))
env.filters['datetimeformat'] = datetimeformat

WebInterface = web.WebInterface(path.abspath(options['bug_root']))

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
cherrypy.quickstart(WebInterface, '/', config)
