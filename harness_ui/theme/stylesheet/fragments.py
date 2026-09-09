"""Focused Qt stylesheet fragments grouped by UI responsibility."""

CHROME = '''
QMainWindow, QWidget {
    background: #16161D;
    color: #ececec;
    font-size: 10pt;
}

QToolTip {
    background-color: #1E2030;
    border: 1px solid #494D64;
    border-radius: 6px;
    color: #CAD3F5;
    font-size: 9pt;
    padding: 7px 9px;
}

QFrame#generationHelpTooltip {
    background-color: #1E2030;
    border: 1px solid #494D64;
    border-radius: 8px;
}

QLabel#generationHelpTooltipText {
    background: transparent;
    border: 0;
    color: #CAD3F5;
    font-size: 9pt;
}

QFrame#appTitleBar {
    background: #1d1d1d;
    border-bottom: 1px solid #303030;
}

QWidget#appMenuBar {
    background: #1d1d1d;
    border: 0;
    color: #B7B7C2;
    padding: 2px 6px;
    spacing: 2px;
}

QToolButton#titleBarMenuButton {
    background: transparent;
    border: 0;
    border-radius: 5px;
    color: #B7B7C2;
    padding: 5px 9px;
}

QToolButton#titleBarMenuButton:hover,
QToolButton#titleBarMenuButton:pressed,
QToolButton#titleBarMenuButton:checked {
    background: #303039;
    color: #F0F0F4;
}

QToolButton#titleBarMenuButton::menu-indicator {
    image: none;
    width: 0;
}

QToolButton#sidebarToggleButton:checked {
    background: transparent;
    border-color: transparent;
    color: #B7B7C2;
}

QToolButton#sidebarToggleButton {
    min-height: 28px;
    max-height: 28px;
    padding: 0;
    border: 0;
    border-radius: 5px;
}

QToolButton#sidebarToggleButton:checked:hover {
    background: #303039;
    border: 0;
    color: #F0F0F4;
}

QToolButton#sidebarToggleButton:hover,
QToolButton#sidebarToggleButton:pressed {
    background: #303039;
    border: 0;
    color: #F0F0F4;
}

QToolButton#titleBarMinimizeButton,
QToolButton#titleBarMaximizeButton,
QToolButton#titleBarCloseButton {
    background: transparent;
    border: 0;
    border-radius: 0;
    color: #B8C0E0;
    min-width: 38px;
    max-width: 38px;
    min-height: 34px;
    max-height: 34px;
    padding: 0;
}

QToolButton#titleBarMinimizeButton:hover,
QToolButton#titleBarMaximizeButton:hover {
    background: #303039;
}

QToolButton#titleBarMinimizeButton:pressed,
QToolButton#titleBarMaximizeButton:pressed {
    background: #3B3B45;
}

QToolButton#titleBarCloseButton:hover {
    background: #ED8796;
    color: #181926;
}

QToolButton#titleBarCloseButton:pressed {
    background: #EE99A0;
    color: #181926;
}

QPushButton,
QToolButton[buttonRole="neutral"],
QToolButton[buttonRole="primary"],
QToolButton[buttonRole="ghost"],
QToolButton[buttonRole="danger"] {
    background: #292930;
    border: 1px solid #3B3B44;
    border-radius: 7px;
    color: #f2f2f2;
    min-height: 30px;
    padding: 2px 10px;
}

QPushButton:hover,
QToolButton[buttonRole="neutral"]:hover,
QToolButton[buttonRole="primary"]:hover,
QToolButton[buttonRole="ghost"]:hover,
QToolButton[buttonRole="danger"]:hover {
    background: #34343D;
    border-color: #50505B;
}

QPushButton:pressed,
QToolButton[buttonRole="neutral"]:pressed,
QToolButton[buttonRole="primary"]:pressed,
QToolButton[buttonRole="ghost"]:pressed,
QToolButton[buttonRole="danger"]:pressed {
    background: #232329;
    border-color: #41414B;
}

QPushButton[primary="true"],
QToolButton[primary="true"] {
    background: #332B34;
    border-color: #745064;
    color: #FFD1DE;
    font-weight: 600;
}

QPushButton[primary="true"]:hover,
QToolButton[primary="true"]:hover {
    background: #3E303B;
    border-color: #A8627B;
    color: #FFE4EB;
}

QPushButton[primary="true"]:pressed,
QToolButton[primary="true"]:pressed {
    background: #2B252C;
    border-color: #83536A;
    color: #FFD1DE;
}

QPushButton[ghost="true"],
QToolButton[ghost="true"] {
    background: transparent;
    border-color: transparent;
    color: #B7B7C2;
}

QPushButton[ghost="true"]:hover,
QToolButton[ghost="true"]:hover {
    background: #25252D;
    border-color: #34343E;
    color: #F0F0F4;
}

QPushButton[ghost="true"]:pressed,
QToolButton[ghost="true"]:pressed,
QToolButton[ghost="true"]:checked {
    background: #303039;
    border-color: #454550;
    color: #FFFFFF;
}

QPushButton[danger="true"],
QToolButton[danger="true"] {
    background: #292930;
    border-color: #4B2D39;
    color: #E7A0B2;
}

QPushButton[danger="true"]:hover,
QToolButton[danger="true"]:hover {
    background: #34343D;
    border-color: #704052;
    color: #FFC0CE;
}

QPushButton[danger="true"]:pressed,
QToolButton[danger="true"]:pressed {
    background: #232329;
    border-color: #5B3444;
    color: #E7A0B2;
}

QPushButton:disabled,
QToolButton[buttonRole="neutral"]:disabled,
QToolButton[buttonRole="primary"]:disabled,
QToolButton[buttonRole="ghost"]:disabled,
QToolButton[buttonRole="danger"]:disabled {
    background: #202020;
    border-color: #292929;
    color: #6f6f6f;
}

QToolButton[buttonVariant="icon"] {
    border-radius: 7px;
    padding: 2px;
}

QToolButton[buttonVariant="icon"]::menu-indicator {
    image: none;
    width: 0;
}

QToolButton[buttonVariant="icon"]:open {
    background: #34343D;
    border-color: #50505B;
    color: #F0F0F4;
}

QPushButton[buttonVariant="navigation"] {
    text-align: left;
    padding: 2px 8px;
}

'''

