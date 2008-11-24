<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
<?python
from libbe.bug import severity_values, status_values, thread_comments
from libbe.utility import time_to_str 
from beweb.controllers import bug_list_url, comment_url
from beweb.formatting import comment_body_xhtml, select_among
from beweb.model import people_map
people = people_map()
?>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:py="http://purl.org/kid/ns#"
    py:extends="'master.kid'">

<head>
    <meta content="text/html; charset=UTF-8" http-equiv="content-type" py:replace="''"/>
    <title>Edit bug</title>
</head>

<body>
<h1>Edit bug</h1>
<form method="post" action=".">
<table>
<tr><td>Status</td><td>Severity</td><td>Assigned To</td><td>Summary</td></tr>
<tr><td>${select_among("status", status_values, bug.status)}</td><td>${select_among("severity", severity_values, bug.severity)}</td>
<td>${select_among("assigned", people.keys()+[None], bug.assigned, people)}</td><td><input name="summary" value="${bug.summary}" size="80" /></td></tr>
</table>
<div py:def="show_comment(comment, children)" class="comment">
    <insetbox>
    <table>
        <tr><td>From</td><td>${comment.From}</td></tr>
        <tr><td>Date</td><td>${time_to_str(comment.time)}</td></tr>
    </table>
    <div py:content="comment_body_xhtml(comment)" py:strip="True"></div>
    <a href="${comment_url(project_id, bug.uuid, comment.uuid)}">Edit</a>
    <a href="${comment_url(project_id, bug.uuid, comment.uuid, 
                           action='Reply')}">Reply</a>
    </insetbox>
    <div style="margin-left:20px;">
    <div py:for="child, grandchildren in children" py:strip="True">
    ${show_comment(child, grandchildren)}
    </div>
    </div>
</div>
<div py:for="comment, children in thread_comments(bug.list_comments())" 
     py:strip="True">
    ${show_comment(comment, children)}
</div>
<p><input type="submit" name="action" value="Update"/></p>
<p><input type="submit" name="action" value="New comment"/></p>
</form>
<a href="${bug_list_url(project_id)}">Bug List</a>
</body>
</html>
