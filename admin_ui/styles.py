from admin_ui.constants import THEME


def build_styles(theme=None):
    theme = theme or THEME
    return f"""
        QWidget {{
            color: {theme['text']};
            font-family: 'Roboto Condensed', 'Segoe UI';
            font-size: 14px;
        }}
        QMainWindow {{
            background: {theme['bg_body']};
        }}
        QWidget#Root {{
            background: qlineargradient(
                x1: 0, y1: 0, x2: 0, y2: 1,
                stop: 0 {theme['bg_gradient_top']},
                stop: 1 {theme['bg_gradient_bottom']}
            );
            background-image: url(assets/graphics/rock_pattern.svg);
            background-position: center;
            background-repeat: repeat;
        }}
        QWidget#Content {{
            background: transparent;
        }}
        QStackedWidget {{
            background: transparent;
        }}
        QStackedWidget > QWidget {{
            background-color: rgba(21, 23, 27, 0.95);
            border: 1px solid {theme['border']};
            border-radius: 10px;
        }}
        QLabel#PanelTitle {{
            color: {theme['text']};
            font-family: 'Oswald', 'Segoe UI';
            font-size: 16px;
            letter-spacing: 1.2px;
        }}
        QLabel#PanelIcon {{
            min-width: 18px;
        }}
        QLabel[badge="cyan"] {{
            background-color: rgba(39, 184, 233, 0.2);
            border: 1px solid {theme['accent_cyan']};
            border-radius: 6px;
            padding: 4px 8px;
            color: {theme['accent_cyan']};
            font-weight: bold;
        }}
        QLabel[badge="yellow"] {{
            background-color: rgba(240, 185, 11, 0.2);
            border: 1px solid {theme['accent_yellow']};
            border-radius: 6px;
            padding: 4px 8px;
            color: {theme['accent_yellow']};
            font-weight: bold;
        }}
        QLabel[badge="red"] {{
            background-color: rgba(228, 37, 44, 0.2);
            border: 1px solid {theme['primary']};
            border-radius: 6px;
            padding: 4px 8px;
            color: {theme['primary']};
            font-weight: bold;
        }}
        QFrame#TopBar {{
            background-color: rgba(10, 10, 12, 0.95);
            border: 1px solid {theme['border']};
            border-bottom: 2px solid {theme['primary']};
            border-radius: 8px;
        }}
        QLabel#TopBarTitle {{
            color: {theme['text']};
            font-family: 'Oswald', 'Segoe UI';
            font-size: 20px;
            letter-spacing: 2px;
        }}
        QLabel#TopBarLogo {{
            padding-right: 2px;
        }}
        QLabel#SidebarLogoIcon {{
            padding-top: 2px;
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
            border-radius: 10px;
        }}
        QLabel#SidebarLogo {{
            color: {theme['text']};
            font-family: 'Oswald', 'Segoe UI';
            font-size: 18px;
            letter-spacing: 1.5px;
        }}
        QListWidget#NavList {{
            background-color: transparent;
            border: none;
        }}
        QListWidget#NavList::item {{
            padding: 12px 14px;
            margin: 4px 0;
            border-radius: 8px;
            color: {theme['muted']};
        }}
        QListWidget#NavList::item:hover {{
            background-color: {theme['bg_hover']};
            color: {theme['text']};
        }}
        QListWidget#NavList::item:selected {{
            background-color: {theme['bg_card']};
            color: {theme['text']};
            border: 1px solid {theme['primary']};
        }}
        QListWidget#QuestionList {{
            background-color: transparent;
            border: none;
        }}
        QListWidget#QuestionList::item {{
            border: none;
        }}
        QListWidget#LiveQuestionList {{
            background-color: transparent;
            border: none;
        }}
        QListWidget#LiveQuestionList::item {{
            padding: 8px 10px;
            margin: 4px 0;
            border-radius: 8px;
            background-color: {theme['bg_card']};
            border: 1px solid {theme['border']};
        }}
        QListWidget#LiveQuestionList::item:selected {{
            border: 1px solid {theme['primary']};
            background-color: {theme['surface_alt']};
        }}
        QFrame#QuestionCard {{
            background-color: {theme['bg_card']};
            border: 1px solid {theme['border']};
            border-radius: 10px;
            background-image: url(assets/graphics/grunge_overlay.svg);
            background-position: center;
            background-repeat: repeat;
        }}
        QLabel#QuestionTitle {{
            font-size: 14px;
            font-weight: bold;
            color: {theme['text']};
        }}
        QLabel#QuestionMeta {{
            color: {theme['muted']};
        }}
        QLabel#QuestionBadge {{
            background-color: {theme['bg_hover']};
            border: 1px solid {theme['border']};
            border-radius: 8px;
            padding: 6px 10px;
            color: {theme['text']};
        }}
        QLabel#QuestionType {{
            background-color: {theme['surface_alt']};
            border: 1px solid {theme['border']};
            border-radius: 8px;
            padding: 6px 10px;
            color: {theme['accent_yellow']};
        }}
        QLabel#SectionTitle {{
            color: {theme['text']};
            font-family: 'Oswald', 'Segoe UI';
            font-size: 16px;
            letter-spacing: 1px;
        }}
        QLabel#StatusLabel {{
            color: {theme['accent']};
            font-weight: bold;
        }}
        QGroupBox {{
            border: 1px solid {theme['border']};
            border-radius: 10px;
            margin-top: 16px;
            padding: 14px;
            background-color: {theme['bg_card']};
        }}
                QGroupBox[watermark="guitar"] {{
                    background-image: url(assets/graphics/watermark_guitar.svg);
                    background-position: right bottom;
                    background-repeat: no-repeat;
                }}
                QGroupBox[watermark="skull"] {{
                    background-image: url(assets/graphics/watermark_skull.svg);
                    background-position: right bottom;
                    background-repeat: no-repeat;
                }}
                QGroupBox[watermark="list"] {{
                    background-image: url(assets/graphics/watermark_list.svg);
                    background-position: right bottom;
                    background-repeat: no-repeat;
                }}
                QGroupBox[watermark="users"] {{
                    background-image: url(assets/graphics/watermark_users.svg);
                    background-position: right bottom;
                    background-repeat: no-repeat;
                }}
                QGroupBox[watermark="live"] {{
                    background-image: url(assets/graphics/watermark_live.svg);
                    background-position: right bottom;
                    background-repeat: no-repeat;
                }}
                QWidget[watermark="db"] {{
                    background-image: url(assets/graphics/watermark_db.svg);
                    background-position: right bottom;
                    background-repeat: no-repeat;
                }}
        QGroupBox::title {{
            subcontrol-origin: margin;
            left: 12px;
            padding: 0 6px;
            color: {theme['text']};
            font-family: 'Oswald', 'Segoe UI';
            background-color: {theme['bg_card']};
        }}
        QGroupBox[panel="true"]::title {{
            color: transparent;
            padding: 0;
        }}
        QLineEdit, QPlainTextEdit, QListWidget, QComboBox, QSpinBox, QDoubleSpinBox {{
            background-color: {theme['surface_alt']};
            border: 1px solid {theme['border']};
            border-radius: 6px;
            padding: 8px 10px;
        }}
        QLineEdit:focus, QPlainTextEdit:focus, QListWidget:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus {{
            border: 1px solid {theme['primary']};
        }}
        QLineEdit::placeholder, QPlainTextEdit::placeholder {{
            color: {theme['muted']};
        }}
        QTabWidget::pane {{
            border: 1px solid {theme['border']};
            border-radius: 10px;
        }}
        QTabBar::tab {{
            background: {theme['bg_card']};
            padding: 8px 16px;
            border: 1px solid {theme['border']};
            border-radius: 6px;
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
            border-radius: 6px;
            padding: 8px 16px;
            font-family: 'Oswald', 'Segoe UI';
            letter-spacing: 0.8px;
            text-transform: uppercase;
        }}
        QPushButton:hover {{
            background: {theme['primary_hover']};
        }}
        QPushButton:pressed {{
            background: {theme['primary']};
            border: 1px solid {theme['primary_hover']};
        }}
        QPushButton[modeToggle="true"][inactive="true"] {{
            background: {theme['bg_card']};
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
            border-radius: 6px;
            padding: 6px 10px;
        }}
        QToolButton:hover {{
            border: 1px solid {theme['primary']};
        }}
        QToolButton#QuestionAction {{
            background: {theme['surface_alt']};
            border: 1px solid {theme['border']};
            border-radius: 6px;
            padding: 6px;
        }}
        QToolButton#QuestionAction:hover {{
            border: 1px solid {theme['primary']};
        }}
        QMenu {{
            background-color: {theme['surface']};
            border: 1px solid {theme['border']};
            border-radius: 6px;
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
            background-color: {theme['bg_card']};
            gridline-color: {theme['border']};
            border-radius: 8px;
        }}
        QTableWidget::item {{
            padding: 6px 8px;
        }}
        QTableWidget::item:selected {{
            background-color: rgba(228, 37, 44, 0.25);
        }}
        QHeaderView::section {{
            background-color: {theme['surface_alt']};
            color: {theme['text']};
            padding: 8px;
            border: 1px solid {theme['border']};
        }}
        QSplitter::handle {{
            background-color: {theme['border']};
            width: 2px;
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
