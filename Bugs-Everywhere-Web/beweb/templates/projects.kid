<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
<?python
from libbe.bug import severity_values
def select_among(name, options, default):
    output = ['<select name="%s">' % name]
    for option in options:
        if option == default:
            selected = ' selected="selected"'
        else:
            selected = ""
        output.append("<option%s>%s</option>" % (selected, option))
    output.append("</select>")
    return XML("".join(output))
?>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:py="http://purl.org/kid/ns#"
    py:extends="'master.kid'">
<?python
project_triples = [(pn, pid, pl) for pid,(pn, pl) in projects.iteritems()]
project_triples.sort()
?>
<head>
    <meta content="text/html; charset=UTF-8" http-equiv="content-type" py:replace="''"/>
    <title>Project List</title>
</head>

<body>
<h1>Project List</h1>
<table>
<tr py:for="project_name, project_id, project_loc in project_triples"><td><a href="/project/${project_id}/">${project_name}</a></td></tr>
</table>
</body>
</html>
