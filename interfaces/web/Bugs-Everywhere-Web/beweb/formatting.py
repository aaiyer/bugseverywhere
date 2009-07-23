from StringIO import StringIO

try :
   from xml.etree.ElementTree import XML # Python 2.5 (and greater?)
except ImportError :
   from elementtree.ElementTree import XML
from libbe.restconvert import rest_xml

def to_unix(text):
   skip_newline = False
   for ch in text:
      if ch not in ('\r', '\n'):
         yield ch
      else:
         if ch == '\n':
            if skip_newline:
               continue
         else:
            skip_newline = True
         yield '\n'


def soft_text(text):
   first_space = False
   translations = {'\n': '<br />\n', '&': '&amp;', '\x3c': '&lt;', 
                   '\x3e': '&gt;'}
   for ch in to_unix(text):
      if ch == ' ' and first_space is True:
            yield '&#160;'
      first_space = ch in (' ')
      try:
         yield translations[ch]
      except KeyError:
         yield ch


def soft_pre(text):
   return XML('<div style="font-family: monospace">'+
              ''.join(soft_text(text)).encode('utf-8')+'</div>') 


def get_rest_body(rest):
    xml, warnings = rest_xml(StringIO(rest))
    return xml.find('{http://www.w3.org/1999/xhtml}body'), warnings
 

def comment_body_xhtml(comment):
    if comment.content_type == "text/restructured":
        return get_rest_body(comment.body)[0]
    else:
        return soft_pre(comment.body)


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