DIALOGS = '''
QDialog#jobSearchDialog {
    background: transparent;
}

QDialog#unsavedScriptDialog {
    background: transparent;
}

QDialog#appDialog,
QDialog#recycleBinDialog {
    background: transparent;
}

QDialog#newJobDialog {
    background: #24273A;
}

QFrame#newJobPanel QLabel {
    background: transparent;
}

QLabel#newJobTitle {
    color: #CAD3F5;
    font-size: 11pt;
    font-weight: 600;
}

QLabel#newJobDescription {
    color: #B8C0E0;
}

QLineEdit#newJobNameInput {
    background: transparent;
    border: 0;
    color: #CAD3F5;
    padding: 7px 9px;
    selection-background-color: #5B6078;
}

QLineEdit#newJobNameInput:hover {
    border: 0;
}

QLineEdit#newJobNameInput:focus {
    border: 0;
}

QLabel#newJobValidation {
    color: #ED8796;
    font-size: 9pt;
}

QFrame#unsavedScriptPanel,
QFrame#recycleBinPanel,
QFrame#appDialogPanel,
QFrame#newJobPanel {
    background: #24273A;
    border: 1px solid #494D64;
    border-radius: 12px;
}

QLabel#unsavedScriptIcon,
QLabel#recycleBinIcon,
QLabel#appDialogIcon,
QLabel#newJobIcon {
    background: #363A4F;
    border: 1px solid #5B6078;
    border-radius: 17px;
}

QLabel#unsavedScriptTitle,
QLabel#recycleBinTitle,
QLabel#appDialogTitle {
    color: #CAD3F5;
    font-size: 11pt;
    font-weight: 600;
}

QLabel#unsavedScriptMessage,
QLabel#recycleBinMessage,
QLabel#appDialogMessage {
    color: #B8C0E0;
}

QWidget#appDialogInputForm,
QWidget#newJobForm {
    background: transparent;
}

QLabel#appDialogInputLabel {
    color: #B8C0E0;
}

QLineEdit#appDialogTextInput {
    background: #1E2030;
    border: 1px solid #494D64;
    border-radius: 7px;
    color: #CAD3F5;
    padding: 7px 9px;
    selection-background-color: #5B6078;
}

QLineEdit#appDialogTextInput:focus {
    border-color: #8BD5CA;
}

QWidget#runtimeSetupContent {
    background: transparent;
}

QLabel#runtimeSetupStatus {
    color: #CAD3F5;
    font-weight: 600;
}

QLabel#runtimeSetupStatus[error="true"],
QLabel#runtimeSetupDetail[error="true"] {
    color: #ED8796;
}

QLabel#runtimeSetupDetail {
    color: #A5ADCB;
    font-size: 9pt;
}

QProgressBar#runtimeSetupProgress {
    background: #363A4F;
    border: 1px solid #5B6078;
    border-radius: 5px;
    color: #181926;
    min-height: 14px;
    text-align: center;
}

QProgressBar#runtimeSetupProgress::chunk {
    background: #8BD5CA;
    border-radius: 4px;
}

QFrame#jobSearchPanel {
    background: #24273A;
    border: 1px solid #494D64;
    border-radius: 18px;
}

QLineEdit#jobSearchInput {
    background: #24273A;
    border: 0;
    border-bottom: 1px solid #50505B;
    border-radius: 0;
    font-size: 11pt;
    padding: 5px 2px 8px;
}

QLineEdit#jobSearchInput:focus {
    border-bottom-color: #8BD5CA;
}

QLabel#jobSearchSection,
QLabel#jobSearchHint {
    background: transparent;
}

QListWidget#jobSearchResults {
    background: #24273A;
    border: 0;
    border-radius: 0;
    padding: 2px 0;
}

QListWidget#jobSearchResults::item {
    border-radius: 6px;
    padding: 8px 10px;
}

QListWidget#jobSearchResults::item:hover,
QListWidget#jobSearchResults::item:selected {
    background: #454550;
    color: #F0F0F4;
}

QFrame#jobSearchResultRow,
QLabel#jobSearchResultTitle,
QLabel#jobSearchResultStatus {
    background: transparent;
}

QLabel#jobSearchResultTitle {
    color: #F0F0F4;
    font-size: 10pt;
}

QLabel#keyboardShortcutKey {
    background: #454550;
    border-radius: 5px;
    color: #B8C0E0;
    padding: 2px 6px;
}

QLabel#jobSearchResultStatus {
    font-size: 9pt;
}

QPushButton[ghost="true"]:disabled,
QToolButton[ghost="true"]:disabled {
    background: transparent;
    border-color: transparent;
    color: #5F5F69;
}

/* Keep the archive action's hover treatment when a poll replaces its card
   beneath a stationary cursor and Qt does not emit a new enter event. */
QToolButton#jobArchiveButton[hoverHighlightVisible="false"] {
    background: transparent;
    border-color: transparent;
    color: #B7B7C2;
}

QToolButton#jobArchiveButton[hoverHighlightVisible="true"] {
    background: #25252D;
    border-color: #34343E;
    color: #F0F0F4;
}

QToolButton#jobArchiveButton[hoverHighlightVisible="true"]:pressed {
    background: #303039;
    border-color: #454550;
    color: #FFFFFF;
}

QToolButton#jobArchiveButton,
QToolButton#scriptRowDeleteButton {
    /* QSS min-height is content-box sized; 22px plus the 1px border on each
       side keeps these icon_button() controls 24px high overall. */
    min-height: 22px;
    max-height: 22px;
    padding: 0;
}

'''

