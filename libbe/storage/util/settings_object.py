# Bugs Everywhere - a distributed bugtracker
# Copyright (C) 2008-2012 Chris Ball <cjb@laptop.org>
#                         Gianluca Montecchi <gian@grys.it>
#                         W. Trevor King <wking@drexel.edu>
#
# This file is part of Bugs Everywhere.
#
# Bugs Everywhere is free software: you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by the Free
# Software Foundation, either version 2 of the License, or (at your option) any
# later version.
#
# Bugs Everywhere is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or
# FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General Public License for
# more details.
#
# You should have received a copy of the GNU General Public License along with
# Bugs Everywhere.  If not, see <http://www.gnu.org/licenses/>.

"""Provides :class:`SavedSettingsObject` implementing settings-dict
based property storage.

See Also
--------
:mod:`libbe.storage.util.properties` : underlying property definitions
"""

import libbe
from properties import Property, doc_property, local_property, \
    defaulting_property, checked_property, fn_checked_property, \
    cached_property, primed_property, change_hook_property, \
    settings_property
if libbe.TESTING == True:
    import doctest
    import unittest

class _Token (object):
    """`Control' value class for properties.

    We want values that only mean something to the `settings_object`
    module.
    """
    pass

class UNPRIMED (_Token):
    "Property has not been primed (loaded)."
    pass

class EMPTY (_Token):
    """Property has been primed but has no user-set value, so use
    default/generator value.
    """
    pass


def prop_save_settings(self, old, new):
    """The default action undertaken when a property changes.
    """
    if self.storage != None and self.storage.is_writeable():
        self.save_settings()

def prop_load_settings(self):
    """The default action undertaken when an UNPRIMED property is
    accessed.

    Attempt to run `.load_settings()`, which calls
    `._setup_saved_settings()` internally.  If `.storage` is
    inaccessible, don't do anything.
    """
    if self.storage != None and self.storage.is_readable():
        self.load_settings()

# Some name-mangling routines for pretty printing setting names
def setting_name_to_attr_name(self, name):
    """Convert keys to the `.settings` dict into their associated
    SavedSettingsObject attribute names.

    Examples
    --------

    >>> print setting_name_to_attr_name(None,"User-id")
    user_id

    See Also
    --------
    attr_name_to_setting_name : inverse
    """
    return name.lower().replace('-', '_')

def attr_name_to_setting_name(self, name):
    """Convert SavedSettingsObject attribute names to `.settings` dict
    keys.

    Examples:

    >>> print attr_name_to_setting_name(None, "user_id")
    User-id

    See Also
    --------
    setting_name_to_attr_name : inverse
    """
    return name.capitalize().replace('_', '-')


def versioned_property(name, doc,
                       default=None, generator=None,
                       change_hook=prop_save_settings,
                       mutable=False,
                       primer=prop_load_settings,
                       allowed=None, check_fn=None,
                       settings_properties=[],
                       required_saved_properties=[],
                       require_save=False):
    """Combine the common decorators in a single function.

    Use zero or one (but not both) of default or generator, since a
    working default will keep the generator from functioning.  Use the
    default if you know what you want the default value to be at
    'coding time'.  Use the generator if you can write a function to
    determine a valid default at run time.  If both default and
    generator are None, then the property will be a defaulting
    property which defaults to None.

    allowed and check_fn have a similar relationship, although you can
    use both of these if you want.  allowed compares the proposed
    value against a list determined at 'coding time' and check_fn
    allows more flexible comparisons to take place at run time.

    Set require_save to True if you want to save the default/generated
    value for a property, to protect against future changes.  E.g., we
    currently expect all comments to be 'text/plain' but in the future
    we may want to default to 'text/html'.  If we don't want the old
    comments to be interpreted as 'text/html', we would require that
    the content type be saved.

    change_hook, primer, settings_properties, and
    required_saved_properties are only options to get their defaults
    into our local scope.  Don't mess with them.

    Set mutable=True if:

    * default is a mutable
    * your generator function may return mutables
    * you set change_hook and might have mutable property values

    See the docstrings in `libbe.properties` for details on how each of
    these cases are handled.

    The value stored in `.settings[name]` will be

    * no value (or UNPRIMED) if the property has been neither set,
      nor loaded as blank.
    * EMPTY if the value has been loaded as blank.
    * some value if the property has been either loaded or set.
    """
    settings_properties.append(name)
    if require_save == True:
        required_saved_properties.append(name)
    def decorator(funcs):
        fulldoc = doc
        if default != None or generator == None:
            defaulting  = defaulting_property(default=default, null=EMPTY,
                                              mutable_default=mutable)
            fulldoc += "\n\nThis property defaults to %s." % default
        if generator != None:
            cached = cached_property(generator=generator, initVal=EMPTY,
                                     mutable=mutable)
            fulldoc += "\n\nThis property is generated with %s." % generator
        if check_fn != None:
            fn_checked = fn_checked_property(value_allowed_fn=check_fn)
            fulldoc += "\n\nThis property is checked with %s." % check_fn
        if allowed != None:
            checked = checked_property(allowed=allowed)
            fulldoc += "\n\nThe allowed values for this property are: %s." \
                       % (', '.join(allowed))
        hooked      = change_hook_property(hook=change_hook, mutable=mutable,
                                           default=EMPTY)
        primed      = primed_property(primer=primer, initVal=UNPRIMED,
                                      unprimeableVal=EMPTY)
        settings    = settings_property(name=name, null=UNPRIMED)
        docp        = doc_property(doc=fulldoc)
        deco = hooked(primed(settings(docp(funcs))))
        if default != None or generator == None:
            deco = defaulting(deco)
        if generator != None:
            deco = cached(deco)
        if check_fn != None:
            deco = fn_checked(deco)
        if allowed != None:
            deco = checked(deco)
        return Property(deco)
    return decorator

