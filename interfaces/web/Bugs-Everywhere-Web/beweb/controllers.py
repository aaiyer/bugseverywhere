import logging

import cherrypy
import turbogears
from turbogears import controllers, expose, validate, redirect, identity

from libbe.bugdir import tree_root, NoRootEntry
from config import projects
from prest import PrestHandler, provide_action


from beweb import json

log = logging.getLogger("beweb.controllers")

def project_tree(project):
    try:
        return tree_root(projects[project][1])
    except KeyError:
        raise Exception("Unknown project %s" % project)

def comment_url(project, bug, comment, **kwargs):
    return turbogears.url("/project/%s/bug/%s/comment/%s" %
                          (project, bug, comment), kwargs)

class Comment(PrestHandler):
    @identity.require( identity.has_permission("editbugs"))
    @provide_action("action", "New comment")
    def new_comment(self, comment_data, comment, *args, **kwargs):
        bug_tree = project_tree(comment_data['project'])
        bug = bug_tree.get_bug(comment_data['bug'])
        comment = new_comment(bug, "")
        comment.From = identity.current.user.userId
        comment.content_type = "text/restructured"
        comment.save()
        raise cherrypy.HTTPRedirect(comment_url(comment=comment.uuid, 
                                    **comment_data))

    @identity.require( identity.has_permission("editbugs"))
    @provide_action("action", "Reply")
    def reply_comment(self, comment_data, comment, *args, **kwargs):
        bug_tree = project_tree(comment_data['project'])
        bug = bug_tree.get_bug(comment_data['bug'])
        reply_comment = new_comment(bug, "")
        reply_comment.From = identity.current.user.userId
        reply_comment.in_reply_to = comment.uuid
        reply_comment.save()
        reply_data = dict(comment_data)
        del reply_data["comment"]
        raise cherrypy.HTTPRedirect(comment_url(comment=reply_comment.uuid, 
                                    **reply_data))

    @identity.require( identity.has_permission("editbugs"))
    @provide_action("action", "Update")
    def update(self, comment_data, comment, comment_body, *args, **kwargs):
        comment.body = comment_body
        comment.save()
        raise cherrypy.HTTPRedirect(bug_url(comment_data['project'], 
                                            comment_data['bug']))

    def instantiate(self, project, bug, comment):
        bug_tree = project_tree(project)
        bug = bug_tree.get_bug(bug)
        return bug.get_comment(comment)

    def dispatch(self, comment_data, comment, *args, **kwargs):
        return self.edit_comment(comment_data['project'], comment)

    @turbogears.expose(html="beweb.templates.edit_comment")
    def edit_comment(self, project, comment):
        return {"comment": comment, "project_id": project}

class Bug(PrestHandler):
    comment = Comment()
    @turbogears.expose(html="beweb.templates.edit_bug")
    def index(self, project, bug):
        return {"bug": bug, "project_id": project}
    
    def dispatch(self, bug_data, bug, *args, **kwargs):
        if bug is None:
            return self.list(bug_data['project'], **kwargs)
        else:
            return self.index(bug_data['project'], bug)

    @turbogears.expose(html="beweb.templates.bugs")
    def list(self, project, sort_by=None, show_closed=False, action=None, 
             search=None):
        if action == "New bug":
            self.new_bug()
        if show_closed == "False":
            show_closed = False
        bug_tree = project_tree(project)
        bugs = list(bug_tree.list())
        if sort_by is None:
            bugs.sort()
        return {"project_id"      : project,
                "project_name"    : projects[project][0],
                "bugs"            : bugs,
                "show_closed"     : show_closed,
                "search"          : search,
               }

    @identity.require( identity.has_permission("editbugs"))
    @provide_action("action", "New bug")
    def new_bug(self, bug_data, bug, **kwargs):
        bug = project_tree(bug_data['project']).new_bug()
        bug.creator = identity.current.user.userId
        bug.save()
        raise cherrypy.HTTPRedirect(bug_url(bug_data['project'], bug.uuid))

    @identity.require( identity.has_permission("editbugs"))
    @provide_action("action", "Update")
    def update(self, bug_data, bug, status, severity, summary, assigned, 
               action):
        bug.status = status
        bug.severity = severity
        bug.summary = summary
        if assigned == "":
            assigned = None
        bug.assigned = assigned
        bug.save()
