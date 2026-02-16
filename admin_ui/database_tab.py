from PySide6 import QtCore, QtWidgets

from musicquiz.models import (
    Answer,
    LogEntry,
    Player,
    PlayerQuiz,
    Question,
    Quiz,
    SimultaneousQuestion,
    Song,
    TextMultiple,
    TextQuestion,
    Video,
)


class DatabaseTabMixin:
    def _build_database_tab(self):
        layout = QtWidgets.QVBoxLayout(self.tab_database)

        header = QtWidgets.QHBoxLayout()
        layout.addLayout(header)

        header.addWidget(QtWidgets.QLabel("Table:"))
        self.db_table_combo = QtWidgets.QComboBox()
        self.db_table_combo.currentIndexChanged.connect(self.refresh_database_table)
        header.addWidget(self.db_table_combo)

        header.addSpacing(12)
        header.addWidget(QtWidgets.QLabel("Limit:"))
        self.db_limit_spin = QtWidgets.QSpinBox()
        self.db_limit_spin.setRange(10, 5000)
        self.db_limit_spin.setSingleStep(50)
        self.db_limit_spin.setValue(500)
        header.addWidget(self.db_limit_spin)

        refresh_btn = QtWidgets.QPushButton("Refresh")
        refresh_btn.clicked.connect(self.refresh_database_table)
        header.addWidget(refresh_btn)
        header.addStretch(1)

        self.db_info_label = QtWidgets.QLabel("Rows: 0")
        self.db_info_label.setObjectName("StatusLabel")
        header.addWidget(self.db_info_label)

        filter_row = QtWidgets.QHBoxLayout()
        layout.addLayout(filter_row)
        filter_row.addWidget(QtWidgets.QLabel("Filter all:"))
        self.db_filter_all = QtWidgets.QLineEdit()
        self.db_filter_all.setPlaceholderText("Search in all columns...")
        self.db_filter_all.textChanged.connect(self.apply_database_filter)
        filter_row.addWidget(self.db_filter_all, 2)

        filter_row.addSpacing(12)
        filter_row.addWidget(QtWidgets.QLabel("Column:"))
        self.db_filter_column = QtWidgets.QComboBox()
        self.db_filter_column.addItem("All columns")
        self.db_filter_column.currentIndexChanged.connect(self.apply_database_filter)
        filter_row.addWidget(self.db_filter_column)

        self.db_filter_value = QtWidgets.QLineEdit()
        self.db_filter_value.setPlaceholderText("Contains...")
        self.db_filter_value.textChanged.connect(self.apply_database_filter)
        filter_row.addWidget(self.db_filter_value, 2)

        self.db_table = QtWidgets.QTableWidget(0, 0)
        self.db_table.horizontalHeader().setStretchLastSection(True)
        self.db_table.horizontalHeader().setSortIndicatorShown(True)
        self.db_table.horizontalHeader().setSectionsClickable(True)
        self.db_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.db_table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.db_table.setWordWrap(False)
        self.db_table.setSortingEnabled(True)
        layout.addWidget(self.db_table, 1)

        self._db_models = {
            "Quiz": Quiz,
            "Question": Question,
            "Song": Song,
            "Video": Video,
            "TextQuestion": TextQuestion,
            "TextMultiple": TextMultiple,
            "SimultaneousQuestion": SimultaneousQuestion,
            "Player": Player,
            "PlayerQuiz": PlayerQuiz,
            "Answer": Answer,
            "LogEntry": LogEntry,
        }

        self.db_table_combo.addItems(list(self._db_models.keys()))
        self.refresh_database_table()

    def refresh_database_table(self):
        if not hasattr(self, "db_table_combo") or not hasattr(self, "db_table"):
            return
        model_name = self.db_table_combo.currentText()
        model = self._db_models.get(model_name)
        if not model:
            return
        limit = int(self.db_limit_spin.value()) if hasattr(self, "db_limit_spin") else 500

        def _fetch():
            columns = [column.name for column in model.__table__.columns]
            query = model.query
            id_column = getattr(model, "id", None)
            if id_column is None and "id" in model.__table__.c:
                id_column = model.__table__.c["id"]
            if id_column is not None:
                query = query.order_by(id_column.desc())
            rows = query.limit(limit).all()
            return columns, rows

        columns, rows = self.with_app(_fetch)

        self.db_columns = list(columns)
        self.db_id_column_index = self.db_columns.index("id") if "id" in self.db_columns else None
        self._db_force_default_sort = True
        self.db_rows_data = []
        for row_obj in rows:
            row_values = [getattr(row_obj, col_name, "") for col_name in self.db_columns]
            self.db_rows_data.append(row_values)

        current_column = self.db_filter_column.currentText() if hasattr(self, "db_filter_column") else "All columns"
        self.db_filter_column.blockSignals(True)
        self.db_filter_column.clear()
        self.db_filter_column.addItem("All columns")
        self.db_filter_column.addItems(self.db_columns)
        idx = self.db_filter_column.findText(current_column)
        self.db_filter_column.setCurrentIndex(idx if idx >= 0 else 0)
        self.db_filter_column.blockSignals(False)

        self.apply_database_filter()

    def apply_database_filter(self):
        columns = getattr(self, "db_columns", [])
        rows_data = getattr(self, "db_rows_data", [])
        if not hasattr(self, "db_table"):
            return

        text_filter_all = self.db_filter_all.text().strip().lower() if hasattr(self, "db_filter_all") else ""
        selected_column = self.db_filter_column.currentText() if hasattr(self, "db_filter_column") else "All columns"
        text_filter_col = self.db_filter_value.text().strip().lower() if hasattr(self, "db_filter_value") else ""

        column_index = -1
        if selected_column and selected_column != "All columns" and selected_column in columns:
            column_index = columns.index(selected_column)

        header = self.db_table.horizontalHeader()
        current_sort_col = header.sortIndicatorSection()
        current_sort_order = header.sortIndicatorOrder()

        self.db_table.setSortingEnabled(False)
        self.db_table.setRowCount(0)
        self.db_table.setColumnCount(len(columns))
        self.db_table.setHorizontalHeaderLabels(columns)

        visible_count = 0
        for row_values in rows_data:
            text_values = [str(value) for value in row_values]
            lower_values = [value.lower() for value in text_values]

            if text_filter_all and not any(text_filter_all in value for value in lower_values):
                continue
            if column_index >= 0 and text_filter_col:
                if text_filter_col not in lower_values[column_index]:
                    continue
            elif column_index < 0 and text_filter_col:
                if not any(text_filter_col in value for value in lower_values):
                    continue

            table_row = self.db_table.rowCount()
            self.db_table.insertRow(table_row)
            for col_idx, value in enumerate(text_values):
                self.db_table.setItem(table_row, col_idx, QtWidgets.QTableWidgetItem(value))
            visible_count += 1

        self.db_table.setSortingEnabled(True)
        if getattr(self, "_db_force_default_sort", False):
            id_col = getattr(self, "db_id_column_index", None)
            if id_col is not None and 0 <= id_col < len(columns):
                self.db_table.sortItems(id_col, QtCore.Qt.DescendingOrder)
                header.setSortIndicator(id_col, QtCore.Qt.DescendingOrder)
            self._db_force_default_sort = False
        elif 0 <= current_sort_col < len(columns):
            self.db_table.sortItems(current_sort_col, current_sort_order)

        if hasattr(self, "db_info_label"):
            total_count = len(rows_data)
            self.db_info_label.setText(f"Rows: {visible_count}/{total_count}")
