<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
<?python import sitetemplate ?>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:py="http://purl.org/kid/ns#" py:extends="sitetemplate">

<head py:match="item.tag=='{http://www.w3.org/1999/xhtml}head'">
    <meta content="text/html; charset=UTF-8" http-equiv="content-type" py:replace="''"/>
    <title py:if="False">Your title goes here</title>
    <link rel="stylesheet" type="text/css" href="/static/css/style.css"/>
    <div py:replace="item[:]"/>
</head>

<body py:match="item.tag=='{http://www.w3.org/1999/xhtml}body'">
<div>b u g s   e v e r y w h e r e</div> 
    <div py:if="tg_flash" class="flash" py:content="tg_flash"></div>
    
    <div py:replace="item[:]"/>
</body>
</html>
