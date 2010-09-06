from datetime import datetime
from urllib import urlencode

from jinja2 import Environment, FileSystemLoader
import cherrypy

from libbe import storage
from libbe import bugdir
from libbe.command.depend import get_blocked_by, get_blocks
from libbe.command.target import add_target, remove_target
from libbe.command.target import bug_from_target_summary, bug_target
from libbe.command.util import bug_comment_from_user_id
from libbe.storage.util import settings_object


EMPTY = settings_object.EMPTY

def datetimeformat(value, format='%B %d, %Y at %I:%M %p'):
    """Takes a timestamp and revormats it into a human-readable string."""
    return datetime.fromtimestamp(value).strftime(format)


class WebInterface:
    """The web interface to CFBE."""
    
    def __init__(self, bug_root, template_root):
        """Initialize the bug repository for this web interface."""
        self.bug_root = bug_root
        store = storage.get_storage(self.bug_root)
        store.connect()
        version = store.storage_version()
        print version
        self.bd = bugdir.BugDir(store, from_storage=True)
        self.repository_name = self.bug_root.split('/')[-1]
        self.env = Environment(loader=FileSystemLoader(template_root))
        self.env.filters['datetimeformat'] = datetimeformat
    
    def get_common_information(self):
        """Returns a dict of common information that most pages will need."""
        possible_assignees = list(set(
          [unicode(bug.assigned) for bug in self.bd if bug.assigned != EMPTY]))
        possible_assignees.sort(key=unicode.lower)
        
        possible_targets = list(set(
          [unicode(bug.summary.rstrip("\n")) for bug in self.bd \
                if bug.severity == u"target"]))

        possible_targets.sort(key=unicode.lower)
        
        possible_statuses = [u'open', u'assigned', u'test', u'unconfirmed', 
                             u'closed', u'disabled', u'fixed', u'wontfix']
        
        possible_severities = [u'minor', u'serious', u'critical', u'fatal', 
                               u'wishlist']
        
        return {'possible_assignees': possible_assignees,
                'possible_targets': possible_targets,
                'possible_statuses': possible_statuses,
                'possible_severities': possible_severities,
                'repository_name': self.repository_name,}
    
    def filter_bugs(self, status, assignee, target):
        """Filter the list of bugs to return only those desired."""
        bugs = [bug for bug in self.bd if bug.status in status]
        
        if assignee != '':
            assignee = None if assignee == 'None' else assignee
            bugs = [bug for bug in bugs if bug.assigned == assignee]
        
        if target != '':
            target = None if target == 'None' else target
            if target == None:
                # Return all bugs that don't block any targets.
                return [bug for bug in bugs if not bug_target(self.bd, bug)]
            else:
                # Return all bugs that block the supplied target.
                targetbug = bug_from_target_summary(self.bd, target)
                if targetbug == None:
                    return []
                bugs = [bug for bug in get_blocked_by(self.bd, targetbug) if
                        bug.active]
        return bugs
    
    
    @cherrypy.expose
    def index(self, status='open', assignee='', target=''):
        """The main bug page.
        Bugs can be filtered by assignee or target.
        The bug database will be reloaded on each visit."""
        
        self.bd.load_all_bugs()
        
        if status == 'open':
            status = ['open', 'assigned', 'test', 'unconfirmed', 'wishlist']
            label = 'All Open Bugs'
        elif status == 'closed':
            status = ['closed', 'disabled', 'fixed', 'wontfix']
            label = 'All Closed Bugs'
        
        if assignee != '':
            label += ' Currently Unassigned' if assignee == 'None' \
                else ' Assigned to %s' % (assignee,)
        if target != '':
            label += ' Currently Unscheduled' if target == 'None' \
                else ' Scheduled for %s' % (target,)
        
        bugs = self.filter_bugs(status, assignee, target)
        if len(bugs) == 0:
            template = self.env.get_template('empty-list.html')
        else:
            template = self.env.get_template('list.html')

        common_info = self.get_common_information()
        return template.render(bugs=bugs, bd=self.bd, label=label, 
                               assignees=common_info['possible_assignees'],
                               targets=common_info['possible_targets'],
                               statuses=common_info['possible_statuses'],
                               severities=common_info['possible_severities'],
                               repository_name=common_info['repository_name'],
                               urlencode=urlencode)
    
    
    @cherrypy.expose
    def bug(self, id=''):
        """The page for viewing a single bug."""
        
        self.bd.load_all_bugs()
        
        bug, comment = bug_comment_from_user_id(self.bd, id)
        
        template = self.env.get_template('bug.html')
        common_info = self.get_common_information()

        # Determine which targets a bug has.
        # First, is this bug blocking any other bugs?
        targets = ''
        blocks = get_blocks(self.bd, bug)
        for targetbug in blocks:
            # Are any of those blocked bugs targets?
            blocker = self.bd.bug_from_uuid(targetbug.uuid)
            if blocker.severity == "target":
                targets += "%s " % blocker.summary
        
        return template.render(bug=bug, bd=self.bd, 
                               assignee='' if bug.assigned == EMPTY else bug.assigned,
                               target=targets,
                               assignees=common_info['possible_assignees'],
                               targets=common_info['possible_targets'],
                               statuses=common_info['possible_statuses'],
                               severities=common_info['possible_severities'],
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
        
        if body.strip() != '':
            bug.comment_root.new_reply(body=body)
            bug.save()

        raise cherrypy.HTTPRedirect(
            '/bug?%s' % urlencode({'id':bug.id.long_user()}),
            status=302)

    @cherrypy.expose
    def edit(self, id, status=None, target=None, assignee=None, severity=None, summary=None):
        """The view that handles editing bug details."""
        bug = self.bd.bug_from_uuid(id)
        
        if summary != None:
            bug.summary = summary
        else:
            bug.status = status if status != 'None' else None
            bug.assigned = assignee if assignee != 'None' else None
            bug.severity = severity if severity != 'None' else None
            
        if target:
            current_target = bug_target(self.bd, bug)
            if current_target:
                remove_target(self.bd, bug)
                if target != "None":
                    add_target(self.bd, bug, target)
            else:
                add_target(self.bd, bug, target)

        bug.save()

        raise cherrypy.HTTPRedirect(
            '/bug?%s' % urlencode({'id':bug.id.long_user()}),
            status=302)
    
