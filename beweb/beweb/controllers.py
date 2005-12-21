import turbogears
from turbogears import controllers
import cherrypy
from libbe.bugdir import tree_root, cmp_severity, new_bug
from libbe import names
from config import projects
from restresource import RESTResource

def project_tree(project):
    try:
        return tree_root(projects[project][1])
    except KeyError:
        raise Exception("Unknown project %s" % project)

def expose_resource(html=None):
    def exposer(func):
        func = turbogears.expose(html=html)(func)
        func.expose_resource = True
        return func
    return exposer 

class Bug(RESTResource):
    @expose_resource(html="beweb.templates.edit_bug")
    def index(self, bug):
        return {"bug": bug, "project_id": self.parent}
    
    @turbogears.expose(html="beweb.templates.bugs")
    def list(self, sort_by=None, show_closed=False, action=None):
        if action == "New bug":
            self.new_bug()
        if show_closed == "False":
            show_closed = False
        bug_tree = project_tree(self.parent)
        bugs = list(bug_tree.list())
        if sort_by is None:
            def cmp_date(bug1, bug2):
                return -cmp(bug1.time, bug2.time)
            bugs.sort(cmp_date)
            bugs.sort(cmp_severity)
        return {"project_id"      : self.parent,
                "project_name"    : projects[self.parent][0],
                "bugs"            : bugs,
                "show_closed"     : show_closed,
               }

    def new_bug(self):
        bug = new_bug(self.bug_tree())
        bug.save()
        raise cherrypy.HTTPRedirect(bug_url(self.parent, bug.uuid))

    @expose_resource()
    def update(self, bug, status, severity, summary, action):
        bug.status = status
        bug.severity = severity
        bug.summary = summary
        bug.save()
        raise cherrypy.HTTPRedirect(bug_list_url(self.parent))

    def REST_instantiate(self, bug_uuid):
        return self.bug_tree().get_bug(bug_uuid)

    def bug_tree(self):
        return project_tree(self.parent)

def project_url(project_id=None):
    project_url = "/project/"
    if project_id is not None:
        project_url += "%s/" % project_id
    return turbogears.url(project_url)

def bug_url(project_id, bug_uuid=None):
    bug_url = "/project/%s/bug/" % project_id
    if bug_uuid is not None:
        bug_url += "%s/" % bug_uuid
    return turbogears.url(bug_url)

def bug_list_url(project_id, show_closed=False):
    bug_url = "/project/%s/bug/?show_closed=%s" % (project_id, 
                                                   str(show_closed))
    return turbogears.url(bug_url)


class Project(RESTResource):
    REST_children = {"bug": Bug()}
    @expose_resource(html="beweb.templates.projects")
    def index(self, project_id=None):
        if project_id is not None:
            raise cherrypy.HTTPRedirect(bug_url(project_id)) 
        else:
            return {"projects": projects}

    def REST_instantiate(self, project_id):
        return project_id


class Root(controllers.Root):
    project = Project()
    @turbogears.expose()
    def index(self):
        raise cherrypy.HTTPRedirect(project_url()) 
