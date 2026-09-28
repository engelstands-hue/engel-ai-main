"""Shared Qt stylesheet fragments for Engel desktop GUIs.

Terminal / monospace theme — dense, readable, zero decoration.
  * Background  #0a0a0a / #111111
  * Text        #cccccc / #888888 (dim)
  * Green       #00ff88  (live / active)
  * Amber       #ffaa00  (warning / value)
  * Red         #ff4444  (error / blocked)
  * Blue        #44aaff  (info / label)
  * Border      #222222 / #333333
  * Font        Consolas, monospace throughout
"""

from __future__ import annotations

COLONY_HIVE_ROOT_OBJECT_NAME = "EngelColonyHiveRoot"

_BG    = "#0a0a0a"
_SURF  = "#111111"
_SURF2 = "#161616"
_BDR   = "#222222"
_BDR2  = "#333333"
_TEXT  = "#cccccc"
_DIM   = "#666666"
_GREEN = "#00ff88"
_AMBER = "#ffaa00"
_RED   = "#ff4444"
_BLUE  = "#44aaff"
_SEL   = "#1a3a1a"
_FONT  = "Consolas, 'Cascadia Mono', 'Courier New', monospace"


def colony_hive_application_stylesheet() -> str:
    return f"""
        QWidget#{COLONY_HIVE_ROOT_OBJECT_NAME} {{ background: {_BG}; }}
        QWidget {{
            background: {_BG};
            color: {_TEXT};
            font-family: {_FONT};
            font-size: 9pt;
        }}
        QPushButton {{
            background: {_SURF};
            color: {_GREEN};
            border: 1px solid {_BDR2};
            border-radius: 0px;
            padding: 3px 8px;
            font-weight: 700;
            font-size: 9pt;
            min-height: 22px;
        }}
        QPushButton:hover {{
            background: {_SURF2};
            border-color: {_GREEN};
            color: #ffffff;
        }}
        QPushButton:pressed {{
            background: #1a2a1a;
            border-color: {_GREEN};
        }}
        QPushButton:disabled {{
            color: {_DIM};
            border-color: {_BDR};
            background: {_SURF};
        }}
        QPushButton:focus, QLineEdit:focus, QComboBox:focus, QTabBar::tab:focus {{
            border: 1px solid {_GREEN};
        }}
        QTextEdit {{
            background: {_BG};
            border: 1px solid {_BDR2};
            border-radius: 0px;
            color: {_TEXT};
            padding: 6px;
            font-family: {_FONT};
            font-size: 9pt;
            selection-background-color: {_SEL};
            selection-color: #ffffff;
        }}
        QLineEdit, QComboBox {{
            background: {_SURF};
            border: 1px solid {_BDR2};
            border-radius: 0px;
            color: {_TEXT};
            padding: 3px 6px;
            min-height: 20px;
            font-family: {_FONT};
            font-size: 9pt;
        }}
        QComboBox::drop-down {{ border: 0; width: 18px; }}
        QScrollArea {{ border: 0; background: transparent; }}
        QScrollArea > QWidget > QWidget {{ background: transparent; }}
        QScrollBar:vertical {{
            background: {_BG};
            width: 6px; margin: 0;
        }}
        QScrollBar::handle:vertical {{
            background: {_BDR2};
            min-height: 20px;
        }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
        QScrollBar:horizontal {{
            background: {_BG};
            height: 6px; margin: 0;
        }}
        QScrollBar::handle:horizontal {{
            background: {_BDR2};
            min-width: 20px;
        }}
        QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}
        QSplitter::handle:horizontal {{ width: 3px; background: {_BDR2}; }}
        QSplitter::handle:vertical {{ height: 3px; background: {_BDR2}; }}
        QSplitter::handle:hover {{ background: {_GREEN}; }}
        QTabWidget::pane {{
            border: 1px solid {_BDR2};
            border-top: 0;
            background: {_BG};
        }}
        QTabBar::tab {{
            background: {_SURF};
            color: {_DIM};
            border: 1px solid {_BDR};
            border-bottom: 0;
            border-radius: 0px;
            padding: 4px 10px;
            font-family: {_FONT};
            font-weight: 700;
            font-size: 8.5pt;
        }}
        QTabBar::tab:hover {{ color: {_TEXT}; border-color: {_BDR2}; }}
        QTabBar::tab:selected {{
            background: {_BG};
            color: {_GREEN};
            border-color: {_BDR2};
            border-bottom: 1px solid {_BG};
        }}
        QTabBar::scroller {{ width: 20px; }}
        QCheckBox {{ color: {_TEXT}; spacing: 5px; font-family: {_FONT}; font-size: 9pt; }}
        QCheckBox::indicator {{ width: 13px; height: 13px; border: 1px solid {_BDR2}; background: {_SURF}; }}
        QCheckBox::indicator:checked {{ background: {_GREEN}; border-color: {_GREEN}; }}
        QToolTip {{
            background: {_SURF};
            color: {_TEXT};
            border: 1px solid {_BDR2};
            padding: 4px;
            font-family: {_FONT};
            font-size: 8.5pt;
        }}
    """


