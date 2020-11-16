# SPDX-License-Identifier: GPL-3.0-only
import logging
import sys
from typing import Any, List, Optional

from gi.repository import Gio, GLib, Gtk, Handy

import passwordsafe.pathbar_button
from passwordsafe.main_window import MainWindow
from passwordsafe.settings_dialog import SettingsDialog


class Application(Gtk.Application):
    window: MainWindow = None
    file_list: List[Gio.File] = []
    development_mode = False
    application_id = "org.gnome.PasswordSafe"

    def __init__(self, *args, **_kwargs):
        app_flags = (Gio.ApplicationFlags.HANDLES_OPEN
                     | Gio.ApplicationFlags.HANDLES_COMMAND_LINE)
        super().__init__(
            *args, application_id=self.application_id,
            flags=app_flags)

        # debug level logging option
        self.add_main_option("debug", ord("d"), GLib.OptionFlags.NONE,
                             GLib.OptionArg.NONE,
                             "Enable debug logging",
                             None)

    def do_startup(self):  # pylint: disable=arguments-differ
        Gtk.Application.do_startup(self)
        GLib.set_application_name('Password Safe')
        GLib.set_prgname("Password Safe")

        Handy.init()
        self.connect("open", self.file_open_handler)
        self.assemble_application_menu()

        go_back_action = Gio.SimpleAction.new("go_back", None)
        go_back_action.connect("activate", self._goto_parent_group)
        self.add_action(go_back_action)
        self.set_accels_for_action("app.go_back", ["Escape"])

    def do_command_line(self, cmd_line):  # pylint: disable=arguments-differ
        options = cmd_line.get_options_dict()
        # convert GVariantDict -> GVariant -> dict
        options = options.end().unpack()

        # set up logging depending on the verbosity level
        loglevel = logging.INFO
        if self.development_mode or 'debug' in options:
            loglevel = logging.DEBUG
            # Don't clutter our log output with debug msg of the
            # pykeepass module it is very noisy.
            pykeepass_logger = logging.getLogger("pykeepass")
            pykeepass_logger.setLevel(logging.INFO)

        logging.basicConfig(format="%(asctime)s | %(levelname)s | %(message)s",
                            datefmt='%d-%m-%y %H:%M:%S', level=loglevel)

        self.activate()
        return 0

    def do_activate(self):  # pylint: disable=arguments-differ
        if self.window:
            # Window exists already eg if we invoke us a 2nd time.
            # Just present the existing one.
            self.window.present()
            return
        self.window = MainWindow(
            application=self, title="Password Safe",
            icon_name=self.application_id)

        self.add_menubutton_popover_actions()
        self.window.add_row_popover_actions()
        self.window.add_database_menubutton_popover_actions()
        self.window.add_selection_actions()
        self.add_global_accelerators()

        self.window.present()

    def assemble_application_menu(self):
        settings_action = Gio.SimpleAction.new("settings", None)
        settings_action.connect("activate", self.on_settings_menu_clicked)

        about_action = Gio.SimpleAction.new("about", None)
        about_action.connect("activate", self.on_about_menu_clicked)

        quit_action = Gio.SimpleAction.new("quit", None)
        quit_action.connect("activate", self.on_quit)
        self.set_accels_for_action("app.quit", ["<Control>q"])

        shortcuts_action = Gio.SimpleAction.new("shortcuts", None)
        shortcuts_action.connect("activate", self.on_shortcuts_menu_clicked)

        self.add_action(settings_action)
        self.add_action(about_action)
        self.add_action(quit_action)
        self.add_action(shortcuts_action)

    def _goto_parent_group(self, _action: Gio.SimpleAction, _: None) -> None:
        """Go to the parent group of the pathbar."""
        for db in self.window.opened_databases:
            if db.props.database_locked:
                return

            db_manager = db.database_manager

            if db.props.selection_mode:
                db.props.selection_mode = False
                return

            if db.props.search_active:
                db.props.search_active = False
                return

            def can_go_back():
                current_element = db.current_element

                if (db_manager.check_is_group_object(current_element)
                    and db_manager.check_is_root_group(current_element)):
                    return False
                return True

            if not can_go_back():
                return

            parent_group = db_manager.get_parent_group(
                db.current_element)

            if db_manager.check_is_root_group(parent_group):
                pathbar = db.pathbar
                pathbar.on_home_button_clicked(pathbar.home_button)

            pathbar_btn_type = passwordsafe.pathbar_button.PathbarButton
            for button in db.pathbar:
                if (
                    isinstance(button, pathbar_btn_type)
                    and button.uuid == parent_group.uuid
                ):
                    pathbar = db.pathbar
                    pathbar.on_pathbar_button_clicked(button)

    def on_settings_menu_clicked(self, action, param):
        SettingsDialog(self.window).on_settings_menu_clicked(action, param)

    def on_about_menu_clicked(self, _action, _param):
        builder = Gtk.Builder()
        builder.add_from_resource("/org/gnome/PasswordSafe/about_dialog.ui")
        about_dialog = builder.get_object("about_dialog")
        about_dialog.set_modal(True)
        if self.window is not NotImplemented:
            about_dialog.set_transient_for(self.window)
        about_dialog.present()

    def on_quit(self, _action: Optional[Gio.SimpleAction] = None,
                _data: Any = None) -> None:
        # Perform cleanups, this calls application.quit() itself if `handled`
        handled: bool = self.window.on_application_shutdown()
        if not handled:
            self.quit()

    def on_shortcuts_menu_clicked(self, _action, _param):
        builder = Gtk.Builder()
        builder.add_from_resource("/org/gnome/PasswordSafe/shortcuts_overview.ui")
        shortcuts_overview = builder.get_object("shortcuts_overview")
        if self.window is not NotImplemented:
            shortcuts_overview.set_transient_for(self.window)
        shortcuts_overview.show()

    def add_menubutton_popover_actions(self):
        new_action = Gio.SimpleAction.new("new", None)
        new_action.connect("activate", self.window.create_filechooser)
        self.add_action(new_action)

        open_action = Gio.SimpleAction.new("open", None)
        open_action.connect("activate", self.window.open_filechooser)
        self.add_action(open_action)

    def file_open_handler(self, _application, g_file_list, _amount, _ukwn):
        for g_file in g_file_list:
            self.file_list.append(g_file)
            if self.window is not None:
                self.window.start_database_opening_routine(g_file.get_path())

        self.do_activate()

    def add_global_accelerators(self):
        self.window.add_global_accelerator_actions()
        self.set_accels_for_action("app.settings", ["<Control>p"])
        self.set_accels_for_action("app.open", ["<Control>o"])
        self.set_accels_for_action("app.new", ["<Control><Shift>n"])
        self.set_accels_for_action("app.db.save", ["<Control>s"])
        self.set_accels_for_action("app.db.lock", ["<Control>l"])
        self.set_accels_for_action("app.db.add_entry", ["<Control>n"])
        self.set_accels_for_action("app.db.add_group", ["<Control>g"])
        self.set_accels_for_action("app.undo", ["<Control>z"])
        self.set_accels_for_action("app.redo", ["<Control>y"])


if __name__ == "__main__":
    app = Application()
    app.run(sys.argv)