CONTROLS = '''
QLineEdit, QPlainTextEdit, QTextEdit, QComboBox, QSpinBox,
QDoubleSpinBox, QListWidget, QTreeWidget, QTableWidget {
    background: #202020;
    border: 1px solid #343434;
    border-radius: 6px;
    color: #ededed;
    selection-background-color: #FF6B9D;
    selection-color: #25171C;
}

QLineEdit:focus, QPlainTextEdit:focus, QTextEdit:focus,
QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus,
QListWidget:focus, QTreeWidget:focus, QTableWidget:focus {
    border-color: #FF8FA1;
}

QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {
    min-height: 29px;
    padding: 1px 7px;
}

QComboBox::down-arrow {
    image: none;
}

QComboBox::drop-down {
    background: transparent;
    border: 0;
    width: 17px;
}

QComboBox::drop-down:hover {
    background: #303039;
    border: 0;
}

QComboBox::drop-down:pressed {
    background: #34343D;
    border: 0;
}

QSpinBox::up-arrow, QDoubleSpinBox::up-arrow,
QSpinBox::down-arrow, QDoubleSpinBox::down-arrow {
    image: none;
}

QSpinBox::up-button, QDoubleSpinBox::up-button,
QSpinBox::down-button, QDoubleSpinBox::down-button {
    background: transparent;
    border: 0;
    width: 17px;
}

QSpinBox::up-button:hover, QDoubleSpinBox::up-button:hover,
QSpinBox::down-button:hover, QDoubleSpinBox::down-button:hover {
    background: #303039;
    border: 0;
}

QSpinBox::up-button:pressed, QDoubleSpinBox::up-button:pressed,
QSpinBox::down-button:pressed, QDoubleSpinBox::down-button:pressed {
    background: #34343D;
    border: 0;
}

'''