def companion_chat_stylesheet() -> str:
    return f"""
        QTextEdit {{
            background: {_BG};
            color: {_TEXT};
            border: 1px solid {_BDR2};
            border-radius: 0px;
            padding: 8px;
            font-family: {_FONT};
            font-size: 9pt;
            selection-background-color: {_SEL};
            selection-color: #ffffff;
        }}
    """


def companion_input_stylesheet() -> str:
    return f"""
        QLineEdit {{
            background: {_SURF};
            color: {_GREEN};
            border: 1px solid {_BDR2};
            border-top: 2px solid {_BDR2};
            border-radius: 0px;
            padding: 6px 8px;
            font-family: {_FONT};
            font-size: 9pt;
            min-height: 18px;
        }}
        QLineEdit:focus {{ border-color: {_GREEN}; }}
    """


def companion_dashboard_title_stylesheet() -> str:
    return (
        f"QLabel {{color:{_GREEN}; font: 900 11px {_FONT}; "
        f"letter-spacing: 3px; background: {_BG}; "
        f"border-bottom: 1px solid {_BDR2}; padding: 4px 6px;}}"
    )


def companion_dashboard_subtitle_stylesheet() -> str:
    return (
        f"QLabel {{color:{_DIM}; font: 400 8pt {_FONT}; "
        f"background: {_BG}; padding: 2px 6px;}}"
    )


def companion_status_rail_stylesheet() -> str:
    return (
        f"QLabel {{color:{_AMBER}; font: 700 7.5pt {_FONT}; "
        f"letter-spacing: 0.5px; background: {_SURF}; "
        f"border: 1px solid {_BDR2}; padding: 3px 6px;}}"
    )


def companion_toggle_stylesheet() -> str:
    return (
        f"QPushButton {{background:{_SURF}; color:{_BLUE}; "
        f"border: 1px solid {_BDR2}; border-radius:0px; "
        f"padding:3px 7px; font: 700 8pt {_FONT}; min-height:18px;}}"
        f"QPushButton:checked {{background:#1a2a1a; color:{_GREEN}; border-color:{_GREEN};}}"
        f"QPushButton:hover {{background:{_SURF2}; color:#ffffff;}}"
    )


def companion_open_host_stylesheet() -> str:
    return (
        f"QFrame#CompanionOpenHost {{background:{_BG}; "
        f"border: 1px solid {_BDR2}; border-radius:0px;}}"
    )


def companion_right_col_stylesheet() -> str:
    return (
        f"QWidget#CompanionRightCol {{background:{_SURF}; "
        f"border: 1px solid {_BDR2}; border-radius:0px; padding:4px;}}"
    )


def super_swarm_text_box_stylesheet() -> str:
    return f"""
        QTextEdit {{
            background: {_BG};
            border: 1px solid {_BDR2};
            border-radius: 0px;
            color: {_TEXT};
            padding: 6px;
            font-family: {_FONT};
            font-size: 9pt;
            selection-background-color: {_SEL};
            selection-color: #ffffff;
        }}
    """


