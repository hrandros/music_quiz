from admin_ui.constants import THEME


def build_styles(theme=None):
    theme = theme or THEME
    return f"""
        QWidget {{
            background-color: {theme['bg_body']};
            color: {theme['text']};
            font-family: 'Roboto Condensed', 'Segoe UI';
            font-size: 12px;
        }}
        QLabel#Header {{
            color: {theme['primary']};
            font-family: 'Oswald', 'Segoe UI';
            font-size: 26px;
            letter-spacing: 2px;
        }}
        QFrame#Sidebar {{
            background-color: {theme['surface']};
            border: 1px solid {theme['border']};
            border-radius: 12px;
        }}
        QLabel#SidebarLogo {{
            color: {theme['text']};
            font-family: 'Oswald', 'Segoe UI';
            font-size: 20px;
            letter-spacing: 1px;
        }}
        QListWidget#NavList {{
            background-color: transparent;
            border: none;
        }}
        QListWidget#NavList::item {{
            padding: 10px 12px;
            margin: 2px 0;
            border-radius: 10px;
            color: {theme['muted']};
        }}
        QListWidget#NavList::item:selected {{
            background-color: {theme['surface_alt']};
            color: {theme['text']};
            border: 1px solid {theme['border']};
        }}
        QListWidget#QuestionList {{
            background-color: transparent;
            border: none;
        }}
        QListWidget#QuestionList::item {{
            border: none;
        }}
        QFrame#QuestionCard {{
            background-color: {theme['surface']};
            border: 1px solid {theme['border']};
            border-radius: 10px;
        }}
        QLabel#QuestionTitle {{
            font-size: 13px;
            font-weight: bold;
            color: {theme['text']};
        }}
        QLabel#QuestionMeta {{
            color: {theme['muted']};
        }}
        QLabel#QuestionBadge {{
            background-color: {theme['surface_alt']};
            border: 1px solid {theme['border']};
            border-radius: 8px;
            padding: 6px 8px;
            color: {theme['text']};
        }}
        QLabel#QuestionType {{
            background-color: {theme['bg_hover']};
            border: 1px solid {theme['border']};
            border-radius: 8px;
            padding: 6px 8px;
            color: {theme['muted']};
        }}
        QLabel#SectionTitle {{
            color: {theme['accent']};
            font-family: 'Oswald', 'Segoe UI';
            font-size: 16px;
        }}
        QLabel#StatusLabel {{
            color: {theme['accent']};
            font-weight: bold;
        }}
        QGroupBox {{
            border: 1px solid {theme['border']};
            border-radius: 10px;
            margin-top: 10px;
            padding: 10px;
            background-color: {theme['surface']};
        }}
        QGroupBox::title {{
            subcontrol-origin: margin;
            left: 12px;
            padding: 0 6px;
            color: {theme['accent']};
            font-family: 'Oswald', 'Segoe UI';
        }}
        QLineEdit, QPlainTextEdit, QListWidget, QComboBox, QSpinBox, QDoubleSpinBox {{
            background-color: {theme['surface_alt']};
            border: 1px solid {theme['border']};
            border-radius: 8px;
            padding: 8px;
        }}
        QLineEdit:focus, QPlainTextEdit:focus, QListWidget:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus {{
            border: 1px solid {theme['primary']};
        }}
        QTabWidget::pane {{
            border: 1px solid {theme['border']};
            border-radius: 10px;
        }}
        QTabBar::tab {{
            background: {theme['bg_card']};
            padding: 10px 18px;
            border: 1px solid {theme['border']};
            border-radius: 10px;
            margin-right: 6px;
        }}
        QTabBar::tab:selected {{
            background: {theme['surface_alt']};
            border: 1px solid {theme['primary']};
            color: {theme['text']};
        }}
        QPushButton {{
            background: {theme['primary']};
            border: 1px solid {theme['primary']};
            border-radius: 10px;
            padding: 8px 16px;
            font-family: 'Oswald', 'Segoe UI';
            letter-spacing: 0.5px;
        }}
        QPushButton:hover {{
            background: {theme['primary_hover']};
        }}
        QPushButton:pressed {{
            background: {theme['primary_hover']};
            border: 1px solid {theme['primary_hover']};
        }}
        QPushButton[modeToggle="true"][inactive="true"] {{
            background: {theme['bg_hover']};
            border: 1px solid {theme['border']};
            color: {theme['muted']};
        }}
        QPushButton[modeToggle="true"][inactive="true"]:hover {{
            background: {theme['bg_hover']};
        }}
        QPushButton[modeToggle="true"][inactive="true"]:pressed {{
            background: {theme['surface_alt']};
            border: 1px solid {theme['border']};
        }}
        QPushButton:disabled {{
            background: {theme['bg_hover']};
            border: 1px solid {theme['border']};
            color: {theme['muted']};
        }}
        QToolButton {{
            background: {theme['surface_alt']};
            border: 1px solid {theme['border']};
            border-radius: 10px;
            padding: 8px 12px;
        }}
        QToolButton:hover {{
            border: 1px solid {theme['primary']};
        }}
        QToolButton#QuestionAction {{
            background: {theme['surface_alt']};
            border: 1px solid {theme['border']};
            border-radius: 8px;
            padding: 6px;
        }}
        QToolButton#QuestionAction:hover {{
            border: 1px solid {theme['primary']};
        }}
        QMenu {{
            background-color: {theme['surface']};
            border: 1px solid {theme['border']};
            padding: 6px;
        }}
        QMenu::item {{
            padding: 6px 16px;
            border-radius: 6px;
        }}
        QMenu::item:selected {{
            background-color: {theme['surface_alt']};
        }}
        QTableWidget {{
            background-color: {theme['surface']};
            gridline-color: {theme['border']};
            border-radius: 8px;
        }}
        QHeaderView::section {{
            background-color: {theme['surface_alt']};
            color: {theme['text']};
            padding: 8px;
            border: 1px solid {theme['border']};
        }}
        QScrollBar:vertical {{
            background: transparent;
            width: 10px;
            margin: 4px 2px;
        }}
        QScrollBar::handle:vertical {{
            background: {theme['bg_hover']};
            border-radius: 5px;
            min-height: 24px;
        }}
        QScrollBar::handle:vertical:hover {{
            background: {theme['border']};
        }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
            height: 0px;
        }}
        QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
            background: none;
        }}
        """
