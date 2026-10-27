from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox, QHBoxLayout, QLabel, QLineEdit, QPushButton, QScrollArea,
    QSizePolicy, QVBoxLayout, QWidget,
)

from app.state import format_with_commas

SMALL_BTN_STYLE = """
QPushButton {
    background: transparent;
    color: #94a3b8;
    font-size: 10px;
    font-weight: 700;
    border: none;
    padding: 2px 4px;
}
QPushButton:hover { color: #334155; }
"""

DELETE_ITEM_BTN_STYLE = SMALL_BTN_STYLE.replace("QPushButton:hover { color: #334155; }", "QPushButton:hover { color: #e11d48; }")

ADD_ITEM_BTN_STYLE = """
QPushButton {
    background: #2563eb;
    color: #ffffff;
    font-size: 12px;
    font-weight: 700;
    border-radius: 11px;
    min-width: 22px;
    min-height: 22px;
    max-width: 22px;
    max-height: 22px;
    border: none;
}
QPushButton:hover { background: #1d4ed8; }
"""


class CtItemChip(QWidget):
    def __init__(self, item_data, parent=None):
        super().__init__(parent)
        self.item_data = item_data
        self.setStyleSheet("""
            CtItemChip {
                background: #ffffff;
                border: 1px solid #cbd5e1;
                border-radius: 5px;
            }
        """)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.label_edit = QLineEdit(item_data.get("label", ""))
        self.label_edit.setFixedWidth(48)
        self.label_edit.setStyleSheet("""
            QLineEdit {
                background: #f1f5f9;
                border: none;
                border-right: 1px solid #cbd5e1;
                border-radius: 0;
                padding: 4px;
                font-size: 10px;
                color: #0f172a;
                text-align: center;
            }
        """)
        layout.addWidget(self.label_edit)

        self.value_edit = QLineEdit(format_with_commas(item_data.get("value", "0.0")))
        self.value_edit.setFixedWidth(56)
        self.value_edit.setStyleSheet("""
            QLineEdit {
                border: none;
                padding: 4px;
                font-size: 10px;
                font-weight: 600;
                color: #0f172a;
            }
        """)
        layout.addWidget(self.value_edit)

        self.delete_btn = QPushButton("x")
        self.delete_btn.setStyleSheet(DELETE_ITEM_BTN_STYLE)
        layout.addWidget(self.delete_btn)


class CtRowWidget(QWidget):
    def __init__(self, row_data, index, get_processes, parent=None):
        super().__init__(parent)
        self.row_data = row_data
        self.index = index
        self.get_processes = get_processes
        self.chips = []

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(6)

        self.process_combo = QComboBox()
        self.process_combo.setFixedWidth(90)
        self.process_combo.setStyleSheet("font-weight: 700; color: #0f172a; font-size: 11px;")
        layout.addWidget(self.process_combo, 0, Qt.AlignTop)

        self.items_container = QWidget()
        self.items_layout = QVBoxLayout(self.items_container)
        self.items_layout.setContentsMargins(0, 0, 0, 0)
        self.items_layout.setSpacing(5)
        self.items_container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        layout.addWidget(self.items_container, 1)

        self.add_item_btn = QPushButton("+")
        self.add_item_btn.setStyleSheet(ADD_ITEM_BTN_STYLE)
        self.add_item_btn.setToolTip("세부 항목 추가")
        layout.addWidget(self.add_item_btn, 0, Qt.AlignTop)

        self.up_btn = QPushButton("↑")
        self.up_btn.setStyleSheet(SMALL_BTN_STYLE)
        layout.addWidget(self.up_btn, 0, Qt.AlignTop)

        self.down_btn = QPushButton("↓")
        self.down_btn.setStyleSheet(SMALL_BTN_STYLE)
        layout.addWidget(self.down_btn, 0, Qt.AlignTop)

        self.delete_row_btn = QPushButton("x")
        self.delete_row_btn.setStyleSheet(SMALL_BTN_STYLE)
        layout.addWidget(self.delete_row_btn, 0, Qt.AlignTop)

        self._refresh_process_combo()
        self._refresh_items()

    def _refresh_process_combo(self):
        self.process_combo.blockSignals(True)
        self.process_combo.clear()
        for p in self.get_processes():
            self.process_combo.addItem(p["id"], p["id"])
        idx = self.process_combo.findData(self.row_data.get("id", ""))
        self.process_combo.setCurrentIndex(idx if idx >= 0 else 0)
        self.process_combo.blockSignals(False)

    def _refresh_items(self):
        while self.items_layout.count():
            item = self.items_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        self.chips = []

        for item_data in self.row_data.get("items", []):
            chip = CtItemChip(item_data, self.items_container)
            self.chips.append(chip)
            self.items_layout.addWidget(chip)
        self.items_layout.addStretch(1)


