from unittest import TestCase
import unittest
"""A pseudo-REST dispatching method in which only the noun comes from the path.
The action performed will depend on kwargs.
"""
class PrestHandler(object):
    def __init__(self):
        object.__init__(self)

    def decode(self, path, data=None):
        """Convert the path into a handler, a resource, data, and extra_path"""
        if data is None:
            data = {}
        if len(path) < 2 or not (path[0] is None or hasattr(self, path[0])):
            if len(path) == 0:
                resource = None
            else:
                resource = self.instantiate(**data)
            return self, resource, data, path[1:] 
        if len(path) > 2:
            data[path[1]] = path[2]
        return getattr(self, path[1]).decode(path[2:], data)

    def default(self, *args, **kwargs):
        child, resource, data, extra = self.decode([None,] + list(args))
        child.dispatch(*([data, resource]+extra), **kwargs)


class PrestTester(TestCase):
    def test_decode(self):
        class ProjectHandler(PrestHandler):
            def dispatch(self, project_data, project, *args, **kwargs):
                self.project_id = project_data['project']
                self.project_data = project_data
                self.resource = project
                self.args = args
                self.kwargs = kwargs

            def instantiate(self, project):
                return [project]

        foo = PrestHandler()
        foo.project = ProjectHandler()
        handler, resource, data, extra = foo.decode([None, 'project', '83', 
                                                     'bloop', 'yeah'])
        assert handler is foo.project
        self.assertEqual({'project': '83'}, data)
        self.assertEqual(['bloop', 'yeah'], extra)
        foo.default(*['project', '27', 'extra'], **{'a':'b', 'b':'97'})
        self.assertEqual(foo.project.args, ('extra',))
        self.assertEqual(foo.project.kwargs, {'a':'b', 'b':'97'})
        self.assertEqual(foo.project.project_data, {'project': '27'})
        self.assertEqual(foo.project.resource, ['27'])
                
def test():
    patchesTestSuite = unittest.makeSuite(PrestTester,'test')
    runner = unittest.TextTestRunner(verbosity=0)
    return runner.run(patchesTestSuite)
    

if __name__ == "__main__":
    test()
