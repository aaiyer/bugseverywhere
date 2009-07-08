
__desc__ = __doc__

css_file = """
body {
font-family: "lucida grande", "sans serif";
color: #333;
width: 60em;
margin: auto;
}


div.main {
padding: 20px;
margin: auto;
padding-top: 0;
margin-top: 1em;
background-color: #fcfcfc;
}


.person {
font-family: courier;
}

a, a:visited {
background: inherit;
text-decoration: none;
}

a {
color: #003d41;
}

a:visited {
color: #553d41;
}

ul {
list-style-type: none;
padding: 0;
}

p {
width: 40em;
}

.inline-status-image {
position: relative;
top: 0.2em;
}

.dimmed {
color: #bbb;
}

table {
border-style: none;
border-spacing: 0;
}

table.log {
}


td {
border-width: 0;
border-style: none;
padding-right: 0.5em;
padding-left: 0.5em;
}

tr {
vertical-align: top;
}

h1 {
padding: 0.5em;
background-color: #305275;
margin-top: 0;
margin-bottom: 0;
color: #fff;
margin-left: -20px;
margin-right: -20px;  
}

h2 {
text-transform: uppercase;
font-size: smaller;
margin-top: 1em;
margin-left: -0.5em;  
/*background: #fffbce;*/
/*background: #628a0d;*/
padding: 5px;
color: #305275;
}



.attrname {
text-align: right;
font-size: smaller;
}

.attrval {
color: #222;
}

.issue-closed-fixed {
background-image: "green-check.png";
}

.issue-closed-wontfix {
background-image: "red-check.png";
}

.issue-closed-reorg {
background-image: "blue-check.png";
}

.inline-issue-link {
text-decoration: underline;
}

img {
border: 0;
}


div.footer {
font-size: small;
padding-left: 20px;
padding-right: 20px;
padding-top: 5px;
padding-bottom: 5px;
margin: auto;
background: #305275;
color: #fffee7;
}

.footer a {
color: #508d91;
}


.header {
font-family: "lucida grande", "sans serif";
font-size: smaller;
background-color: #a9a9a9;
text-align: left;

padding-right: 0.5em;
padding-left: 0.5em;

}


.even-row {
background-color: #e9e9e2;
}

.odd-row {
background-color: #f9f9f9;
}

.backptr {
font-size: smaller;
width: 100%;
text-align: left;
padding-bottom: 1em;
margin-top: 0;
}

.logcomment {
padding-left: 4em;
font-size: smaller;
}

.id {
font-family: courier;
}

.description {
background: #f2f2f2;
padding-left: 1em;
padding-right: 1em;
padding-top: 0.5em;
padding-bottom: 0.5em;
}

.message {
}

.littledate {
font-size: smaller;
}

.progress-meter-done {
background-color: #03af00;
}

.progress-meter-undone {
background-color: #ddd;
}

.progress-meter {
}
"""

html_index = """
<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="en" lang="en">
<head>
<title>BugsEverywhere Issue Tracker</title>
<meta http-equiv="Content-Type" content="text/html; charset=utf-8" />
<link rel="stylesheet" href="style.css" type="text/css" />
</head>
<body>


<div class="main">
<h1>BugsEverywhere Issue Tracker</h1>
<table>
<tbody>
<tr>
<td>
  <h2>Issues list by status</h2>
  <table>
    <tbody>
        <tr class="even-row">
            <td>
                <a href="unconfirmed.html">unconfirmed</a>
            </td>
            <td align="right">
                _unconfirmed_ 
            </td>
            <td>
                issues
            </td>
        </tr>
        <tr class="odd-row">
            <td>
                <a href="open.html">open</a>
            </td>
            <td align="right">
                _open_ 
            </td>
            <td>
                 issues
            </td>
        </tr>
        <tr class="even-row">
            <td>
                <a href="assigned.html">assigned</a>
            </td>
            <td align="right">
                _assigned_
            </td>
            <td>
                issues
            </td>
        </tr>
        <tr class="odd-row">
            <td>
                <a href="test.html">test</a>
            </td>
            <td align="right">
                _test_
            </td>
            <td>
                issues
            </td>
        </tr>
        <tr class="even-row">
            <td>
                <a href="closed.html">closed</a>
            </td>
            <td align="right">
                _closed_
            </td>
            <td>
                issues
            </td>
        </tr>
        <tr class="odd-row">
            <td>
                <a href="fixed.html">fixed</a>
            </td>
            <td align="right">
                _fixed_
            </td>
            <td>
                 issues
            </td>
        </tr>
        <tr class="even-row">
            <td>
                <a href="wontfix.html">wontfix</a>
            </td>
            <td align="right">
                _wontfix_
            </td>
            <td>
                 issues
            </td>
        </tr>
        <tr class="odd-row">
            <td>
                <a href="disabled.html">disabled</a>
            </td>
            <td align="right">
                _disabled_
            </td>
            <td>
                 issues
            </td>
        </tr>    
    </tbody>
  </table>
</td>

<td>

  <h2>Issues list by severity</h2>
  <table>
    <tbody>
        <tr class="even-row">
            <td>
                <a href="serious.html">serious</a>
            </td>
            <td align="right">
                _serious_ 
            </td>
            <td>
                issues
            </td>
        </tr>
        <tr class="odd-row">
            <td>
                <a href="critical.html">critical</a>
            </td>
            <td align="right">
                _critical_ 
            </td>
            <td>
                 issues
            </td>
        </tr>
        <tr class="even-row">
            <td>
                <a href="fatal.html">fatal</a>
            </td>
            <td align="right">
                _fatal_
            </td>
            <td>
                issues
            </td>
        </tr>
        <tr class="odd-row">
            <td>
                <a href="wishlist.html">wishlist</a>
            </td>
            <td align="right">
                _wishlist_
            </td>
            <td>
                issues
            </td>
        </tr>
        <tr class="even-row">
            <td>
                <a href="minor.html">minor</a>
            </td>
            <td align="right">
                _minor_
            </td>
            <td>
                issues
            </td>
        </tr>
    </tbody>
  </table>
</td>
<td>

  <h2>Last 10 Open bugs</h2>
  <table>
    <tbody>

_LAST_ACTVITY_

    </tbody>
  </table>
</td>

</tr>
</tbody>
</table>

</div>

<div class="footer">Generated by <a href="http://www.bugseverywhere.org/">BugsEverywhere</a>.</div>


</body>
</html>
"""

last_activity = """
        <tr class="_ROW_">
            <td><a href="_BUG_ID_.html">_BUG_ on _DATE_</a></td>
        </tr>
"""