def super_swarm_application_stylesheet() -> str:
    return f"""
        QMainWindow, QWidget {{
            background: {_BG};
            color: {_TEXT};
            font-family: {_FONT};
            font-size: 9pt;
        }}
        QPushButton {{
            background: {_SURF};
            border: 1px solid {_BDR2};
            border-radius: 0px;
            color: {_BLUE};
            padding: 3px 8px;
            font-weight: 700;
            font-size: 9pt;
            min-height: 22px;
        }}
        QPushButton:hover {{
            border-color: {_GREEN};
            color: #ffffff;
            background: {_SURF2};
        }}
        QPushButton:pressed {{
            background: #1a2a1a;
            border-color: {_GREEN};
            color: {_GREEN};
        }}
        QPushButton:disabled {{
            background: {_SURF};
            border-color: {_BDR};
            color: {_DIM};
        }}
        QPushButton:focus, QToolButton:focus, QLineEdit:focus,
        QComboBox:focus, QTabBar::tab:focus {{
            border: 1px solid {_GREEN};
        }}
        QToolButton {{
            background: {_SURF};
            border: 1px solid {_BDR2};
            border-radius: 0px;
            color: {_TEXT};
            padding: 3px 8px;
            font-weight: 700;
            font-size: 9pt;
        }}
        QToolButton:hover {{ border-color: {_AMBER}; color: #ffffff; }}
        QToolButton:disabled {{ color: {_DIM}; border-color: {_BDR}; }}
        QPushButton#GuardianButton {{ border-color: {_GREEN}; color: {_GREEN}; }}
        QTabWidget::pane {{
            border: 1px solid {_BDR2};
            border-top: 0;
            background: {_BG};
        }}
        QTabBar::tab {{
            background: {_SURF};
            color: {_DIM};
            border: 1px solid {_BDR};
            border-bottom: 0;
            border-radius: 0px;
            padding: 4px 10px;
            font-weight: 700;
            font-size: 8.5pt;
        }}
        QTabBar::tab:selected {{
            background: {_BG};
            color: {_GREEN};
            border-color: {_BDR2};
        }}
        QTabBar::tab:hover {{ color: {_TEXT}; border-color: {_BDR2}; }}
        QTabBar::scroller {{ width: 22px; }}
        QFrame#SafetyBanner {{
            background: #0a1a0a;
            border: 1px solid #1a4a1a;
            border-radius: 0px;
        }}
        QFrame#Footer, QFrame#Panel, QFrame#CardPanel,
        QFrame#BottomPanel, QFrame#SidePanel {{
            background: {_SURF};
            border: 1px solid {_BDR2};
            border-radius: 0px;
        }}
        QGroupBox {{
            border: 1px solid {_BDR2};
            border-radius: 0px;
            margin-top: 10px;
            color: {_DIM};
            font-weight: 700;
        }}
        QGroupBox::title {{
            subcontrol-origin: margin;
            left: 6px;
            padding: 0 3px;
            color: {_GREEN};
        }}
        QCheckBox {{ color: {_TEXT}; spacing: 5px; font-size: 9pt; }}
        QCheckBox::indicator {{
            width: 13px; height: 13px;
            border: 1px solid {_BDR2}; background: {_SURF};
        }}
        QCheckBox::indicator:checked {{ background: {_GREEN}; border-color: {_GREEN}; }}
        QLineEdit, QComboBox {{
            background: {_SURF};
            border: 1px solid {_BDR2};
            border-radius: 0px;
            color: {_TEXT};
            padding: 3px 6px;
            min-height: 20px;
            font-family: {_FONT};
            font-size: 9pt;
        }}
        QComboBox QAbstractItemView {{
            background: {_SURF};
            color: {_TEXT};
            border: 1px solid {_BDR2};
            selection-background-color: {_SEL};
        }}
        QToolTip {{
            background: {_SURF};
            color: {_TEXT};
            border: 1px solid {_BDR2};
            padding: 4px;
            font-size: 8.5pt;
        }}
        QTableWidget {{
            background: {_BG};
            alternate-background-color: {_SURF};
            border: 1px solid {_BDR2};
            border-radius: 0px;
            color: {_TEXT};
            gridline-color: {_BDR};
            selection-background-color: {_SEL};
            selection-color: #ffffff;
            font-family: {_FONT};
            font-size: 9pt;
        }}
        QTableWidget::item {{ padding: 2px 4px; }}
        QHeaderView::section {{
            background: {_SURF2};
            color: {_GREEN};
            border: 0;
            border-right: 1px solid {_BDR};
            border-bottom: 1px solid {_BDR2};
            padding: 4px 6px;
            font-weight: 700;
            font-size: 8.5pt;
        }}
        QProgressBar {{
            background: {_SURF};
            border: 1px solid {_BDR2};
            border-radius: 0px;
            color: {_TEXT};
            text-align: center;
            min-height: 14px;
            font-size: 8pt;
        }}
        QProgressBar::chunk {{ background: {_GREEN}; }}
        QScrollArea {{ border: 0; background: transparent; }}
        QScrollArea > QWidget > QWidget {{ background: transparent; }}
        QScrollBar:vertical {{
            background: {_BG};
            width: 6px; margin: 0;
        }}
        QScrollBar::handle:vertical {{
            background: {_BDR2};
            min-height: 20px;
        }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
        QScrollBar:horizontal {{
            background: {_BG};
            height: 6px; margin: 0;
        }}
        QScrollBar::handle:horizontal {{
            background: {_BDR2};
            min-width: 20px;
        }}
        QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}
        QSplitter::handle:horizontal {{ width: 3px; background: {_BDR2}; }}
        QSplitter::handle:vertical {{ height: 3px; background: {_BDR2}; }}
        QSplitter::handle:hover {{ background: {_GREEN}; }}
        QDockWidget {{ color: {_TEXT}; }}
        QDockWidget::title {{
            background: {_SURF2};
            border: 1px solid {_BDR2};
            padding: 4px 6px;
            text-align: left;
            font-weight: 700;
            font-family: {_FONT};
        }}
    """
