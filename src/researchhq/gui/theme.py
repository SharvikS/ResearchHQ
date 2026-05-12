"""Dark theme stylesheet for ResearchHQ Studio.

Designed to read like a SaaS workstation: dark background, soft cards,
clear accent for primary actions, subdued accent for navigation.
"""

PALETTE = {
    "bg":          "#0e1116",
    "bg_alt":      "#151a22",
    "panel":       "#1a212c",
    "panel_2":     "#212a36",
    "border":      "#262f3d",
    "text":        "#e6ecf3",
    "text_muted":  "#8a96a8",
    "accent":      "#5e8bff",
    "accent_2":    "#3f6cf2",
    "accent_dim":  "#2a3d70",
    "ok":          "#3ecf8e",
    "warn":        "#f4b740",
    "err":         "#ef5b5b",
    "bg_input":    "#0f141c",
}


DARK_QSS = """
QWidget {{
    background-color: {bg};
    color: {text};
    font-family: "Segoe UI", "Inter", "SF Pro Text", system-ui, sans-serif;
    font-size: 13px;
}}

QMainWindow {{ background-color: {bg}; }}

/* ---------- Sidebar ---------- */
#Sidebar {{
    background-color: {bg_alt};
    border-right: 1px solid {border};
}}
#Sidebar QPushButton {{
    text-align: left;
    padding: 10px 16px;
    background-color: transparent;
    border: none;
    border-radius: 8px;
    color: {text_muted};
    font-size: 13px;
}}
#Sidebar QPushButton:hover {{
    background-color: {panel};
    color: {text};
}}
#Sidebar QPushButton[active="true"] {{
    background-color: {accent_dim};
    color: {text};
    font-weight: 600;
}}
#SidebarBrand {{
    color: {text};
    font-size: 16px;
    font-weight: 700;
    padding: 18px 16px 6px 16px;
    background-color: transparent;
}}
#SidebarBrandSub {{
    color: {text_muted};
    font-size: 11px;
    padding: 0 16px 16px 16px;
    background-color: transparent;
}}

/* ---------- Cards ---------- */
#Card {{
    background-color: {panel};
    border: 1px solid {border};
    border-radius: 12px;
}}
#CardTitle {{
    color: {text};
    font-size: 13px;
    font-weight: 600;
    background-color: transparent;
}}
#CardSubtitle {{
    color: {text_muted};
    font-size: 12px;
    background-color: transparent;
}}
#StatValue {{
    color: {text};
    font-size: 22px;
    font-weight: 700;
    background-color: transparent;
}}
#StatLabel {{
    color: {text_muted};
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    background-color: transparent;
}}

/* ---------- Inputs ---------- */
QLineEdit, QPlainTextEdit, QTextEdit {{
    background-color: {bg_input};
    border: 1px solid {border};
    border-radius: 8px;
    padding: 8px 10px;
    color: {text};
    selection-background-color: {accent_dim};
}}
QLineEdit:focus, QPlainTextEdit:focus, QTextEdit:focus {{
    border: 1px solid {accent};
}}

QComboBox, QSpinBox {{
    background-color: {bg_input};
    border: 1px solid {border};
    border-radius: 8px;
    padding: 6px 10px;
    color: {text};
    min-width: 80px;
}}
QComboBox:focus, QSpinBox:focus {{ border: 1px solid {accent}; }}
QComboBox QAbstractItemView {{
    background-color: {panel};
    border: 1px solid {border};
    selection-background-color: {accent_dim};
    color: {text};
}}

/* ---------- Buttons ---------- */
QPushButton {{
    background-color: {panel_2};
    color: {text};
    border: 1px solid {border};
    border-radius: 8px;
    padding: 8px 16px;
    font-weight: 500;
}}
QPushButton:hover {{ background-color: {panel}; border-color: {accent}; }}
QPushButton:pressed {{ background-color: {accent_dim}; }}
QPushButton:disabled {{ color: {text_muted}; background-color: {panel}; border-color: {border}; }}

QPushButton#Primary {{
    background-color: {accent};
    border: 1px solid {accent};
    color: white;
}}
QPushButton#Primary:hover {{ background-color: {accent_2}; border-color: {accent_2}; }}
QPushButton#Primary:disabled {{ background-color: {accent_dim}; border-color: {accent_dim}; color: {text_muted}; }}
QPushButton#Danger {{
    background-color: transparent;
    border: 1px solid {err};
    color: {err};
}}
QPushButton#Danger:hover {{ background-color: rgba(239, 91, 91, 0.12); }}

/* ---------- Pipeline status ---------- */
#StageChip {{
    background-color: {panel_2};
    border: 1px solid {border};
    border-radius: 999px;
    padding: 6px 12px;
    color: {text_muted};
    font-size: 12px;
}}
#StageChip[state="running"] {{
    border-color: {accent};
    color: {accent};
    background-color: rgba(94, 139, 255, 0.10);
}}
#StageChip[state="done"] {{
    border-color: {ok};
    color: {ok};
    background-color: rgba(62, 207, 142, 0.10);
}}
#StageChip[state="failed"] {{
    border-color: {err};
    color: {err};
    background-color: rgba(239, 91, 91, 0.12);
}}

/* ---------- Tables ---------- */
QTableView, QTableWidget {{
    background-color: {panel};
    alternate-background-color: {panel_2};
    gridline-color: {border};
    border: 1px solid {border};
    border-radius: 8px;
    selection-background-color: {accent_dim};
    selection-color: {text};
}}
QHeaderView::section {{
    background-color: {bg_alt};
    color: {text_muted};
    border: none;
    border-bottom: 1px solid {border};
    padding: 8px;
    font-weight: 600;
}}
QListWidget {{
    background-color: {panel};
    border: 1px solid {border};
    border-radius: 8px;
}}
QListWidget::item {{ padding: 8px; border-bottom: 1px solid {border}; }}
QListWidget::item:selected {{ background-color: {accent_dim}; color: {text}; }}

/* ---------- Tabs ---------- */
QTabWidget::pane {{
    border: 1px solid {border};
    border-radius: 8px;
    top: -1px;
    background-color: {panel};
}}
QTabBar::tab {{
    background-color: transparent;
    color: {text_muted};
    padding: 8px 14px;
    border: 1px solid transparent;
    border-bottom: none;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    margin-right: 2px;
}}
QTabBar::tab:selected {{
    background-color: {panel};
    color: {text};
    border: 1px solid {border};
    border-bottom: none;
}}
QTabBar::tab:hover:!selected {{ color: {text}; }}

/* ---------- Misc ---------- */
QScrollBar:vertical {{
    background: transparent; width: 10px;
}}
QScrollBar::handle:vertical {{
    background: {border}; border-radius: 5px; min-height: 20px;
}}
QScrollBar::handle:vertical:hover {{ background: {text_muted}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; }}
QScrollBar::handle:horizontal {{ background: {border}; border-radius: 5px; min-width: 20px; }}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}

QToolTip {{
    background-color: {panel_2};
    border: 1px solid {border};
    color: {text};
    padding: 6px 8px;
    border-radius: 6px;
}}

#Toast {{
    background-color: {err};
    color: white;
    border-radius: 8px;
    padding: 10px 14px;
    font-weight: 600;
}}
""".format(**PALETTE)