#        bug.vcs.precommit(bug.path)
#        bug.vcs.commit(bug.path, "Auto-commit")
#        bug.vcs.postcommit(bug.path)
        raise cherrypy.HTTPRedirect(bug_list_url(bug_data["project"]))

    def instantiate(self, project, bug):
        return project_tree(project).get_bug(bug)

    @provide_action("action", "New comment")
    def new_comment(self, bug_data, bug, *args, **kwargs):
        try:
            self.update(bug_data, bug, *args, **kwargs)
        except cherrypy.HTTPRedirect:
            pass
        return self.comment.new_comment(bug_data, comment=None, *args, 
                                         **kwargs)


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

def bug_list_url(project_id, show_closed=False, search=None):
    bug_url = "/project/%s/bug/?show_closed=%s" % (project_id, 
                                                   str(show_closed))
    if search is not None:
        bug_url = "%s&search=%s" % (bug_url, search)
    return turbogears.url(str(bug_url))


class Project(PrestHandler):
    bug = Bug()
    @turbogears.expose(html="beweb.templates.projects")
    def dispatch(self, project_data, project, *args, **kwargs):
        if project is not None:
            raise cherrypy.HTTPRedirect(bug_url(project)) 
        else:
            return {"projects": projects}

    def instantiate(self, project):
        return project


class Root(controllers.Root):
    prest = PrestHandler()
    prest.project = Project()
    @turbogears.expose()
    def index(self):
        raise cherrypy.HTTPRedirect(project_url()) 

    @expose(template="beweb.templates.login")
    def login(self, forward_url=None, previous_url=None, *args, **kw):

        if not identity.current.anonymous and identity.was_login_attempted():
            raise redirect(forward_url)

        forward_url=None
        previous_url= cherrypy.request.path

        if identity.was_login_attempted():
            msg=_("The credentials you supplied were not correct or "\
                   "did not grant access to this resource.")
        elif identity.get_identity_errors():
            msg=_("You must provide your credentials before accessing "\
                   "this resource.")
        else:
            msg=_("Please log in.")
            forward_url= cherrypy.request.headers.get("Referer", "/")
        cherrypy.response.status=403
        return dict(message=msg, previous_url=previous_url, logging_in=True,
                    original_parameters=cherrypy.request.params,
                    forward_url=forward_url)

    @expose()
    def logout(self):
        identity.current.logout()
        raise redirect("/")

    @turbogears.expose('beweb.templates.about')
    def about(self, *paths, **kwargs):
        return {}

    @turbogears.expose()
    def default(self, *args, **kwargs):
        return self.prest.default(*args, **kwargs)

    def _cp_on_error(self):
        import traceback, StringIO
        bodyFile = StringIO.StringIO()
        traceback.print_exc(file = bodyFile)
        trace_text = bodyFile.getvalue()
        try:
            raise
        except cherrypy.NotFound:
            self.handle_error('Not Found', str(e), trace_text, '404 Not Found')

        except NoRootEntry, e:
            self.handle_error('Project Misconfiguration', str(e), trace_text)

        except Exception, e:
            self.handle_error('Internal server error', str(e), trace_text)

    def handle_error(self, heading, body, traceback=None, 
                     status='500 Internal Server Error'):
        cherrypy.response.headerMap['Status'] = status 
        cherrypy.response.body = [self.errorpage(heading, body, traceback)]
        

    @turbogears.expose(html='beweb.templates.error')
    def errorpage(self, heading, body, traceback):
        return {'heading': heading, 'body': body, 'traceback': traceback}
