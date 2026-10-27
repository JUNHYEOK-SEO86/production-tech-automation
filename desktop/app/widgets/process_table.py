from PySide6.QtCore import Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QLineEdit, QPushButton, QScrollArea, QVBoxLayout, QWidget

SMALL_BTN_STYLE = """
QPushButton {
    background: #f1f5f9;
    color: #475569;
    font-size: 10px;
    font-weight: 700;
    border-radius: 4px;
    padding: 3px 6px;
    border: none;
}
QPushButton:hover { background: #e2e8f0; }
"""

DANGER_BTN_STYLE = """
QPushButton {
    background: #f1f5f9;
    color: #475569;
    font-size: 10px;
    font-weight: 700;
    border-radius: 4px;
    padding: 3px 6px;
    border: none;
}
QPushButton:hover { background: #e11d48; color: #ffffff; }
"""

ADD_BTN_STYLE = """
QPushButton {
    background: #dbeafe;
    color: #2563eb;
    font-size: 10px;
    font-weight: 700;
    border-radius: 4px;
    padding: 3px 6px;
    border: none;
}
QPushButton:hover { background: #2563eb; color: #ffffff; }
"""


class ProcessRowWidget(QWidget):
    def __init__(self, row_data, index, total, parent=None):
        super().__init__(parent)
        self.row_data = row_data
        self.index = index

        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 4, 6, 4)
        layout.setSpacing(6)

        self.id_edit = QLineEdit(row_data.get("id", ""))
        self.id_edit.setFixedWidth(84)
        self.id_edit.setStyleSheet("font-weight: 700; color: #0f172a; padding: 3px 6px; border: 1px solid #e2e8f0; border-radius: 4px; background: #f8fafc;")
        layout.addWidget(self.id_edit)

        self.name_edit = QLineEdit(row_data.get("name", ""))
        self.name_edit.setStyleSheet("color: #0f172a; padding: 3px 6px; border: 1px solid #e2e8f0; border-radius: 4px; background: #f8fafc;")
        layout.addWidget(self.name_edit, 1)

        self.up_btn = QPushButton("↑")
        self.up_btn.setStyleSheet(SMALL_BTN_STYLE)
        self.up_btn.setEnabled(index > 0)
        layout.addWidget(self.up_btn)

        self.down_btn = QPushButton("↓")
        self.down_btn.setStyleSheet(SMALL_BTN_STYLE)
        self.down_btn.setEnabled(index < total - 1)
        layout.addWidget(self.down_btn)

        self.insert_btn = QPushButton("+")
        self.insert_btn.setToolTip("바로 아래 공정 추가")
        self.insert_btn.setStyleSheet(ADD_BTN_STYLE)
        layout.addWidget(self.insert_btn)

        self.delete_btn = QPushButton("x")
        self.delete_btn.setToolTip("삭제")
        self.delete_btn.setStyleSheet(DANGER_BTN_STYLE)
        layout.addWidget(self.delete_btn)


class ProcessTableWidget(QWidget):
    changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.processes = []

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        header = QWidget()
        header.setStyleSheet("background: #f1f5f9; border-bottom: 1px solid #e2e8f0;")
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(10, 6, 10, 6)
        h1 = QLabel("공정 NO")
        h1.setFixedWidth(84)
        h2 = QLabel("공정명")
        h3 = QLabel("삽입 / 이동 / 삭제")
        for h in (h1, h2, h3):
            h.setStyleSheet("color: #475569; font-size: 11px; font-weight: 700;")
        h_layout.addWidget(h1)
        h_layout.addWidget(h2, 1)
        h_layout.addWidget(h3)
        outer.addWidget(header)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setStyleSheet("QScrollArea { border: none; }")
        self.body = QWidget()
        self.body_layout = QVBoxLayout(self.body)
        self.body_layout.setContentsMargins(0, 0, 0, 0)
        self.body_layout.setSpacing(1)
        self.body_layout.addStretch(1)
        self.scroll.setWidget(self.body)
        outer.addWidget(self.scroll, 1)

    def set_processes(self, processes):
        self.processes = processes
        self._rebuild()

    def _rebuild(self):
        while self.body_layout.count():
            item = self.body_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        total = len(self.processes)
        for index, row in enumerate(self.processes):
            row_widget = ProcessRowWidget(row, index, total, self.body)
            row_widget.id_edit.editingFinished.connect(
                lambda w=row_widget: self._update_field(w.index, "id", w.id_edit.text())
            )
            row_widget.name_edit.editingFinished.connect(
                lambda w=row_widget: self._update_field(w.index, "name", w.name_edit.text())
            )
            row_widget.up_btn.clicked.connect(lambda _c=False, i=index: self._move_row(i, -1))
            row_widget.down_btn.clicked.connect(lambda _c=False, i=index: self._move_row(i, 1))
            row_widget.insert_btn.clicked.connect(lambda _c=False, i=index: self._insert_row(i))
            row_widget.delete_btn.clicked.connect(lambda _c=False, i=index: self._delete_row(i))
            self.body_layout.addWidget(row_widget)

        self.body_layout.addStretch(1)

    def _update_field(self, index, field, value):
        self.processes[index][field] = value
        self.changed.emit()

    def _move_row(self, index, direction):
        target = index + direction
        if target < 0 or target >= len(self.processes):
            return
        self.processes[index], self.processes[target] = self.processes[target], self.processes[index]
        self._rebuild()
        self.changed.emit()

    def _insert_row(self, after_index):
        new_row = {"id": f"OP-{len(self.processes) + 1:03d}", "name": "신규 공정명 입력"}
        self.processes.insert(after_index + 1, new_row)
        self._rebuild()
        self.changed.emit()

    def add_row(self):
        new_row = {"id": f"OP-{len(self.processes) + 1:03d}", "name": "신규 공정명 입력"}
        self.processes.append(new_row)
        self._rebuild()
        self.changed.emit()

    def _delete_row(self, index):
        del self.processes[index]
        self._rebuild()
        self.changed.emit()
