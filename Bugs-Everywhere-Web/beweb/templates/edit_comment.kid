<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
<?python
from libbe.utility import time_to_str 
from beweb.controllers import bug_list_url, bug_url
?>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:py="http://purl.org/kid/ns#"
    py:extends="'master.kid'">

<head>
    <meta content="text/html; charset=UTF-8" http-equiv="content-type" py:replace="''"/>
    <title>Edit comment</title>
</head>

<body>
<h1>Edit comment</h1>
<form method="post">
<table>
    <tr><td>From</td><td>${comment.From}</td></tr>
    <tr><td>Date</td><td>${time_to_str(comment.time)}</td></tr>
</table>
<insetbox><textarea rows="15" cols="80" py:content="comment.body" name="comment_body" style="border-style: none"/></insetbox>
<p><input type="submit" name="action" value="Update"/></p>
</form>
<a href="${bug_url(project_id, comment.bug.uuid)}">Up to Bug</a>
</body>
</html>
