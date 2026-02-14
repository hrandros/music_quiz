from PySide6 import QtWidgets

from musicquiz.models import LogEntry


class LogsTabMixin:
    def _build_logs_tab(self):
        layout = QtWidgets.QVBoxLayout(self.tab_logs)
        header = QtWidgets.QHBoxLayout()
        layout.addLayout(header)

        title = QtWidgets.QLabel("LOGS")
        title.setObjectName("SectionTitle")
        header.addWidget(title)

        header.addStretch(1)
        refresh_btn = QtWidgets.QPushButton("Refresh")
        refresh_btn.clicked.connect(self.refresh_logs)
        header.addWidget(refresh_btn)

        filter_row = QtWidgets.QHBoxLayout()
        filter_row.addWidget(QtWidgets.QLabel("Filter:"))
        self.logs_filter_time = QtWidgets.QLineEdit()
        self.logs_filter_time.setPlaceholderText("Time")
        self.logs_filter_time.textChanged.connect(self.apply_logs_filter)
        filter_row.addWidget(self.logs_filter_time)
        self.logs_filter_source = QtWidgets.QLineEdit()
        self.logs_filter_source.setPlaceholderText("Source")
        self.logs_filter_source.textChanged.connect(self.apply_logs_filter)
        filter_row.addWidget(self.logs_filter_source)
        self.logs_filter_message = QtWidgets.QLineEdit()
        self.logs_filter_message.setPlaceholderText("Message")
        self.logs_filter_message.textChanged.connect(self.apply_logs_filter)
        filter_row.addWidget(self.logs_filter_message)
        layout.addLayout(filter_row)

        self.logs_table = QtWidgets.QTableWidget(0, 3)
        self.logs_table.setHorizontalHeaderLabels(["Time", "Source", "Message"])
        self.logs_table.setColumnWidth(0, 170)
        self.logs_table.horizontalHeader().setStretchLastSection(True)
        self.logs_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.logs_table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        layout.addWidget(self.logs_table, 1)

        self.refresh_logs()

    def refresh_logs(self):
        def _fetch():
            return LogEntry.query.order_by(LogEntry.created_at.desc()).limit(1000).all()

        self.logs_rows = self.with_app(_fetch)
        self.apply_logs_filter()

    def apply_logs_filter(self):
        if not hasattr(self, "logs_table"):
            return
        rows = getattr(self, "logs_rows", [])
        time_filter = self.logs_filter_time.text().strip().lower()
        source_filter = self.logs_filter_source.text().strip().lower()
        message_filter = self.logs_filter_message.text().strip().lower()

        self.logs_table.setRowCount(0)
        for entry in rows:
            time_text = entry.created_at.strftime("%Y-%m-%d %H:%M:%S")
            source_text = str(entry.source)
            message_text = str(entry.message)
            if time_filter and time_filter not in time_text.lower():
                continue
            if source_filter and source_filter not in source_text.lower():
                continue
            if message_filter and message_filter not in message_text.lower():
                continue
            row = self.logs_table.rowCount()
            self.logs_table.insertRow(row)
            self.logs_table.setItem(row, 0, QtWidgets.QTableWidgetItem(time_text))
            self.logs_table.setItem(row, 1, QtWidgets.QTableWidgetItem(source_text))
            self.logs_table.setItem(row, 2, QtWidgets.QTableWidgetItem(message_text))