WORKSPACE = '''
QSpinBox:focus, QDoubleSpinBox:focus {
    border-color: #FF8FA1;
}

QPlainTextEdit, QTextEdit {
    padding: 8px;
}

QListWidget, QTreeWidget, QTableWidget {
    outline: 0;
}

QListWidget::item, QTreeWidget::item {
    min-height: 30px;
    padding: 3px 5px;
}

QListWidget::item:selected, QTreeWidget::item:selected,
QTableWidget::item:selected {
    background: #303039;
    color: #F4F4F7;
}

QListWidget#jobList::item {
    background: transparent;
    border: 0;
    padding: 0;
}

QListWidget#jobList::item:selected {
    background: transparent;
    border: 0;
}

QListWidget#jobList {
    background: #1E2030;
    border: 1px solid #303039;
    border-radius: 8px;
}

QListWidget#jobList:focus {
    border-color: #303039;
}

QListWidget#jobList[keyboardFocus="true"] {
    border-color: #8BD5CA;
}

QFrame#jobCard {
    background: transparent;
    border: 0;
    border-radius: 6px;
}

QFrame#jobCard[selected="true"] {
    background: #34343D;
}

QLabel#jobCardTitle {
    background: transparent;
    color: #F1F1F4;
    font-weight: 650;
}

QLabel#jobStatusChip {
    background: #24273A;
    border: 1px solid #5B6078;
    border-radius: 8px;
    color: #CAD3F5;
    font-size: 8pt;
    font-weight: 650;
    padding: 1px 7px;
}

QLabel#jobStatusChip[status="running"] {
    border-color: #8AADF4;
    color: #8AADF4;
}

QLabel#jobStatusChip[status="complete"] {
    border-color: #A6DA95;
    color: #A6DA95;
}

QLabel#jobStatusChip[status="failed"] {
    border-color: #ED8796;
    color: #ED8796;
}

QLabel#jobStatusChip[status="pausing"],
QLabel#jobStatusChip[status="paused"],
QLabel#jobStatusChip[status="cancelling"],
QLabel#jobStatusChip[status="interrupted"] {
    border-color: #EED49F;
    color: #EED49F;
}

QLabel#jobStatusChip[status="cancelled"] {
    border-color: #B7BDF8;
    color: #B7BDF8;
}

QLabel#jobCardMeta {
    background: transparent;
    color: #B8C0E0;
    font-size: 8.5pt;
    font-weight: 500;
}

QStackedWidget#jobListStack {
    background: transparent;
    border: 0;
}

QProgressBar#jobCardProgress {
    background: #34343D;
    border: 0;
    border-radius: 2px;
    min-height: 3px;
    max-height: 3px;
}

QProgressBar#jobCardProgress::chunk {
    background: #FF6B9D;
    border-radius: 2px;
}

QListWidget#scriptList::item:selected {
    background: #383838;
    color: #ededed;
}

QListWidget#scriptList {
    background: #1E2030;
    border: 1px solid #303039;
    border-radius: 8px;
}

QListWidget#scriptList:focus {
    border-color: #303039;
}

QListWidget#scriptList[keyboardFocus="true"],
QListWidget#scriptList[dropActive="true"] {
    border-color: #8BD5CA;
}

QListWidget#scriptList::item {
    border-bottom: 1px solid #2D2D35;
    min-height: 42px;
    padding: 5px 35px 5px 7px;
}

QLabel#editorPath {
    color: #F0F0F3;
    font-weight: 600;
}

QPlainTextEdit#scriptEditor {
    font-size: 11pt;
    background: #1E2030;
    border: 1px solid #303039;
    border-radius: 8px;
}

QPlainTextEdit#scriptEditor:focus {
    border-color: #303039;
}

QPlainTextEdit#scriptEditor[keyboardFocus="true"] {
    border-color: #8BD5CA;
}

QMenu#scriptMenu, QMenu#accentMenu,
QMenu#scriptContextMenu, QMenu#jobContextMenu,
QMenu#appFileMenu, QMenu#appEditMenu, QMenu#appViewMenu,
QMenu#appSettingsMenu, QMenu#appHelpMenu, QMenu#appSectionsMenu,
QMenu#viewAccentMenu {
    background: #222229;
    border: 1px solid #3B3B45;
    border-radius: 7px;
    color: #ECECF0;
    padding: 5px;
}

QMenu#scriptMenu::item, QMenu#accentMenu::item,
QMenu#scriptContextMenu::item, QMenu#jobContextMenu::item,
QMenu#appFileMenu::item, QMenu#appEditMenu::item,
QMenu#appViewMenu::item, QMenu#appSettingsMenu::item,
QMenu#appHelpMenu::item, QMenu#appSectionsMenu::item,
QMenu#viewAccentMenu::item {
    border-radius: 5px;
    padding: 7px 28px 7px 10px;
}

QMenu#scriptMenu::item:selected, QMenu#accentMenu::item:selected,
QMenu#scriptContextMenu::item:selected,
QMenu#jobContextMenu::item:selected,
QMenu#appFileMenu::item:selected, QMenu#appEditMenu::item:selected,
QMenu#appViewMenu::item:selected, QMenu#appSettingsMenu::item:selected,
QMenu#appHelpMenu::item:selected, QMenu#appSectionsMenu::item:selected,
QMenu#viewAccentMenu::item:selected {
    background: #34343D;
}

QMenu#accentMenu::item:checked,
QMenu#viewAccentMenu::item:checked {
    background: #34343D;
    color: #F0F0F4;
}

QMenu#accentMenu::indicator,
QMenu#viewAccentMenu::indicator,
QMenu#accentMenu::indicator:checked,
QMenu#viewAccentMenu::indicator:checked {
    image: none;
    width: 0;
    height: 0;
}

QMenu#accentMenu::item,
QMenu#viewAccentMenu::item {
    padding: 7px 10px;
}

QMenu#scriptMenu::separator, QMenu#accentMenu::separator,
QMenu#scriptContextMenu::separator,
QMenu#jobContextMenu::separator,
QMenu#appFileMenu::separator, QMenu#appEditMenu::separator,
QMenu#appViewMenu::separator, QMenu#appSettingsMenu::separator,
QMenu#appHelpMenu::separator, QMenu#appSectionsMenu::separator,
QMenu#viewAccentMenu::separator {
    background: #393942;
    height: 1px;
    margin: 5px 7px;
}

QLabel#jobHeaderTitle {
    color: #F5F5F7;
    font-size: 17pt;
    font-weight: 650;
}

QLabel#jobSegmentCount {
    background: #222229;
    border: 1px solid #34343E;
    border-radius: 6px;
    color: #A8A8B3;
    padding: 4px 8px;
}

QFrame#completionSummary {
    background: #202A26;
    border: 1px solid #345044;
    border-radius: 7px;
}

QLabel#completionMark {
    background: transparent;
    color: #85DC9A;
    font-size: 12pt;
    font-weight: 700;
}

QFrame#completionSummary QLabel {
    background: transparent;
}

QLabel#completionTitle {
    color: #EAF7EF;
    font-weight: 650;
}

QLabel#completionText {
    color: #9FB2A7;
    font-size: 9pt;
}

QFrame#emptyState {
    background: #1C1C22;
    border: 1px solid #303039;
    border-radius: 8px;
}

QFrame#emptyState[dropActive="true"] {
    border-color: #8BD5CA;
}

QFrame#emptyState QLabel {
    background: transparent;
}

QLabel#emptyStateIcon {
    color: #FF8FA9;
    font-size: 20pt;
    font-weight: 650;
}

QLabel#emptyStateTitle {
    color: #F2F2F5;
    font-size: 13pt;
    font-weight: 650;
}

QLabel#emptyStateMessage {
    color: #9B9BA7;
    font-size: 9.5pt;
}

QHeaderView::section {
    background: #202020;
    border: 0;
    border-bottom: 1px solid #363636;
    color: #aaa;
    padding: 7px;
}

QTabWidget::pane {
    border: 0;
}

QTabBar::tab {
    background: transparent;
    border: 0;
    border-bottom: 2px solid transparent;
    color: #999;
    min-width: 92px;
    padding: 9px 14px;
}

QTabBar::tab:hover:!selected {
    background: #292930;
    color: #ddd;
}

QTabBar::tab:selected {
    background: #292930;
    color: #FFD59E;
    border-bottom: 2px solid #FF6B9D;
}

QTabWidget#workTabs QTabBar::tab {
    margin-top: 0;
}

QGroupBox {
    border: 1px solid #303030;
    border-radius: 8px;
    margin-top: 13px;
    padding: 10px;
    font-weight: 600;
}

QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 4px;
}

QToolBox::tab {
    background: #242424;
    border: 1px solid #323232;
    border-radius: 6px;
    color: #ddd;
    min-height: 36px;
    padding: 0 10px;
    font-weight: 600;
}

QToolBox::tab:selected {
    background: #494D64;
    border-color: #8BD5CA;
    color: #F2F2F5;
}

QToolBox#settingsToolbox {
    background: transparent;
    border: 0;
}

QWidget#settingsSectionPage {
    background: #1E2030;
    border: 1px solid #363A4F;
    border-top: 0;
    border-bottom-left-radius: 6px;
    border-bottom-right-radius: 6px;
}

QLabel#settingsScopeHint {
    padding-bottom: 2px;
}

QLabel#settingsHelper {
    background: transparent;
    color: #8087A2;
    font-size: 8.5pt;
    padding: 0 0 2px 0;
}

QDockWidget {
    color: #ddd;
    font-weight: 600;
}

QDockWidget::title {
    background: #1f1f1f;
    border-top: 1px solid #303030;
    padding: 7px 10px;
    text-align: left;
}

QProgressBar {
    background: #272727;
    border: 0;
    border-radius: 4px;
    color: #eee;
    min-height: 8px;
    text-align: center;
}

QProgressBar::chunk {
    background: #FF6B9D;
    border-radius: 4px;
}

QSlider::groove:horizontal {
    background: #343434;
    border-radius: 3px;
    height: 6px;
}

QSlider::sub-page:horizontal {
    background: #FF6B9D;
    border-radius: 3px;
}

QSlider::handle:horizontal {
    background: #FFD59E;
    border: 2px solid #FF6B9D;
    border-radius: 7px;
    margin: -5px 0;
    width: 14px;
}

QScrollBar:vertical {
    background: transparent;
    width: 11px;
    margin: 0;
}

QScrollBar::handle:vertical {
    background: #454545;
    border-radius: 5px;
    min-height: 28px;
}

QScrollBar::handle:vertical:hover {
    background: #FF6B9D;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
}

QSplitter::handle {
    background: #303030;
}

QSplitter::handle:horizontal {
    width: 1px;
}

QSplitter::handle:vertical {
    height: 1px;
}

QLabel[muted="true"] {
    color: #9a9a9a;
}

QLabel[error="true"] {
    color: #ff8f86;
}

QLabel[status="running"] { color: #8ec5ff; }
QLabel[status="complete"] { color: #85dc9a; }
QLabel[status="failed"] { color: #ff8f86; }
QLabel[status="paused"] { color: #f1c675; }

'''

