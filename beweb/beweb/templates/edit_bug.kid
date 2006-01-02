<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
<?python
from libbe.bugdir import severity_levels
from libbe.utility import time_to_str 
from beweb.controllers import bug_list_url, comment_url
from beweb.config import people
def select_among(name, options, default, display_names=None):
    output = ['<select name="%s">' % name]
    for option in options:
        if option == default:
            selected = ' selected="selected"'
        else:
            selected = ""
        if display_names is None:
            display_name = None
        else:
            display_name = display_names.get(option)

        if option is None:
            option = ""
        if display_name is None:
            display_name = option
            value = ""
        else:
            value = ' value="%s"' % option
        output.append("<option%s%s>%s</option>" % (selected, value, 
                                                   display_name))
    output.append("</select>")
    return XML("".join(output))
?>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:py="http://purl.org/kid/ns#"
    py:extends="'master.kid'">

<head>
    <meta content="text/html; charset=UTF-8" http-equiv="content-type" py:replace="''"/>
    <title>Edit bug</title>
</head>

<body>
<h1>Edit bug</h1>
<form method="post">
<table>
<tr><td>Status</td><td>Severity</td><td>Assigned To</td><td>Summary</td></tr>
<tr><td>${select_among("status", ["open", "closed", "in-progress"], bug.status)}</td><td>${select_among("severity", severity_levels, bug.severity)}</td>
<td>${select_among("assigned", people.keys()+[None], bug.assigned, people)}</td><td><input name="summary" value="${bug.summary}" size="80" /></td></tr>
</table>
<div py:for="comment in bug.list_comments()" class="comment">
    <insetbox>
    <table>
        <tr><td>From</td><td>${comment.From}</td></tr>
        <tr><td>Date</td><td>${time_to_str(comment.date)}</td></tr>
    </table>
    <pre>${comment.body}</pre>
    <a href="${comment_url(project_id, bug.uuid, comment.uuid)}">Edit</a>
    </insetbox>
</div>
<p><input type="submit" name="action" value="Update"/></p>
<p><input type="submit" name="action" value="New comment"/></p>
</form>
<a href="${bug_list_url(project_id)}">Bug List</a>
</body>
</html>
