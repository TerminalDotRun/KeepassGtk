# SPDX-License-Identifier: GPL-3.0-only
from __future__ import annotations

import typing
from gettext import gettext as _

from gi.repository import GObject, Gtk
from passwordsafe.safe_element import SafeGroup

if typing.TYPE_CHECKING:
    from passwordsafe.unlocked_database import UnlockedDatabase


@Gtk.Template(resource_path="/org/gnome/PasswordSafe/group_row.ui")
class GroupRow(Gtk.ListBoxRow):

    __gtype_name__ = "GroupRow"

    _entry_box_gesture = Gtk.Template.Child()
    name_label = Gtk.Template.Child()
    selection_checkbox = Gtk.Template.Child()
    edit_button = Gtk.Template.Child()
    _entry_box_gesture = Gtk.Template.Child()

    type = "GroupRow"

    def __init__(self, unlocked_database, safe_group):
        Gtk.ListBoxRow.__init__(self)
        self.get_style_context().add_class("row")

        assert isinstance(safe_group, SafeGroup)
        self.unlocked_database = unlocked_database
        self.safe_group = safe_group
        self.assemble_group_row()

    def assemble_group_row(self):
        self._entry_box_gesture.connect(
            "pressed", self._on_group_row_button_pressed)

        if self.safe_group.name:
            self.name_label.set_text(self.safe_group.name)
        else:
            self.name_label.set_markup("<span font-style=\"italic\">" + _("No group title specified") + "</span>")

        # Selection Mode Checkboxes
        self.unlocked_database.bind_property(
            "selection_mode",
            self.selection_checkbox,
            "visible",
            GObject.BindingFlags.SYNC_CREATE,
        )
        self.unlocked_database.connect(
            "notify::selection-mode",
            self._on_selection_mode_change,
            self.selection_checkbox,
        )

        # Edit Button
        self.unlocked_database.bind_property(
            "selection_mode",
            self.edit_button,
            "visible",
            GObject.BindingFlags.SYNC_CREATE | GObject.BindingFlags.INVERT_BOOLEAN,
        )

    def _on_selection_mode_change(
        self,
        unlocked_db: UnlockedDatabase,
        _value: GObject.ParamSpecBoolean,
        checkbox: Gtk.CheckBox,
    ) -> None:
        if not unlocked_db.props.selection_mode:
            checkbox.set_active(False)

    def _on_group_row_button_pressed(
            self, _gesture: Gtk.GestureMultiPress, _n_press: int, _event_x: float,
            _event_y: float) -> None:
        # pylint: disable=too-many-arguments
        db_view: UnlockedDatabase = self.unlocked_database
        db_view.start_database_lock_timer()

        if not db_view.props.search_active:
            if db_view.props.selection_mode:
                active = self.selection_checkbox.props.active
                self.selection_checkbox.props.active = not active
            else:
                db_view.props.selection_mode = True
                self.selection_checkbox.props.active = True

    def get_uuid(self):
        return self.safe_group.uuid

    @Gtk.Template.Callback()
    def on_selection_checkbox_toggled(self, _widget):
        if self.selection_checkbox.get_active():
            self.unlocked_database.selection_ui.add_group(self)
        else:
            self.unlocked_database.selection_ui.remove_group(self)

    @Gtk.Template.Callback()
    def on_group_edit_button_clicked(self, button: Gtk.Button) -> None:
        """Edit button in a GroupRow was clicked

        button: The edit button in the GroupRow"""
        self.unlocked_database.start_database_lock_timer()  # Reset the lock timer

        self.unlocked_database.props.current_element = self.safe_group
        self.unlocked_database.show_page_of_new_directory(True, False)