class CtStatusTableWidget(QWidget):
    changed = Signal()

    def __init__(self, get_processes, parent=None):
        super().__init__(parent)
        self.get_processes = get_processes
        self.ct_status = []

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        header = QWidget()
        header.setStyleSheet("background: #2563eb; border-radius: 6px 6px 0 0;")
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(10, 6, 10, 6)
        h1 = QLabel("공정 NO")
        h1.setFixedWidth(90)
        h2 = QLabel("세부 항목 (C/T)")
        h3 = QLabel("이동/삭제")
        h3.setFixedWidth(70)
        for h in (h1, h2, h3):
            h.setStyleSheet("color: #ffffff; font-size: 11px; font-weight: 700;")
        h_layout.addWidget(h1)
        h_layout.addWidget(h2, 1)
        h_layout.addWidget(h3)
        outer.addWidget(header)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setStyleSheet("QScrollArea { border: 1px solid #e2e8f0; border-top: none; background: #f8fafc; }")
        self.body = QWidget()
        self.body_layout = QVBoxLayout(self.body)
        self.body_layout.setContentsMargins(0, 0, 0, 0)
        self.body_layout.setSpacing(1)
        self.body_layout.addStretch(1)
        self.scroll.setWidget(self.body)
        outer.addWidget(self.scroll, 1)

    def set_ct_status(self, ct_status):
        self.ct_status = ct_status
        self._rebuild()

    def refresh_process_options(self):
        """공정 목록이 바뀌었을 때 각 행의 콤보박스만 갱신."""
        for i in range(self.body_layout.count()):
            widget = self.body_layout.itemAt(i).widget()
            if isinstance(widget, CtRowWidget):
                widget._refresh_process_combo()

    def _rebuild(self):
        while self.body_layout.count():
            item = self.body_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        if not self.ct_status:
            empty = QLabel("등록된 항목이 없습니다.")
            empty.setStyleSheet("color: #94a3b8; font-size: 11px; padding: 16px;")
            empty.setAlignment(Qt.AlignCenter)
            self.body_layout.addWidget(empty)
            self.body_layout.addStretch(1)
            return

        for index, row in enumerate(self.ct_status):
            row_widget = CtRowWidget(row, index, self.get_processes, self.body)
            row_widget.process_combo.currentIndexChanged.connect(
                lambda _i, w=row_widget: self._update_process_id(w)
            )
            row_widget.add_item_btn.clicked.connect(lambda _c=False, w=row_widget: self._add_item(w))
            row_widget.up_btn.clicked.connect(lambda _c=False, i=index: self._move_row(i, -1))
            row_widget.down_btn.clicked.connect(lambda _c=False, i=index: self._move_row(i, 1))
            row_widget.delete_row_btn.clicked.connect(lambda _c=False, i=index: self._delete_row(i))

            for chip in row_widget.chips:
                chip.label_edit.editingFinished.connect(
                    lambda c=chip: self._update_item(c, "label", c.label_edit.text())
                )
                chip.value_edit.editingFinished.connect(
                    lambda c=chip: self._update_item_value(c)
                )
                chip.delete_btn.clicked.connect(lambda _c=False, w=row_widget, c=chip: self._delete_item(w, c))

            self.body_layout.addWidget(row_widget)

        self.body_layout.addStretch(1)

    def _update_process_id(self, row_widget):
        row_widget.row_data["id"] = row_widget.process_combo.currentData() or ""
        self.changed.emit()

    def _update_item(self, chip, field, value):
        chip.item_data[field] = value
        self.changed.emit()

    def _update_item_value(self, chip):
        cleaned = chip.value_edit.text().replace(",", "")
        chip.item_data["value"] = cleaned
        chip.value_edit.setText(format_with_commas(cleaned))
        self.changed.emit()

    def _add_item(self, row_widget):
        row_widget.row_data.setdefault("items", []).append(
            {"label": f"항목{len(row_widget.row_data['items']) + 1}", "value": "0.0"}
        )
        self._rebuild()
        self.changed.emit()

    def _delete_item(self, row_widget, chip):
        if chip.item_data in row_widget.row_data.get("items", []):
            row_widget.row_data["items"].remove(chip.item_data)
        self._rebuild()
        self.changed.emit()

    def _move_row(self, index, direction):
        target = index + direction
        if target < 0 or target >= len(self.ct_status):
            return
        self.ct_status[index], self.ct_status[target] = self.ct_status[target], self.ct_status[index]
        self._rebuild()
        self.changed.emit()

    def _delete_row(self, index):
        del self.ct_status[index]
        self._rebuild()
        self.changed.emit()

    def add_row(self):
        processes = self.get_processes()
        default_id = processes[0]["id"] if processes else ""
        self.ct_status.append({
            "id": default_id,
            "items": [
                {"label": "로딩", "value": "0.0"},
                {"label": "작업", "value": "0.0"},
                {"label": "언로딩", "value": "0.0"},
            ],
        })
        self._rebuild()
        self.changed.emit()
