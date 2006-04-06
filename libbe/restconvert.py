import re
from StringIO import StringIO
from docutils import nodes
from docutils.statemachine import StringList
from docutils.core import publish_file
from docutils.parsers import rst
from docutils.parsers.rst import directives
from docutils.parsers.rst.states import Inliner, MarkupMismatch, unescape
from elementtree import ElementTree


def rest_xml(rest):
    warnings = StringIO()
    parser = rst.Parser(inliner=HelpLinkInliner())
    xmltext = publish_file(rest, writer_name="html", parser=parser,
                           settings_overrides={"warning_stream": warnings,
                                               "halt_level": 5})
    warnings.seek(0)
    return ElementTree.parse(StringIO(xmltext)).getroot(), warnings.read()

class HelpLinkInliner(Inliner):
    def __init__(self, roles=None):
        Inliner.__init__(self, roles)
        regex = re.compile('\[([^|]*)\|([^]]*)\]')
        self.implicit_dispatch.append((regex, self.help_reference))

    def parse(self, *args, **kwargs):
        self.more_messages = []
        nodes, messages = Inliner.parse(self, *args, **kwargs)
        return nodes, (messages + self.more_messages)
        
    def help_reference(self, match, lineno):
        from wizardhelp.controllers import iter_help_pages
        text,link = match.groups()
        rawtext = match.group(0)
        text, link, rawtext = [unescape(f, 1) for f in (text, link, rawtext)]
        if link not in list(iter_help_pages()):
            msg = self.reporter.warning('Broken link to "%s".' % link, 
                                        line=lineno)
            self.more_messages.append(msg)
        ref = "/help/%s/" % link
        unescaped = text
        node = nodes.reference(rawtext, text, refuri=ref)
        node.set_class("helplink")
        return [node]


def rst_directive(name=None, required_args=0, optional_args=0, 
                  final_arg_ws=False, options=None, content='forbidden'):
    """Decorator that simplifies creating ReST directives
    
    All arguments are optional.  Name is, by default, determined from the
    function name.

    The possible values for content are 'forbidden', 'allowed' (but not 
    required), and 'required' (a warning will be generated if not present).
    """
    content_rules = {'forbidden': (False, False), 'allowed': (True, False), 
                     'required': (True, True)}
    content_allowed, content_required = content_rules[content]

    def decorator_factory(func):
        my_name = name
        if my_name is None:
            my_name = func.__name__

        def decorator(name, arguments, options, content, lineno, 
                      content_offset, block_text, state, state_machine):
            warn = state_machine.reporter.warning
            if not content and content_required:
                warn = state_machine.reporter.warning
                warning = warn('%s is empty' % my_name,
                               nodes.literal_block(block_text, block_text),
                               line=lineno)
                return [warning]
            return func(name, arguments, options, content, lineno,
                        content_offset, block_text, state, state_machine)

        decorator.arguments = (required_args, optional_args, final_arg_ws)
        decorator.options = options
        decorator.content = content_allowed
        directives.register_directive(my_name, decorator)
        return decorator 
    return decorator_factory


@rst_directive(required_args=1, final_arg_ws=True, content='required')
def foldout(name, arguments, options, content, lineno, content_offset, 
            block_text, state, state_machine):
    """\
    Generate a foldout section.
    
    On the ReST side, this merely involves marking the items with suitable
    classes.  A Kid match rule will be used to insert the appropriate
    Javascript magic.
    """
    text = '\n'.join(content)
    foldout_title = nodes.paragraph([arguments[0]])
    foldout_title.set_class('foldout-title')
    state.nested_parse(StringList([arguments[0]]), 0, foldout_title)
    foldout_body = nodes.compound(text)
    foldout_body.set_class('foldout-body')
    state.nested_parse(content, content_offset, foldout_body)
    foldout = nodes.compound(text)
    foldout += foldout_title
    foldout += foldout_body
    foldout.set_class('foldout')
    return [foldout]
