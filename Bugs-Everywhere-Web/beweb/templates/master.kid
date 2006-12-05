<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
<?python import sitetemplate ?>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:py="http://purl.org/kid/ns#" py:extends="sitetemplate">

<head py:match="item.tag=='{http://www.w3.org/1999/xhtml}head'" py:attrs="item.items()">
    <meta content="text/html; charset=UTF-8" http-equiv="content-type" py:replace="''"/>
    <title py:if="False">Your title goes here</title>
    <link rel="stylesheet" type="text/css" href="/static/css/style.css"/>
    <meta py:replace="item[:]"/>
    <style type="text/css">
        #pageLogin
        {
            font-size: 10px;
            font-family: verdana;
            text-align: right;
        }
    </style>
</head>

<body py:match="item.tag=='{http://www.w3.org/1999/xhtml}body'" py:attrs="item.items()">
<div id="header"><div style="float: left">b u g s   e v r y w h e r e</div><ul class="navoption"><li><a href="/about/">About</a></li></ul>&#160;</div> 
    <div py:if="tg.config('identity.on',False) and not 'logging_in' in locals()"
        id="pageLogin">
        <span py:if="tg.identity.anonymous">
            <a href="/login">Login</a>
        </span>
        <span py:if="not tg.identity.anonymous">
            Welcome ${tg.identity.user.display_name}.
            <a href="/logout">Logout</a>
        </span>
    </div>

    <div py:if="tg_flash" class="flash" py:content="tg_flash"></div>

    <div py:replace="[item.text]+item[:]"/>

<table py:match="item.tag=='{http://www.w3.org/1999/xhtml}insetbox'" cellspacing="0" cellpadding="0" border="0" class="insetbox">
<tr height="19"><td background="/static/images/is-tl.png" width="19"/>
    <td background="/static/images/is-t.png" />
    <td background="/static/images/is-tr.png" width="11"></td>
</tr>
<tr>
    <td background="/static/images/is-l.png"/>
    <td py:content="item[:]"> Hello, this is some random text</td>
    <td background="/static/images/is-r.png"/>
</tr>
<tr height="11">
    <td background="/static/images/is-bl.png"/>
    <td background="/static/images/is-b.png" />
    <td background="/static/images/is-br.png"/>
</tr>
</table>
<table py:match="item.tag=='{http://www.w3.org/1999/xhtml}dsbox'" cellspacing="0" cellpadding="0" border="0" class="dsbox">
<tr height="11"><td background="/static/images/ds-tl.png" width="11"/>
    <td background="/static/images/ds-t.png" />
    <td background="/static/images/ds-tr.png" width="19"></td>
</tr>
<tr>
    <td background="/static/images/ds-l.png"/>
    <td py:content="item[:]"> Hello, this is some random text</td>
    <td background="/static/images/ds2-r.png"/>
</tr>
<tr height="19">
    <td background="/static/images/ds-bl.png"/>
    <td background="/static/images/ds2-b.png" />
    <td background="/static/images/ds-br.png"/>
</tr>
</table>
</body>

</html>
