# styles.py
from admin_ui.constants import THEME

def _qss_dark(theme):
    # ROCKQUIZ Classic (tamni) – usklađeno s web screenshotom
    return """
    QWidget {{
        color: {text};
        font-family: 'Roboto Condensed', 'Segoe UI';
        font-size: 14px;
        background: transparent;
    }}
    QMainWindow {{ background: #000000; }}

    QWidget#Root {{
        background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
            stop:0 #6e0000, stop:0.5 #300000, stop:1 #000000);
    }}
    QWidget#Content {{ background: transparent; }}

    /* WATERMARK pozadine za panele */
    QGroupBox[watermark="guitar"]   {{ background-image: url(assets/graphics/watermark_guitar.svg);  background-position: right bottom; background-repeat: no-repeat; }}
    QGroupBox[watermark="skull"]    {{ background-image: url(assets/graphics/watermark_skull.svg);   background-position: right bottom; background-repeat: no-repeat; }}
    QGroupBox[watermark="list"]     {{ background-image: url(assets/graphics/watermark_list.svg);    background-position: right bottom; background-repeat: no-repeat; }}
    QGroupBox[watermark="users"]    {{ background-image: url(assets/graphics/watermark_users.svg);   background-position: right bottom; background-repeat: no-repeat; }}
    QGroupBox[watermark="live"]     {{ background-image: url(assets/graphics/watermark_live.svg);    background-position: right bottom; background-repeat: no-repeat; }}
    QWidget   [watermark="db"]      {{ background-image: url(assets/graphics/watermark_db.svg);      background-position: right bottom; background-repeat: no-repeat; }}

    /* Sidebar */
    QFrame#Sidebar {{
        background: #101010;
        border: 1px solid #2c2c2c;
        border-radius: 6px;
    }}
    QLabel#SidebarLogo {{
        color: #ffffff;
        font-family: 'Oswald';
        font-size: 18px;
        letter-spacing: 2px;
    }}
    QListWidget#NavList {{ background: transparent; border: none; }}
    QListWidget#NavList::item {{
        padding: 12px 14px; margin: 4px 0;
        border-radius: 4px; color: #bbbbbb;
        font-size: 15px; font-weight: 600;
    }}
    QListWidget#NavList::item:hover {{ background:#1e1e1e; color:#ffffff; }}
    QListWidget#NavList::item:selected {{
        background:#400000; color:#ffffff;
        border-left: 3px solid {primary}; margin-left:-3px;
    }}

    /* Top bar */
    QFrame#TopBar {{
        background: #111111;
        border-bottom: 2px solid {primary};
        border-radius: 4px;
    }}
    QLabel#TopBarTitle {{
        color: #ffffff; font-family:'Oswald';
        font-size: 22px; letter-spacing: 2px;
    }}

    /* Headings */
    QLabel#SectionTitle, QLabel#PanelTitle {{
        color:#ffffff; font-family:'Oswald'; font-size:16px; letter-spacing:1px;
    }}

    /* Inputs */
    QLineEdit, QPlainTextEdit, QComboBox, QSpinBox, QDoubleSpinBox {{
        background:#1a1a1a; border:1px solid #333; border-radius:4px; padding:6px 10px; color:#fff;
    }}
    QLineEdit:focus, QPlainTextEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus {{
        border:1px solid {primary}; background:#222;
    }}
    QLineEdit::placeholder, QPlainTextEdit::placeholder {{ color:#777; }}

    /* Buttons: base + variants */
    QPushButton {{
        background:{primary}; border:none; border-radius:4px; padding:7px 16px;
        font-family:'Oswald'; font-weight:bold; color:#ffffff;
    }}
    QPushButton:hover {{ background:{primary_hover}; }}
    QPushButton:pressed {{ background:{primary}; padding-top:8px; padding-bottom:6px; }}
    QPushButton:disabled {{ background:#333; color:#777; }}

    /* Accent variants */
    QPushButton[accent="green"] {{ background:#0fa040; color:#fff; }}
    QPushButton[accent="green"]:hover {{ background:#11b749; }}
    QPushButton[accent="blue"] {{ background:#2563eb; color:#fff; }}
    QPushButton[accent="blue"]:hover {{ background:#1e4fd6; }}
    QPushButton[accent="danger"] {{ background:#b91c1c; color:#fff; }}
    QPushButton[accent="danger"]:hover {{ background:#dc2626; }}

    /* Outline variant */
    QPushButton[variant="outline"] {{
        background: transparent; color:#ffffff;
        border:1px solid #444; border-radius:4px; padding:6px 14px;
    }}
    QPushButton[variant="outline"]:hover {{ border-color:{primary}; }}

    /* Size variants */
    QPushButton[size="sm"] {{ padding:6px 10px; border-radius:4px; }}
    QPushButton[size="lg"] {{ padding:10px 20px; border-radius:6px; }}

    /* Badges & chips */
    QLabel[badge="yellow"] {{
        background:#f0b90b; color:#000; border-radius:4px; padding:2px 6px; font-weight:800;
    }}
    QLabel[badge="cyan"] {{
        background:#27b8e9; color:#000; border-radius:4px; padding:2px 6px; font-weight:bold;
    }}
    QLabel[chip="status"] {{
        background:#1a1a1a; color:#e5e7eb; border:1px solid #333; border-radius:999px; padding:2px 10px;
        font-weight:700;
    }}
    QLabel[chip="status"][state="ok"] {{ color:#10b981; border-color:#14532d; }}
    QLabel[chip="status"][state="warn"] {{ color:#f59e0b; border-color:#7c2d12; }}
    QLabel[chip="status"][state="err"] {{ color:#ef4444; border-color:#7f1d1d; }}

    /* ToolButton */
    QToolButton {{
        background:#1a1a1a; border:1px solid #333; border-radius:4px; padding:6px; color:#fff;
    }}
    QToolButton:hover {{ border-color:{primary}; background:#222; }}

    /* Cards / panels */
    QGroupBox, QWidget[panel="true"] {{
        background:#0d0d0d; border:1px solid #222; border-radius:4px; padding:16px; margin-top:16px;
    }}
    QGroupBox::title {{
        subcontrol-origin: margin; left: 12px; padding: 0 6px;
        color:#fff; font-family:'Oswald'; background:#0d0d0d;
    }}

    /* Table */
    QTableWidget {{
        background:#000; border:1px solid #222; border-radius:4px; gridline-color:#333;
    }}
    QTableWidget::item {{ padding:8px 10px; background:#0d0d0d; color:#fff; }}
    QTableWidget::item:selected {{ background:#400000; border:none; }}
    QHeaderView::section {{
        background:#111; padding:8px; border:1px solid #333; color:#fff; font-weight:bold;
    }}

    /* Scrollbar */
    QScrollBar:vertical {{ background:#111; width:10px; margin:4px; }}
    QScrollBar::handle:vertical {{ background:#444; border-radius:4px; min-height:24px; }}
    QScrollBar::handle:vertical:hover {{ background:#666; }}

    /* Live questions list */
    QListWidget#LiveQuestionList::item {{
        background:#0d0d0d; border:1px solid #222; border-radius:4px; padding:8px 12px; margin:4px 0; color:#fff;
    }}
    QListWidget#LiveQuestionList::item[selected="true"], QListWidget#LiveQuestionList::item:selected {{
        background:#400000; border:1px solid {primary};
    }}

    /* Tabs */
    QTabWidget::pane {{ border:1px solid #333; border-radius:4px; background:#0d0d0d; }}
    QTabBar::tab {{
        background:#1a1a1a; padding:8px 14px; border:1px solid #333; border-radius:4px;
    }}
    QTabBar::tab:selected {{
        background:#400000; border:1px solid {primary}; color:#fff;
    }}
    """.format(
        text=theme.get('text', '#eaeaea'),
        primary=theme.get('primary', '#e4252c'),
        primary_hover=theme.get('primary_hover', '#ff4248'),
    )


