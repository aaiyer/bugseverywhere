class FileString(object):
    """Bare-bones pseudo-file class
    
    >>> f = FileString("me\\nyou")
    >>> len(list(f))
    2
    >>> len(list(f))
    0
    >>> f = FileString()
    >>> f.write("hello\\nthere")
    >>> "".join(list(f))
    'hello\\nthere'
    """
    def __init__(self, str=""):
        object.__init__(self)
        self.str = str
        self._iter = None

    def __iter__(self):
        if self._iter is None:
            self._iter = self._get_iter()
        return self._iter

    def _get_iter(self):
        for line in self.str.splitlines(True):
            yield line

    def write(self, line):
        self.str += line


def get_file(f):
    """
    Return a file-like object from input.  This is a helper for functions that
    can take either file or string parameters.

    :param f: file or string
    :return: a FileString if input is a string, otherwise return the imput 
    object.

    >>> isinstance(get_file(file("/dev/null")), file)
    True
    >>> isinstance(get_file("f"), FileString)
    True
    """
    if isinstance(f, basestring):
        return FileString(f)
    else:
        return f


