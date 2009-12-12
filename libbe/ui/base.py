    def _setup_user_id(self, user_id):
        if isinstance(self.storage, storage.vcs.base.VCS):
            self.storage.user_id = user_id
    def _guess_user_id(self):
        if isinstance(self.storage, storage.vcs.base.VCS):
            return self.storage.get_user_id()
    def _set_user_id(self, old_user_id, new_user_id):
        self._setup_user_id(new_user_id)
        self._prop_save_settings(old_user_id, new_user_id)

    @_versioned_property(name="user_id",
                         doc=
"""The user's prefered name, e.g. 'John Doe <jdoe@example.com>'.  Note
that the Arch VCS backend *enforces* ids with this format.""",
                         change_hook=_set_user_id,
                         generator=_guess_user_id)
    def user_id(): return {}

    @_versioned_property(name="default_assignee",
                         doc=
"""The default assignee for new bugs e.g. 'John Doe <jdoe@example.com>'.""")
    def default_assignee(): return {}