PREFERENCES = '''
QPushButton#modelInstallButton[modelState="installed"] {
    background: #202A26;
    color: #85dc9a;
}

QPushButton#modelInstallButton[modelState="installing"] {
    background: #292930;
    color: #f1c675;
}

QPushButton#modelInstallButton[modelState="repairing"] {
    background: #292930;
    color: #f1c675;
}

QDialog#preferencesDialog {
    background: transparent;
}

QFrame#preferencesPanel {
    background: #24273A;
    border: 1px solid #494D64;
    border-radius: 12px;
}

QFrame#preferencesTitleBar {
    background: #1E2030;
    border: 0;
    border-bottom: 1px solid #363A4F;
    border-top-left-radius: 12px;
    border-top-right-radius: 12px;
}

QLabel#preferencesWindowTitle {
    background: transparent;
    color: #CAD3F5;
}

QListWidget#preferencesNavigation {
    background: #1E2030;
    border: 0;
    border-right: 1px solid #363A4F;
    border-radius: 0;
    padding: 10px 8px;
    outline: 0;
}

QListWidget#preferencesNavigation::item {
    background: transparent;
    border: 0;
    border-left: 2px solid transparent;
    border-radius: 6px;
    color: #A5ADCB;
    padding: 7px 10px;
}

QListWidget#preferencesNavigation::item:hover {
    background: #363A4F;
    color: #CAD3F5;
}

QListWidget#preferencesNavigation::item:selected {
    background: #363A4F;
    border-left-color: #8BD5CA;
    color: #CAD3F5;
    font-weight: 600;
}

QStackedWidget#preferencesPages {
    background: #24273A;
    border: 0;
}

QFrame#preferencesSection {
    background: #1E2030;
    border: 1px solid #363A4F;
    border-radius: 8px;
}

QScrollArea#modelManagerScroll,
QWidget#modelManagerContent {
    background: transparent;
    border: 0;
}

QFrame#modelManagerCard {
    background: #1E2030;
    border: 1px solid #363A4F;
    border-radius: 9px;
}

QFrame#modelManagerCard QLabel {
    background: transparent;
}

QLabel#modelManagerName {
    color: #CAD3F5;
    font-size: 10.5pt;
    font-weight: 650;
}

QLabel#modelManagerRepository,
QLabel#modelManagerLocalSize {
    color: #A5ADCB;
    font-size: 9pt;
}

QLabel#modelManagerStatus {
    color: #B8C0E0;
}

QLabel#modelManagerStateBadge {
    background: #24273A;
    border: 1px solid #5B6078;
    border-radius: 9px;
    color: #B8C0E0;
    font-size: 8.5pt;
    font-weight: 600;
    padding: 3px 9px;
}

QLabel#modelManagerStateBadge[modelState="installed"] {
    border-color: #A6DA95;
    color: #A6DA95;
}

QLabel#modelManagerStateBadge[modelState="unverified"],
QLabel#modelManagerStateBadge[modelState="partial"] {
    border-color: #EED49F;
    color: #EED49F;
}

QProgressBar#modelOperationProgress {
    background: #24273A;
    border: 1px solid #363A4F;
    border-radius: 5px;
    color: #181926;
    font-weight: 600;
    min-height: 24px;
    text-align: center;
}

QProgressBar#modelOperationProgress::chunk {
    background: #8BD5CA;
    border-radius: 4px;
}

QFrame#credentialServiceCard {
    background: #1E2030;
    border: 1px solid #363A4F;
    border-radius: 9px;
}

QFrame#credentialServiceCard QLabel {
    background: transparent;
}

QLabel#credentialServiceName {
    color: #CAD3F5;
    font-size: 10.5pt;
    font-weight: 650;
}

QLabel#credentialServiceDescription {
    color: #A5ADCB;
    font-size: 9pt;
}

QLabel#credentialStatusBadge {
    background: #24273A;
    border: 1px solid #5B6078;
    border-radius: 9px;
    color: #B8C0E0;
    font-size: 9pt;
    font-weight: 600;
    padding: 4px 10px;
}

QLabel#credentialStatusBadge[credentialState="configured"] {
    background: #363A4F;
    border-color: #A6DA95;
    color: #A6DA95;
}

QLabel#credentialStatusBadge[credentialState="error"] {
    background: #363A4F;
    border-color: #ED8796;
    color: #ED8796;
}

QLabel#preferencesFeedback {
    color: #A6DA95;
}

QLabel#preferencesFeedback[error="true"] {
    color: #ED8796;
}
'''