class SavedSettingsObject(object):
    """Setup a framework for lazy saving and loading of `.settings`
    properties.

    This is useful for BE objects with saved properties
    (e.g. :class:`~libbe.bugdir.BugDir`, :class:`~libbe.bug.Bug`,
    :class:`~libbe.comment.Comment`).  For example usage, consider the
    unittests at the end of the module.

    See Also
    --------
    versioned_property, prop_save_settings, prop_load_settings
    setting_name_to_attr_name, attr_name_to_setting_name
    """
    # Keep a list of properties that may be stored in the .settings dict.
    #settings_properties = []

    # A list of properties that we save to disk, even if they were
    # never set (in which case we save the default value).  This
    # protects against future changes in default values.
    #required_saved_properties = []

    _setting_name_to_attr_name = setting_name_to_attr_name
    _attr_name_to_setting_name = attr_name_to_setting_name

    def __init__(self):
        self.storage = None
        self.settings = {}

    def load_settings(self):
        """Load the settings from disk."""
        # Override.  Must call ._setup_saved_settings({}) with
        # from-storage settings.
        self._setup_saved_settings({})

    def _setup_saved_settings(self, settings=None):
        """
        Sets up a settings dict loaded from storage.  Fills in
        all missing settings entries with EMPTY.
        """
        if settings == None:
            settings = {}
        for property in self.settings_properties:
            if property not in self.settings \
                    or self.settings[property] == UNPRIMED:
                if property in settings:
                    self.settings[property] = settings[property]
                else:
                    self.settings[property] = EMPTY

    def save_settings(self):
        """Save the settings to disk."""
        # Override.  Should save the dict output of ._get_saved_settings()
        settings = self._get_saved_settings()
        pass # write settings to disk....

    def _get_saved_settings(self):
        """
        In order to avoid overwriting unread on-disk data, make sure
        we've loaded anything sitting on the disk.  In the current
        implementation, all the settings are stored in a single file,
        so we need to load _all_ the saved settings.  Another approach
        would be per-setting saves, in which case you could skip this
        step, since any setting changes would have forced that setting
        load already.
        """
        settings = {}
        for k in self.settings_properties: # force full load
            if not k in self.settings or self.settings[k] == UNPRIMED:
                value = getattr(
                    self, self._setting_name_to_attr_name(k))
        for k in self.settings_properties:
            if k in self.settings and self.settings[k] != EMPTY:
                settings[k] = self.settings[k]
            elif k in self.required_saved_properties:
                settings[k] = getattr(
                    self, self._setting_name_to_attr_name(k))
        return settings

    def clear_cached_setting(self, setting=None):
        "If setting=None, clear *all* cached settings"
        if setting != None:
            if hasattr(self, "_%s_cached_value" % setting):
                delattr(self, "_%s_cached_value" % setting)
        else:
            for setting in settings_properties:
                self.clear_cached_setting(setting)


