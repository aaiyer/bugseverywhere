class FileString(object):
    """Bare-bones pseudo-file class"""
    def __init__(self, str=""):
        object.__init__(self)
        self.str = str

    def __iter__(self):
        for line in self.str.splitlines(True):
            yield line

    def write(self, line):
        self.str += line


def parse(f):
    """Parses a mapfile, returns a Dictionary

    >>> f = FileString("1:q\\n2:q\\n3:q\\n>p\\n4:q\\n5:q\\n6:q\\n")
    >>> parse(f)["q"]
    'p'
    >>> parse("1:q\\n2:q\\n3:q\\n>r\\n4:q\\n5:q\\n6:q\\n")["q"]
    'r'
    >>> parse("1:q:5\\n>s\\n2:q:5\\n")["q:5"]
    's'
    >>> parse("1:q\\n>s\\n2:q\\n1:q\\n>s\\n2:q\\n")
    Traceback (most recent call last):
      File "<stdin>", line 1, in ?
      File "libbe/mapfile.py", line 41, in parse
        assert (lnum == prev_num + 1)
    AssertionError
    >>> parse("1:q\\n>s\\n2:q\\n1:l\\n>s\\n2:l\\n1:q\\n>s\\n2:q\\n")
    Traceback (most recent call last):
    AssertionError
    >>> parse("1:q\\n>s\\n>s\\n2:q\\n")
    Traceback (most recent call last):
    AssertionError
    """
    if isinstance(f, basestring):
        f = FileString(f)
    result = {}
    name = None
    prev_num = None
    for line in f:
        value = None
        # Handle values
        if line.startswith(">"):
            assert (name is not None)
            assert (not result.has_key(name))
            result[name] = line[1:].rstrip("\n")
        # Handle names
        else:
            lname = ":".join(line.split(":")[1:]).rstrip("\n")
            lnum = int(line.split(":")[0])

            #special-case the first execution
            if name is None:
                name = lname 

            #ensure sequential operation
            elif lname == name:
                assert (lnum == prev_num + 1)
            #if name changes, start over at 1
            else:
                if lnum != 1:
                    assert(lname != name)
                    raise "%i %s %s" % (lnum, lname, name)
                assert (lnum == 1)
                name = lname
            prev_num = lnum
    return result
 

def generate(f, map, context=3):
    """
    >>> f = FileString()
    >>> generate(f, {"q":"p"})
    >>> f.str
    '1:q\\n2:q\\n3:q\\n>p\\n4:q\\n5:q\\n6:q\\n'
    >>> parse(f)["q"]
    'p'
    >>> f = FileString()
    >>> generate(f, {"a":"b", "c":"d", "e":"f"})
    >>> dict = parse(f)
    >>> dict["a"]
    'b'
    >>> dict["c"]
    'd'
    >>> dict["e"]
    'f'
    """
    assert(context > 0)
    keys = map.keys()
    keys.sort()
    for key in keys:
        for i in range(context):
            f.write("%i:%s\n" % (i+1, key))
        f.write(">%s\n" % map[key])
        for i in range(context):
            f.write("%i:%s\n" % (i+context+1, key))
