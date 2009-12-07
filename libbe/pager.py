# Copyright

"""
Automatic pager for terminal output (a la Git).
"""

import sys, os, select

# see http://nex-3.com/posts/73-git-style-automatic-paging-in-ruby
def run_pager(paginate=None):
    """
    paginate should be one of 'never', 'auto', or 'always'.

    usage: just call this function and continue using sys.stdout like
    you normally would.
    """
    if paginate == 'never' \
            or sys.platform == 'win32' \
            or not hasattr(sys.stdout, 'isatty') \
            or sys.stdout.isatty() == False:
        return

    if paginate == 'auto':
        if 'LESS' not in os.environ:
            os.environ['LESS'] = '' # += doesn't work on undefined var
        # don't page if the input is short enough
        os.environ['LESS'] += ' -FRX'
    if 'PAGER' in os.environ:
        pager = os.environ['PAGER']
    else:
        pager = 'less'

    read_fd, write_fd = os.pipe()
    if os.fork() == 0:
        # child process
        os.close(read_fd)
        os.close(0)
        os.dup2(write_fd, 1)
        os.close(write_fd)
        if hasattr(sys.stderr, 'isatty') and sys.stderr.isatty() == True:
            os.dup2(1, 2)
        return

    # parent process, become pager
    os.close(write_fd)
    os.dup2(read_fd, 0)
    os.close(read_fd)

    # Wait until we have input before we start the pager
    select.select([0], [], [])
    os.execlp(pager, pager)
