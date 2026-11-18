"""A visible command row beneath the native macOS title bar."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QToolBar

from .menu_bar import TitleBarMenuBar


def add_window_menu_row(window, menus):
    toolbar = QToolBar("Application menus", window)
    toolbar.setObjectName("windowMenuToolbar")
    toolbar.setMovable(False)
    toolbar.setFloatable(False)
    toolbar.setAllowedAreas(Qt.ToolBarArea.TopToolBarArea)
    toolbar.toggleViewAction().setVisible(False)

    strip = TitleBarMenuBar(toolbar)
    strip.setObjectName("appMenuBar")
    strip.setFixedHeight(34)
    for source in menus:
        _copy_menu(source, strip.addMenu(source.title()))
    toolbar.addWidget(strip)
    window.addToolBar(Qt.ToolBarArea.TopToolBarArea, toolbar)
    return toolbar, strip


def _copy_menu(source, target):
    # Cocoa owns the original QMenus. Separate popup menus can remain in the
    # window while shared QActions keep commands, shortcuts and state in sync.
    target.aboutToShow.connect(source.aboutToShow.emit)
    for action in source.actions():
        submenu = action.menu()
        if submenu is not None:
            _copy_menu(submenu, target.addMenu(submenu.title()))
        else:
            target.addAction(action)
