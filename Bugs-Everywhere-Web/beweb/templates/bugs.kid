<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
<?python
from libbe.cmdutil import unique_name
from beweb.controllers import bug_url, project_url, bug_list_url
from beweb.model import people_map
people = people_map()
def row_class(bug, num):
    if not bug.active is True:
        extra = "closed"
    else:
        extra = ""
    if num % 2 == 0:
        return extra+"even"
    else:
        return extra+"odd"


def match(bug, show_closed, search):
    if search is None:
        return True
    else:
        return search.lower() in bug.summary.lower()
?>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:py="http://purl.org/kid/ns#"
    py:extends="'master.kid'">

<head>
    <meta content="text/html; charset=UTF-8" http-equiv="content-type" py:replace="''"/>
    <title>Bugs for $project_name</title>
    <style type="text/css" py:if="not show_closed">
    tr.closedeven, tr.closedodd
    {
        display:None
    }
    </style>
</head>

<body>
<h1>Bug list for ${project_name}</h1>
<table>
<tr><td>ID</td><td>Status</td><td>Severity</td><td>Assigned To</td><td>Comments</td><td>Summary</td></tr>
<div py:for="num, bug in enumerate([b for b in bugs if match(b, show_closed, search)])" py:strip="True"><tr class="${row_class(bug, num)}"><td><a href="${bug_url(project_id, bug.uuid)}">${unique_name(bug, bugs[:])}</a></td><td>${bug.status}</td><td>${bug.severity}</td><td>${people.get(bug.assigned, bug.assigned)}</td><td>${len(list(bug.iter_comment_ids()))}</td><td>${bug.summary}</td></tr>
</div>
</table>
<a href="${project_url()}">Project list</a>
<a href="${bug_list_url(project_id, not show_closed, search)}">Toggle closed</a>
<form action="${bug_list_url(project_id)}" method="post">
<input type="submit" name="action" value="New bug"/>
</form>
<form action="${bug_list_url(project_id)}" method="get">
<input type="hidden" name="show_closed" value="False" />
<input name="search" value="$search"/>
<input type="submit" name="action" value="Search" />
</form>
</body>
</html>
