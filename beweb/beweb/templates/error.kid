<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:py="http://purl.org/kid/ns#"
    py:extends="'master.kid'">
<head>
    <meta content="text/html; charset=UTF-8" http-equiv="content-type" py:replace="''"/>
    <title>BE Error: ${heading}</title>
</head>

<body>
<h1 py:content="heading">Error heading</h1>
<div py:replace="body" >Error Body</div>
<pre py:content="traceback" class="traceback">Traceback</pre>
</body>
</html>
