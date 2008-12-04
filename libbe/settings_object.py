# Bugs Everywhere - a distributed bugtracker
# Copyright (C) 2008 W. Trevor King <wking@drexel.edu>
#
#   This program is free software: you can redistribute it and/or modify
#   it under the terms of the GNU General Public License as published by
#   the Free Software Foundation, either version 3 of the License, or
#   (at your option) any later version.
#
#   This program is distributed in the hope that it will be useful,
#   but WITHOUT ANY WARRANTY; without even the implied warranty of
#   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#   GNU General Public License for more details.
#
#   You should have received a copy of the GNU General Public License
#   along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""
This module provides a base class implementing settings-dict based
property storage useful for BE objects with saved properties
(e.g. BugDir, Bug, Comment).  For example usage, consider the
unittests at the end of the module.
"""

import doctest
import unittest

from properties import Property, doc_property, local_property, \
    defaulting_property, checked_property, fn_checked_property, \
    cached_property, primed_property, change_hook_property, \
    settings_property

# Define an invalid value for our properties, distinct from None,
# which shows that a property has been initialized but has no value.
EMPTY = -1


def prop_save_settings(self, old, new):
    if self.sync_with_disk==True:
        self.save_settings()
def prop_load_settings(self):
    if self.sync_with_disk==True and self._settings_loaded==False:
        self.load_settings()
    else:
        self._setup_saved_settings(flag_as_loaded=False)

def setting_name_to_attr_name(self, name):
    """
    Convert keys to the .settings dict into their associated
    SavedSettingsObject attribute names.
    >>> print setting_name_to_attr_name(None,"User-id")
    user_id
    """
    return name.lower().replace('-', '_')

def attr_name_to_setting_name(self, name):
    """
    The inverse of setting_name_to_attr_name.
    >>> print attr_name_to_setting_name(None, "user_id")
    User-id
    """
    return name.capitalize().replace('_', '-')

def versioned_property(name, doc,
                       default=None, generator=None,
                       change_hook=prop_save_settings,
                       primer=prop_load_settings,
                       allowed=None, check_fn=None,
                       settings_properties=[],
                       required_saved_properties=[],
                       require_save=False):
    """
    Combine the common decorators in a single function.
    
    Use zero or one (but not both) of default or generator, since a
    working default will keep the generator from functioning.  Use the
    default if you know what you want the default value to be at
    'coding time'.  Use the generator if you can write a function to
    determine a valid default at run time.
        
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
    """
    settings_properties.append(name)
    if require_save == True:
        required_saved_properties.append(name)
    def decorator(funcs):
        fulldoc = doc
        if default != None:
            defaulting  = defaulting_property(default=default, null=EMPTY)
            fulldoc += "\n\nThis property defaults to %s" % default
        if generator != None:
            cached = cached_property(generator=generator, initVal=EMPTY)
            fulldoc += "\n\nThis property is generated with %s" % generator
        if check_fn != None:
            fn_checked = fn_checked_property(value_allowed_fn=check_fn)
            fulldoc += "\n\nThis property is checked with %s" % check_fn
        if allowed != None:
            checked = checked_property(allowed=allowed)
            fulldoc += "\n\nThe allowed values for this property are: %s." \
                       % (', '.join(allowed))
        hooked      = change_hook_property(hook=change_hook)
        primed      = primed_property(primer=primer)
        settings    = settings_property(name=name)
        docp        = doc_property(doc=fulldoc)
        deco = hooked(primed(settings(docp(funcs))))
        if default != None:
            deco = defaulting(deco)
        if generator != None:
            deco = cached(deco)
        if default != None:
            deco = defaulting(deco)
        if allowed != None:
            deco = checked(deco)
        if check_fn != None:
            deco = fn_checked(deco)
        return Property(deco)
    return decorator

class SavedSettingsObject(object):

    # Keep a list of properties that may be stored in the .settings dict.
    #settings_properties = []

    # A list of properties that we save to disk, even if they were
    # never set (in which case we save the default value).  This
    # protects against future changes in default values.
    #required_saved_properties = []

    _setting_name_to_attr_name = setting_name_to_attr_name
    _attr_name_to_setting_name = attr_name_to_setting_name

    def __init__(self):
        self._settings_loaded = False
        self.sync_with_disk = False
        self.settings = {}

    def load_settings(self):
        """Load the settings from disk."""
        # Override.  Must call ._setup_saved_settings() after loading.
        self.settings = {}
        self._setup_saved_settings()
        
    def _setup_saved_settings(self, flag_as_loaded=True):
        """To be run after setting self.settings up from disk."""
        for property in self.settings_properties:
            if property not in self.settings:
                self.settings[property] = EMPTY
            elif self.settings[property] == None:
                self.settings[property] = EMPTY
        if flag_as_loaded == True:
            self._settings_loaded = True

    def save_settings(self):
        """Load the settings from disk."""
        # Override.  Should save the dict output of ._get_saved_settings()
        settings = self._get_saved_settings()
        pass # write settings to disk....

    def _get_saved_settings(self):
        settings = {}
        for k,v in self.settings.items():
            if v != None and v != EMPTY:
                settings[k] = v
        for k in self.required_saved_properties:
            settings[k] = getattr(self, self._setting_name_to_attr_name(k))
        return settings
    
    def clear_cached_setting(self, setting=None):
        "If setting=None, clear *all* cached settings"
        if setting != None:
            if hasattr(self, "_%s_cached_value" % setting):
                delattr(self, "_%s_cached_value" % setting)
        else:
            for setting in settings_properties:
                self.clear_cached_setting(setting)


class SavedSettingsObjectTests(unittest.TestCase):
    def testDefaultingProperty(self):
        class Test(SavedSettingsObject):
            settings_properties = []
            required_saved_properties = []
            @versioned_property(name="Content-type",
                                doc="A test property",
                                default="text/plain",
                                settings_properties=settings_properties,
                                required_saved_properties=required_saved_properties)
            def content_type(): return {}
            def __init__(self):
                SavedSettingsObject.__init__(self)
        t = Test()
        self.failUnless(t._settings_loaded == False, t._settings_loaded)
        self.failUnless(t.content_type == "text/plain", t.content_type)
        self.failUnless(t._settings_loaded == False, t._settings_loaded)
        t.load_settings()
        self.failUnless(t._settings_loaded == True, t._settings_loaded)
        self.failUnless(t.content_type == "text/plain", t.content_type)
        self.failUnless(t.settings["Content-type"] == EMPTY,
                        t.settings["Content-type"])
        self.failUnless(t._get_saved_settings() == {}, t._get_saved_settings())
        t.content_type = "text/html"
        self.failUnless(t.content_type == "text/html",
                        t.content_type)
        self.failUnless(t.settings["Content-type"] == "text/html",
                        t.settings["Content-type"])
        self.failUnless(t._get_saved_settings()=={"Content-type":"text/html"},
                        t._get_saved_settings())
    def testRequiredDefaultingProperty(self):
        class Test(SavedSettingsObject):
            settings_properties = []
            required_saved_properties = []
            @versioned_property(name="Content-type",
                                doc="A test property",
                                default="text/plain",
                                settings_properties=settings_properties,
                                required_saved_properties=required_saved_properties,
                                require_save=True)
            def content_type(): return {}
            def __init__(self):
                SavedSettingsObject.__init__(self)
        t = Test()
        self.failUnless(t._get_saved_settings()=={"Content-type":"text/plain"},
                        t._get_saved_settings())
        t.content_type = "text/html"
        self.failUnless(t._get_saved_settings()=={"Content-type":"text/html"},
                        t._get_saved_settings())
    def testClassVersionedPropertyDefinition(self):
        class Test(SavedSettingsObject):
            settings_properties = []
            required_saved_properties = []
            def _versioned_property(settings_properties=settings_properties,
                                    required_saved_properties=required_saved_properties,
                                    **kwargs):
                if "settings_properties" not in kwargs:
                    kwargs["settings_properties"] = settings_properties
                if "required_saved_properties" not in kwargs:
                    kwargs["required_saved_properties"]=required_saved_properties
                return versioned_property(**kwargs)
            @_versioned_property(name="Content-type",
                                doc="A test property",
                                default="text/plain",
                                require_save=True)
            def content_type(): return {}
            def __init__(self):
                SavedSettingsObject.__init__(self)
        t = Test()
        self.failUnless(t._get_saved_settings()=={"Content-type":"text/plain"},
                        t._get_saved_settings())
        t.content_type = "text/html"
        self.failUnless(t._get_saved_settings()=={"Content-type":"text/html"},
                        t._get_saved_settings())

unitsuite=unittest.TestLoader().loadTestsFromTestCase(SavedSettingsObjectTests)
suite = unittest.TestSuite([unitsuite, doctest.DocTestSuite()])