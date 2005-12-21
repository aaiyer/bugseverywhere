from unittest import TestCase
import unittest
"""A pseudo-REST dispatching method in which only the noun comes from the path.
The action performed will depend on kwargs.
"""

class AmbiguousAction(Exception):
    def __init__(self, actions):
        Exception.__init__(self, "Supplied action is ambiguous.")
        self.actions = actions
    

def provide_action(name, value):
    def provider(func):
        func._action_desc = (name, value)
        return func
    return provider

class PrestHandler(object):
    def __init__(self):
        object.__init__(self)
        self.actions = {}
        for member in (getattr(self, m) for m in dir(self)):
            if not hasattr(member, '_action_desc'):
                continue
            name, value = member._action_desc
            if name not in self.actions:
                self.actions[name] = {}
            self.actions[name][value] = member

    @classmethod
    def add_action(klass, name, value, function):
        if name not in klass.actions:
            klass.actions[name] = {}
        klass.actions[name][value] = function


    def decode(self, path, data=None):
        """Convert the path into a handler, a resource, data, and extra_path"""
        if data is None:
            data = {}
        if len(path) < 2 or not (hasattr(self, path[1])):
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
        action = child.get_action(**kwargs)
        new_args = ([data, resource]+extra)
        if action is not None:
            return action(*new_args, **kwargs)
        else:
            print child.__class__.__name__
            return child.dispatch(*new_args, **kwargs)

    def get_action(self, **kwargs):
        """Return the action requested by kwargs, if any.
        
        Raises AmbiguousAction if more than one action matches.
        """
        actions = []
        for key in kwargs:
            if key in self.actions:
                if kwargs[key] in self.actions[key]:
                    actions.append(self.actions[key][kwargs[key]])
        if len(actions) == 0:
            return None
        elif len(actions) == 1:
            return actions[0]
        else:
            raise AmbiguousAction(actions)


class PrestTester(TestCase):
    def test_decode(self):
        class ProjectHandler(PrestHandler):
            actions = {}
            def dispatch(self, project_data, project, *args, **kwargs):
                self.project_id = project_data['project']
                self.project_data = project_data
                self.resource = project
                self.args = args
                self.kwargs = kwargs

            def instantiate(self, project):
                return [project]

            @provide_action('action', 'Save')
            def save(self, project_data, project, *args, **kwargs):
                self.action = "save"

            @provide_action('behavior', 'Update')
            def update(self, project_data, project, *args, **kwargs):
                self.action = "update"
            
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
        foo.default(*['project', '27', 'extra'], **{'action':'Save', 'b':'97'})
        self.assertEqual(foo.project.action, 'save')
        foo.default(*['project', '27', 'extra'], 
                    **{'behavior':'Update', 'b':'97'})
        self.assertEqual(foo.project.action, 'update')
        self.assertRaises(AmbiguousAction, foo.default, 
                          *['project', '27', 'extra'], 
                          **{'behavior':'Update', 'action':'Save', 'b':'97'})
                
        class BugHandler(PrestHandler):
            actions = {}
            def dispatch(self, bug_data, bug, *args, **kwargs):
                self.project_id = project_data['project']
                self.project_data = project_data
                self.resource = project
                self.args = args
                self.kwargs = kwargs

            def instantiate(self, project, bug):
                return [project, bug]

            @provide_action('action', 'Save')
            def save(self, project_data, project, *args, **kwargs):
                self.action = "save"

            @provide_action('behavior', 'Update')
            def update(self, project_data, project, *args, **kwargs):
                self.action = "update"

        foo.project.bug = BugHandler()
        handler, resource, data, extra = foo.decode([None, 'project', '83', 
                                                     'bug', '92'])
        assert handler is foo.project.bug
        self.assertEqual(resource[0], '83')
        self.assertEqual(resource[1], '92')
        self.assertEqual([], extra)
        self.assertEqual(data['project'], '83')
        self.assertEqual(data['bug'], '92')

def test():
    patchesTestSuite = unittest.makeSuite(PrestTester,'test')
    runner = unittest.TextTestRunner(verbosity=0)
    return runner.run(patchesTestSuite)
    

if __name__ == "__main__":
    test()