def _qss_light(theme):
    # Modern Light – web dashboard look (čist, čitljiv)
    return """
    QWidget {{
        color: #1b1f24;
        font-family: 'Roboto Condensed', 'Segoe UI';
        font-size: 14px;
        background: transparent;
    }}
    QMainWindow {{ background: #f6f7f9; }}

    QWidget#Root {{ background: #f6f7f9; }}
    QWidget#Content {{ background: transparent; }}

    /* WATERMARK pozadine za panele */
    QGroupBox[watermark="guitar"]   {{ background-image: url(assets/graphics/watermark_guitar.svg);  background-position: right bottom; background-repeat: no-repeat; }}
    QGroupBox[watermark="skull"]    {{ background-image: url(assets/graphics/watermark_skull.svg);   background-position: right bottom; background-repeat: no-repeat; }}
    QGroupBox[watermark="list"]     {{ background-image: url(assets/graphics/watermark_list.svg);    background-position: right bottom; background-repeat: no-repeat; }}
    QGroupBox[watermark="users"]    {{ background-image: url(assets/graphics/watermark_users.svg);   background-position: right bottom; background-repeat: no-repeat; }}
    QGroupBox[watermark="live"]     {{ background-image: url(assets/graphics/watermark_live.svg);    background-position: right bottom; background-repeat: no-repeat; }}
    QWidget   [watermark="db"]      {{ background-image: url(assets/graphics/watermark_db.svg);      background-position: right bottom; background-repeat: no-repeat; }}

    /* Top bar s burgundy gradijentom (brand) */
    QFrame#TopBar {{
        background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
            stop:0 #861313, stop:1 #2d0b0b);
        border: 0px; border-radius: 12px;
    }}
    QLabel#TopBarTitle {{ color:#ffffff; font-family:'Oswald'; font-size:22px; letter-spacing:2px; }}

    /* Sidebar (tamni, kontrast u light modu) */
    QFrame#Sidebar {{
        background: #111418;
        border: 0px;
        border-radius: 10px;
    }}
    QLabel#SidebarLogo {{ color:#ffffff; font-family:'Oswald'; font-size:20px; letter-spacing:2px; }}
    QListWidget#NavList {{ background: transparent; border: none; }}
    QListWidget#NavList::item {{
        padding: 12px 14px; margin: 6px 0;
        border-radius: 8px; color: #c9d1d9; font-size: 15px; font-weight: 600;
    }}
    QListWidget#NavList::item:hover {{ background:#1d232b; color:#ffffff; }}
    QListWidget#NavList::item:selected {{
        background:#2c3340; color:#ffffff; border-left:3px solid {primary}; margin-left:-3px;
    }}

    /* Cards / panels */
    QGroupBox, QWidget[panel="true"] {{
        background: #ffffff;
        border: 1px solid #e5e7eb;
        border-radius: 12px;
        padding: 16px; margin-top: 16px;
    }}
    QGroupBox::title {{
        subcontrol-origin: margin; left: 12px; padding: 0 6px;
        color: #111418; font-family: 'Oswald'; background: #ffffff;
    }}
    QLabel#SectionTitle, QLabel#PanelTitle {{
        color:#111418; font-family:'Oswald'; font-size:16px; letter-spacing:0.5px;
    }}

    /* Inputs */
    QLineEdit, QPlainTextEdit, QComboBox, QSpinBox, QDoubleSpinBox {{
        background: #ffffff;
        border: 1px solid #d0d7de;
        border-radius: 8px;
        padding: 8px 12px;
        color: #111418;
    }}
    QLineEdit:focus, QPlainTextEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus {{
        border: 1px solid {primary};
        background: #ffffff;
    }}
    QLineEdit::placeholder, QPlainTextEdit::placeholder {{ color: #8b949e; }}

    /* Buttons */
    QPushButton {{
        background: {primary};
        border: none; border-radius: 8px;
        padding: 8px 18px;
        font-family: 'Oswald'; font-weight: 700; color: #ffffff;
    }}
    QPushButton:hover {{ background: {primary_hover}; }}
    QPushButton:disabled {{ background: #e5e7eb; color: #9aa0a6; }}

    /* Variants */
    QPushButton[accent="green"] {{ background:#12b76a; color:#fff; }}
    QPushButton[accent="green"]:hover {{ background:#16cf78; }}
    QPushButton[accent="blue"] {{ background:#2563eb; color:#fff; }}
    QPushButton[accent="blue"]:hover {{ background:#1e4fd6; }}
    QPushButton[accent="danger"] {{ background:#dc2626; color:#fff; }}
    QPushButton[accent="danger"]:hover {{ background:#ef4444; }}

    QPushButton[variant="outline"] {{
        background:#ffffff; color:#111418; border:1px solid #d0d7de; border-radius:8px; padding:8px 16px;
    }}
    QPushButton[variant="outline"]:hover {{
        border-color:{primary}; color:#111418;
    }}
    QPushButton[size="sm"] {{ padding:6px 10px; border-radius:6px; }}
    QPushButton[size="lg"] {{ padding:10px 20px; border-radius:10px; }}

    /* Chips */
    QLabel[chip="status"] {{
        background:#f8fafc; color:#0f172a; border:1px solid #e2e8f0; border-radius:999px; padding:2px 10px; font-weight:700;
    }}
    QLabel[chip="status"][state="ok"] {{ color:#047857; border-color:#99f6e4; }}
    QLabel[chip="status"][state="warn"] {{ color:#92400e; border-color:#fde68a; }}
    QLabel[chip="status"][state="err"] {{ color:#991b1b; border-color:#fecaca; }}

    /* ToolButton */
    QToolButton {{
        background: #ffffff; border: 1px solid #d0d7de; border-radius: 8px; padding: 6px 10px; color: #111418;
    }}
    QToolButton:hover {{ border-color: {primary}; background:#ffffff; }}

    /* Table */
    QTableWidget {{
        background: #ffffff; border-radius: 12px; border: 1px solid #e5e7eb; gridline-color:#eef2f7;
    }}
    QTableWidget::item {{ padding: 10px 12px; background:#ffffff; color:#111418; }}
    QTableWidget::item:selected {{ background:#ffe4e4; border:none; }}
    QHeaderView::section {{
        background:#f3f4f6; padding:10px; border:1px solid #e5e7eb; color:#111418; font-weight:700;
    }}

    /* Scrollbar */
    QScrollBar:vertical {{ background: transparent; width: 10px; margin: 4px; }}
    QScrollBar::handle:vertical {{ background:#cdd5df; border-radius: 6px; min-height:24px; }}
    QScrollBar::handle:vertical:hover {{ background:#b7c2d0; }}

    /* Live list */
    QListWidget#LiveQuestionList::item {{
        background:#ffffff; border:1px solid #e5e7eb; border-radius: 12px; padding:10px 12px; margin:6px 0; color:#111418;
    }}
    QListWidget#LiveQuestionList::item[selected="true"], QListWidget#LiveQuestionList::item:selected {{
        background:#ffe4e4; border:1px solid {primary};
    }}

    /* Tabs */
    QTabWidget::pane {{ border:1px solid #e5e7eb; border-radius:12px; background:#ffffff; }}
    QTabBar::tab {{
        background:#f3f4f6; padding:8px 14px; border:1px solid #e5e7eb; border-radius:999px; margin: 4px;
    }}
    QTabBar::tab:selected {{
        background:#ffffff; border:1px solid {primary}; color:#111418;
    }}
    """.format(
        primary=theme.get('primary', '#e4252c'),
        primary_hover=theme.get('primary_hover', '#ff4248'),
    )


def build_styles(theme=None, mode="dark"):
    """
    Vrati QSS za zadani mode: "dark" ili "light".
    """
    theme = theme or THEME
    if str(mode).lower() == "light":
        return _qss_light(theme)
    return _qss_dark(theme)