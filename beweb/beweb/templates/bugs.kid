<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
<?python
from libbe.cmdutil import unique_name
def row_class(bug):
    if bug.status == "closed":
        return "closed"
    else:
        return ""
?>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:py="http://purl.org/kid/ns#"
    py:extends="'master.kid'">

<head>
    <meta content="text/html; charset=UTF-8" http-equiv="content-type" py:replace="''"/>
    <title>Bugs for $project_name</title>
</head>

<body>
<h1>Bug list for ${project_name}</h1>
<table>
<tr><td>ID</td><td>Status</td><td>Severity</td><td>Assigned To</td><td>Summary</td></tr>
<div py:for="bug in bugs" py:strip="True"><tr class="${row_class(bug)}" py:if="bug.status != 'closed' or show_closed"><td><a href="${'/%s/%s/' % (project_id, bug.uuid)}">${unique_name(bug, bugs[:])}</a></td><td>${bug.status}</td><td>${bug.severity}</td><td>${bug.assigned}</td><td>${bug.summary}</td></tr>
</div>
</table>
<a href="/">Project list</a>
<a href="${'/%s/?show_closed=%s' % (project_id, str(not show_closed))}">Toggle closed</a>
<form action="/$project_id/new/" method="post">
<input type="submit" name="action" value="New bug"/>
</form>
</body>
</html>
