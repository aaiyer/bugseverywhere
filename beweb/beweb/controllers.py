import turbogears
from turbogears import controllers
from libbe.bugdir import tree_root, cmp_severity
projects = {"be": ("Bugs Everywhere","/home/abentley/be"),
            "devel": ("PF devel","/home/abentley/devel"),
}

def project_tree(project):
    try:
        return tree_root(projects[project][1])
    except KeyError:
        raise Exception("Unknown project %s" % project)

class Root(controllers.Root):
    @turbogears.expose(html="beweb.templates.projects")
    def index(self):
        return {"projects" : projects}

    @turbogears.expose()
    def default(self, *args, **kwargs):
        if len(args) == 1:
            return self.bugs(args[0], **kwargs)
        elif len(args) == 2:
            return self.bug(*args, **kwargs)
        else:
            return repr(args)
            

    @turbogears.expose(html="beweb.templates.bugs")
    def bugs(self, project_id, sort_by=None):
        bug_tree = project_tree(project_id)
        bugs = list(bug_tree.list())
        if sort_by is None:
            def cmp_date(bug1, bug2):
                return -cmp(bug1.time, bug2.time)
            bugs.sort(cmp_date)
            bugs.sort(cmp_severity)
        return {"project_id"      : project_id,
                "project_name"    : projects[project_id][0],
                "bugs"            : bugs,
               }

    @turbogears.expose(html="beweb.templates.edit_bug")
    def bug(self, project_id, bug_uuid, action=None, status=None, 
            severity=None, summary=None):
        bug_tree = project_tree(project_id)
        bug = bug_tree.get_bug(bug_uuid)
        if action == "Update":
            bug.status = status
            bug.severity = severity
            bug.summary = summary
            bug.save()
        return {"bug": bug, "project_id": project_id}