if libbe.TESTING == True:
    import copy

    class TestStorage (list):
        def __init__(self):
            list.__init__(self)
            self.readable = True
            self.writeable = True
        def is_readable(self):
            return self.readable
        def is_writeable(self):
            return self.writeable
        
    class TestObject (SavedSettingsObject):
        def load_settings(self):
            self.load_count += 1
            if len(self.storage) == 0:
                settings = {}
            else:
                settings = copy.deepcopy(self.storage[-1])
            self._setup_saved_settings(settings)
        def save_settings(self):
            settings = self._get_saved_settings()
            self.storage.append(copy.deepcopy(settings))
        def __init__(self):
            SavedSettingsObject.__init__(self)
            self.load_count = 0
            self.storage = TestStorage()

    class SavedSettingsObjectTests(unittest.TestCase):
        def testSimplePropertyDoc(self):
            """Testing a minimal versioned property docstring"""
            class Test (TestObject):
                settings_properties = []
                required_saved_properties = []
                @versioned_property(
                    name="Content-type",
                    doc="A test property",
                    settings_properties=settings_properties,
                    required_saved_properties=required_saved_properties)
                def content_type(): return {}
            expected = "A test property\n\nThis property defaults to None."
            self.failUnless(Test.content_type.__doc__ == expected,
                            Test.content_type.__doc__)
        def testSimplePropertyFromMemory(self):
            """Testing a minimal versioned property from memory"""
            class Test (TestObject):
                settings_properties = []
                required_saved_properties = []
                @versioned_property(
                    name="Content-type",
                    doc="A test property",
                    settings_properties=settings_properties,
                    required_saved_properties=required_saved_properties)
                def content_type(): return {}
            t = Test()
            self.failUnless(len(t.settings) == 0, len(t.settings))
            # accessing t.content_type triggers the priming, but
            # t.storage.is_readable() == False, so nothing happens.
            t.storage.readable = False
            self.failUnless(t.content_type == None, t.content_type)
            self.failUnless(t.settings == {}, t.settings)
            self.failUnless(len(t.settings) == 0, len(t.settings))
            self.failUnless(t.content_type == None, t.content_type)
            # accessing t.content_type triggers the priming again, and
            # now that t.storage.is_readable() == True, this fills out
            # t.settings with EMPTY data.  At this point there should
            # be one load and no saves.
            t.storage.readable = True
            self.failUnless(t.content_type == None, t.content_type)
            self.failUnless(len(t.settings) == 1, len(t.settings))
            self.failUnless(t.settings["Content-type"] == EMPTY,
                            t.settings["Content-type"])
            self.failUnless(t.content_type == None, t.content_type)
            self.failUnless(t.load_count == 1, t.load_count)
            self.failUnless(len(t.storage) == 0, len(t.storage))
            # an explicit call to load settings forces a reload,
            # but nothing else changes.
            t.load_settings()
            self.failUnless(len(t.settings) == 1, len(t.settings))
            self.failUnless(t.settings["Content-type"] == EMPTY,
                            t.settings["Content-type"])
            self.failUnless(t.content_type == None, t.content_type)
            self.failUnless(t.load_count == 2, t.load_count)
            self.failUnless(len(t.storage) == 0, len(t.storage))
            # now we set a value
            t.content_type = 5
            self.failUnless(t.settings["Content-type"] == 5,
                            t.settings["Content-type"])
            self.failUnless(t.load_count == 2, t.load_count)
            self.failUnless(len(t.storage) == 1, len(t.storage))
            self.failUnless(t.storage == [{'Content-type':5}], t.storage)
            # getting its value changes nothing
            self.failUnless(t.content_type == 5, t.content_type)
            self.failUnless(t.settings["Content-type"] == 5,
                            t.settings["Content-type"])
            self.failUnless(t.load_count == 2, t.load_count)
            self.failUnless(len(t.storage) == 1, len(t.storage))
            self.failUnless(t.storage == [{'Content-type':5}], t.storage)
            # now we set another value
            t.content_type = "text/plain"
            self.failUnless(t.content_type == "text/plain", t.content_type)
            self.failUnless(t.settings["Content-type"] == "text/plain",
                            t.settings["Content-type"])
            self.failUnless(t.load_count == 2, t.load_count)
            self.failUnless(len(t.storage) == 2, len(t.storage))
            self.failUnless(t.storage == [{'Content-type':5},
                                          {'Content-type':'text/plain'}],
                            t.storage)
            # t._get_saved_settings() returns a dict of required or
            # non-default values.
            self.failUnless(t._get_saved_settings() == \
                                {"Content-type":"text/plain"},
                            t._get_saved_settings())
            # now we clear to the post-primed value
            t.content_type = EMPTY
            self.failUnless(t.settings["Content-type"] == EMPTY,
                            t.settings["Content-type"])
            self.failUnless(t.content_type == None, t.content_type)
            self.failUnless(len(t.settings) == 1, len(t.settings))
            self.failUnless(t.settings["Content-type"] == EMPTY,
                            t.settings["Content-type"])
            self.failUnless(t._get_saved_settings() == {},
                            t._get_saved_settings())
            self.failUnless(t.storage == [{'Content-type':5},
                                          {'Content-type':'text/plain'},
                                          {}],
                            t.storage)
        def testSimplePropertyFromStorage(self):
            """Testing a minimal versioned property from storage"""
            class Test (TestObject):
                settings_properties = []
                required_saved_properties = []
                @versioned_property(
                    name="prop-a",
                    doc="A test property",
                    settings_properties=settings_properties,
                    required_saved_properties=required_saved_properties)
                def prop_a(): return {}
                @versioned_property(
                    name="prop-b",
                    doc="Another test property",
                    settings_properties=settings_properties,
                    required_saved_properties=required_saved_properties)
                def prop_b(): return {}
            t = Test()
            t.storage.append({'prop-a':'saved'})
            # setting prop-b forces a load (to check for changes),
            # which also pulls in prop-a.
            t.prop_b = 'new-b'
            settings = {'prop-b':'new-b', 'prop-a':'saved'}
            self.failUnless(t.settings == settings, t.settings)
            self.failUnless(t._get_saved_settings() == settings,
                            t._get_saved_settings())
            # test that _get_saved_settings() works even when settings
            # were _not_ loaded beforehand
            t = Test()
            t.storage.append({'prop-a':'saved'})
            settings ={'prop-a':'saved'}
            self.failUnless(t.settings == {}, t.settings)
            self.failUnless(t._get_saved_settings() == settings,
                            t._get_saved_settings())
        def testSimplePropertySetStorageSave(self):
            """Set a property, then attach storage and save"""
            class Test (TestObject):
                settings_properties = []
                required_saved_properties = []
                @versioned_property(
                    name="prop-a",
                    doc="A test property",
                    settings_properties=settings_properties,
                    required_saved_properties=required_saved_properties)
                def prop_a(): return {}
                @versioned_property(
                    name="prop-b",
                    doc="Another test property",
                    settings_properties=settings_properties,
                    required_saved_properties=required_saved_properties)
                def prop_b(): return {}
            t = Test()
            storage = t.storage
            t.storage = None
            t.prop_a = 'text/html'
            t.storage = storage
            t.save_settings()
            self.failUnless(t.prop_a == 'text/html', t.prop_a)
            self.failUnless(t.settings == {'prop-a':'text/html',
                                           'prop-b':EMPTY},
                            t.settings)
            self.failUnless(t.load_count == 1, t.load_count)
            self.failUnless(len(t.storage) == 1, len(t.storage))
            self.failUnless(t.storage == [{'prop-a':'text/html'}],
                            t.storage)
        def testDefaultingProperty(self):
            """Testing a defaulting versioned property"""
            class Test (TestObject):
                settings_properties = []
                required_saved_properties = []
                @versioned_property(
                    name="Content-type",
                    doc="A test property",
                    default="text/plain",
                    settings_properties=settings_properties,
                    required_saved_properties=required_saved_properties)
                def content_type(): return {}
            t = Test()
            self.failUnless(t.settings == {}, t.settings)
            self.failUnless(t.content_type == "text/plain", t.content_type)
            self.failUnless(t.settings == {"Content-type":EMPTY},
                            t.settings)
            self.failUnless(t.load_count == 1, t.load_count)
            self.failUnless(len(t.storage) == 0, len(t.storage))
            self.failUnless(t._get_saved_settings() == {},
                            t._get_saved_settings())
            t.content_type = "text/html"
            self.failUnless(t.content_type == "text/html",
                            t.content_type)
            self.failUnless(t.settings == {"Content-type":"text/html"},
                            t.settings)
            self.failUnless(t.load_count == 1, t.load_count)
            self.failUnless(len(t.storage) == 1, len(t.storage))
            self.failUnless(t.storage == [{'Content-type':'text/html'}],
                            t.storage)
            self.failUnless(t._get_saved_settings() == \
                                {"Content-type":"text/html"},
                            t._get_saved_settings())
        def testRequiredDefaultingProperty(self):
            """Testing a required defaulting versioned property"""
            class Test (TestObject):
                settings_properties = []
                required_saved_properties = []
                @versioned_property(
                    name="Content-type",
                    doc="A test property",
                    default="text/plain",
                    settings_properties=settings_properties,
                    required_saved_properties=required_saved_properties,
                    require_save=True)
                def content_type(): return {}
            t = Test()
            self.failUnless(t.settings == {}, t.settings)
            self.failUnless(t.content_type == "text/plain", t.content_type)
            self.failUnless(t.settings == {"Content-type":EMPTY},
                            t.settings)
            self.failUnless(t.load_count == 1, t.load_count)
            self.failUnless(len(t.storage) == 0, len(t.storage))
            self.failUnless(t._get_saved_settings() == \
                                {"Content-type":"text/plain"},
                            t._get_saved_settings())
            t.content_type = "text/html"
            self.failUnless(t.content_type == "text/html",
                            t.content_type)
            self.failUnless(t.settings == {"Content-type":"text/html"},
                            t.settings)
            self.failUnless(t.load_count == 1, t.load_count)
            self.failUnless(len(t.storage) == 1, len(t.storage))
            self.failUnless(t.storage == [{'Content-type':'text/html'}],
                            t.storage)
            self.failUnless(t._get_saved_settings() == \
                                {"Content-type":"text/html"},
                            t._get_saved_settings())
        def testClassVersionedPropertyDefinition(self):
            """Testing a class-specific _versioned property decorator"""
            class Test (TestObject):
                settings_properties = []
                required_saved_properties = []
                def _versioned_property(
                        settings_properties=settings_properties,
                        required_saved_properties=required_saved_properties,
                        **kwargs):
                    if "settings_properties" not in kwargs:
                        kwargs["settings_properties"] = settings_properties
                    if "required_saved_properties" not in kwargs:
                        kwargs["required_saved_properties"] = \
                            required_saved_properties
                    return versioned_property(**kwargs)
                @_versioned_property(name="Content-type",
                                     doc="A test property",
                                     default="text/plain",
                                     require_save=True)
                def content_type(): return {}
            t = Test()
            self.failUnless(t._get_saved_settings() == \
                                {"Content-type":"text/plain"},
                            t._get_saved_settings())
            self.failUnless(t.load_count == 1, t.load_count)
            self.failUnless(len(t.storage) == 0, len(t.storage))
            t.content_type = "text/html"
            self.failUnless(t._get_saved_settings() == \
                                {"Content-type":"text/html"},
                            t._get_saved_settings())
            self.failUnless(t.load_count == 1, t.load_count)
            self.failUnless(len(t.storage) == 1, len(t.storage))
            self.failUnless(t.storage == [{'Content-type':'text/html'}],
                            t.storage)
        def testMutableChangeHookedProperty(self):
            """Testing a mutable change-hooked property"""
            class Test (TestObject):
                settings_properties = []
                required_saved_properties = []
                @versioned_property(
                    name="List-type",
                    doc="A test property",
                    mutable=True,
                    change_hook=prop_save_settings,
                    settings_properties=settings_properties,
                    required_saved_properties=required_saved_properties)
                def list_type(): return {}
            t = Test()
            self.failUnless(len(t.storage) == 0, len(t.storage))
            self.failUnless(t.list_type == None, t.list_type)
            self.failUnless(len(t.storage) == 0, len(t.storage))
            self.failUnless(t.settings["List-type"]==EMPTY,
                            t.settings["List-type"])
            t.list_type = []
            self.failUnless(t.settings["List-type"] == [],
                            t.settings["List-type"])
            self.failUnless(len(t.storage) == 1, len(t.storage))
            self.failUnless(t.storage == [{'List-type':[]}],
                            t.storage)
            t.list_type.append(5) # external modification not detected yet
            self.failUnless(len(t.storage) == 1, len(t.storage))
            self.failUnless(t.storage == [{'List-type':[]}],
                            t.storage)
            self.failUnless(t.settings["List-type"] == [5],
                            t.settings["List-type"])
            self.failUnless(t.list_type == [5], t.list_type)# get triggers save
            self.failUnless(len(t.storage) == 2, len(t.storage))
            self.failUnless(t.storage == [{'List-type':[]},
                                          {'List-type':[5]}],
                            t.storage)

    unitsuite = unittest.TestLoader().loadTestsFromTestCase( \
        SavedSettingsObjectTests)
    suite = unittest.TestSuite([unitsuite, doctest.DocTestSuite()])
