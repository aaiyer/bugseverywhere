"""Add a comment to a bug"""
from libbe import bugdir, cmdutil, names, utility
import os
def execute(args):
    """
    >>> from libbe import tests, names
    >>> import os, time
    >>> dir = tests.simple_bug_dir()
    >>> os.chdir(dir.dir)
    >>> execute(["a", "This is a comment about a"])
    >>> comment = dir.get_bug("a").list_comments()[0]
    >>> comment.body
    'This is a comment about a\\n'
    >>> comment.From == names.creator()
    True
    >>> comment.date <= int(time.time())
    True
    >>> comment.in_reply_to is None
    True
    >>> os.environ["EDITOR"] = "echo 'I like cheese' > "
    >>> execute(["b"])
    >>> dir.get_bug("b").list_comments()[0].body
    'I like cheese\\n'
    >>> tests.clean_up()
    """
    options, args = get_parser().parse_args(args)
    if len(args) < 1:
        raise cmdutil.UsageError()
    bug = cmdutil.get_bug(args[0])
    if len(args) == 1:
        body = utility.editor_string()
        if body is None:
            raise cmdutil.UserError("No comment entered.")
    else:
        body = args[1]
        if not body.endswith('\n'):
            body+='\n'

    comment = bugdir.new_comment(bug, body)
    comment.save()


def get_parser():
    parser = cmdutil.CmdOptionParser("be comment BUG-ID COMMENT")
    return parser

longhelp="""
Add a comment to a bug.
"""

def help():
    return get_parser().help_str() + longhelp
