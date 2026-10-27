from PySide6.QtWidgets import (
    QFileDialog, QFrame, QGridLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QSplitter, QVBoxLayout, QWidget,
)
from PySide6.QtCore import Qt

from app.state import compute_target_ct, format_with_commas
from app.widgets.cad_layout import CadDropZone, PaletteHandle
from app.widgets.ct_status_table import CtStatusTableWidget
from app.widgets.process_table import ProcessTableWidget

CARD_STYLE = """
QFrame#card {
    background: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 12px;
}
"""

INPUT_STYLE = """
QLineEdit {
    background: #f8fafc;
    border: 1px solid #cbd5e1;
    border-radius: 5px;
    padding: 5px 8px;
    font-size: 12px;
    color: #0f172a;
}
QLineEdit:focus { border-color: #2563eb; }
"""

TARGET_CT_STYLE = """
QLineEdit {
    background: #eff6ff;
    border: 1px solid #bfdbfe;
    border-radius: 5px;
    padding: 5px 8px;
    font-size: 12px;
    font-weight: 700;
    color: #1d4ed8;
    text-align: center;
}
"""


def make_field_label(text, blue=False):
    label = QLabel(text)
    color = "#2563eb" if blue else "#64748b"
    label.setStyleSheet(f"color: {color}; font-size: 10px; font-weight: 600;")
    return label


class CtProcessScreen(QWidget):
    def __init__(self, state, parent=None):
        super().__init__(parent)
        self.state = state

        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        splitter = QSplitter(Qt.Horizontal)
        splitter.setChildrenCollapsible(False)
        outer.addWidget(splitter)

        splitter.addWidget(self._build_left_column())
        splitter.addWidget(self._build_right_column())
        splitter.setStretchFactor(0, 7)
        splitter.setStretchFactor(1, 5)

    # ---------------- 왼쪽: 정보 입력 + CAD 레이아웃 ----------------
    def _build_left_column(self):
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(4, 8, 4, 8)
        layout.setSpacing(16)

        layout.addWidget(self._build_info_card())
        layout.addWidget(self._build_cad_card(), 1)
        return container

    def _build_info_card(self):
        card = QFrame()
        card.setObjectName("card")
        card.setStyleSheet(CARD_STYLE)
        outer = QVBoxLayout(card)
        outer.setContentsMargins(18, 16, 18, 16)
        outer.setSpacing(10)

        title_row = QHBoxLayout()
        title = QLabel("정보 기입")
        title.setStyleSheet("font-weight: 700; color: #1e293b; font-size: 13px;")
        title_row.addWidget(title)
        title_row.addStretch(1)
        self.delete_item_btn = QPushButton("현재 화면 삭제")
        self.delete_item_btn.setStyleSheet("color: #94a3b8; font-size: 11px; border: none;")
        title_row.addWidget(self.delete_item_btn)
        outer.addLayout(title_row)

        grid = QGridLayout()
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(2)

        self.car_edit = QLineEdit()
        self.car_edit.setStyleSheet(INPUT_STYLE)
        self.qty_edit = QLineEdit()
        self.qty_edit.setStyleSheet(INPUT_STYLE)
        self.eff_edit = QLineEdit()
        self.eff_edit.setStyleSheet(INPUT_STYLE)
        self.hours_edit = QLineEdit()
        self.hours_edit.setStyleSheet(INPUT_STYLE)
        self.days_edit = QLineEdit()
        self.days_edit.setStyleSheet(INPUT_STYLE)
        self.target_ct_edit = QLineEdit()
        self.target_ct_edit.setReadOnly(True)
        self.target_ct_edit.setStyleSheet(TARGET_CT_STYLE)

        fields = [
            ("차종명", self.car_edit, False),
            ("생산대수 (대)", self.qty_edit, False),
            ("라인효율 (%)", self.eff_edit, False),
            ("일근무 (HR)", self.hours_edit, False),
            ("연근무 (일)", self.days_edit, False),
            ("목표 C/T (초/대)", self.target_ct_edit, True),
        ]
        for col, (label_text, widget, blue) in enumerate(fields):
            grid.addWidget(make_field_label(label_text, blue), 0, col)
            grid.addWidget(widget, 1, col)

        outer.addLayout(grid)

        for edit in (self.car_edit,):
            edit.editingFinished.connect(self._on_inputs_changed)
        for edit in (self.qty_edit, self.eff_edit, self.hours_edit, self.days_edit):
            edit.editingFinished.connect(self._on_numeric_input_finished)

        return card

    def _build_cad_card(self):
        card = QFrame()
        card.setStyleSheet("""
            QFrame#cadCard {
                background: #1f293d;
                border: 1px solid #334155;
                border-radius: 12px;
            }
        """)
        card.setObjectName("cadCard")
        outer = QVBoxLayout(card)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        header = QWidget()
        header.setStyleSheet("background: #111827; border-radius: 12px 12px 0 0;")
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(14, 10, 14, 10)
        title = QLabel("공정 레이아웃")
        title.setStyleSheet("color: #ffffff; font-weight: 700; font-size: 12px;")
        h_layout.addWidget(title)
        h_layout.addStretch(1)

        self.palette_handle = PaletteHandle("공정 NO")
        h_layout.addWidget(self.palette_handle)

        self.upload_image_btn = QPushButton("이미지 업로드")
        self.upload_image_btn.setStyleSheet("""
            QPushButton {
                background: #2563eb; color: #ffffff; font-size: 11px; font-weight: 600;
                padding: 6px 12px; border-radius: 6px; border: none;
            }
            QPushButton:hover { background: #1d4ed8; }
        """)
        self.upload_image_btn.clicked.connect(self._on_upload_image)
        h_layout.addWidget(self.upload_image_btn)

        outer.addWidget(header)

        self.cad_zone = CadDropZone(self._get_current_processes)
        self.cad_zone.changed.connect(self._on_data_changed)
        outer.addWidget(self.cad_zone, 1)

        return card

    # ---------------- 오른쪽: 공정 표 + C/T 현황 ----------------
    def _build_right_column(self):
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(4, 8, 4, 8)
        layout.setSpacing(16)

        layout.addWidget(self._build_process_card())
        layout.addWidget(self._build_ct_card(), 1)
        return container

    def _build_process_card(self):
        card = QFrame()
        card.setObjectName("card")
        card.setStyleSheet(CARD_STYLE)
        card.setMinimumHeight(300)
        card.setMaximumHeight(340)
        outer = QVBoxLayout(card)
        outer.setContentsMargins(18, 14, 18, 14)
        outer.setSpacing(8)

        top = QHBoxLayout()
        title = QLabel("ITEM 및 공정 구성")
        title.setStyleSheet("font-weight: 700; color: #1e293b; font-size: 13px;")
        top.addWidget(title)
        top.addStretch(1)
        add_btn = QPushButton("공정 추가")
        add_btn.setStyleSheet("""
            QPushButton {
                background: #2563eb; color: #ffffff; font-size: 11px; font-weight: 600;
                padding: 6px 12px; border-radius: 6px; border: none;
            }
            QPushButton:hover { background: #1d4ed8; }
        """)
        top.addWidget(add_btn)
        outer.addLayout(top)

        self.process_table = ProcessTableWidget()
        self.process_table.setStyleSheet("border: 1px solid #e2e8f0; border-radius: 8px;")
        self.process_table.changed.connect(self._on_processes_changed)
        add_btn.clicked.connect(self._on_add_process_row)
        outer.addWidget(self.process_table, 1)

        return card

    def _build_ct_card(self):
        card = QFrame()
        card.setObjectName("card")
        card.setStyleSheet(CARD_STYLE)
        outer = QVBoxLayout(card)
        outer.setContentsMargins(18, 14, 18, 14)
        outer.setSpacing(8)

        top_bar = QWidget()
        top_bar.setStyleSheet("background: #f1f5f9; border-radius: 6px;")
        top_layout = QHBoxLayout(top_bar)
        top_layout.setContentsMargins(10, 6, 10, 6)
        title = QLabel("공정별 C/T 현황")
        title.setStyleSheet("font-weight: 700; color: #1e293b; font-size: 13px;")
        top_layout.addWidget(title)
        top_layout.addStretch(1)
        add_row_btn = QPushButton("행 추가")
        add_row_btn.setStyleSheet("""
            QPushButton {
                background: #2563eb; color: #ffffff; font-size: 11px; font-weight: 600;
                padding: 5px 10px; border-radius: 6px; border: none;
            }
            QPushButton:hover { background: #1d4ed8; }
        """)
        top_layout.addWidget(add_row_btn)
        outer.addWidget(top_bar)

        self.ct_table = CtStatusTableWidget(self._get_current_processes)
        self.ct_table.changed.connect(self._on_data_changed)
        add_row_btn.clicked.connect(self.ct_table.add_row)
        outer.addWidget(self.ct_table, 1)

        note = QLabel("• 레이아웃 공정 박스는 마우스로 자유롭게 드래그할 수 있으며, Ctrl + 클릭 시 복제됩니다.")
        note.setWordWrap(True)
        note.setStyleSheet("background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 8px; color: #64748b; font-size: 10px;")
        outer.addWidget(note)

        return card

    # ---------------- 데이터 바인딩 ----------------
    def _get_current_processes(self):
        return self.state.current().get("processes", [])

    def refresh(self):
        item = self.state.current()
        inputs = item["inputs"]

        self.car_edit.setText(inputs.get("car", ""))
        self.qty_edit.setText(format_with_commas(inputs.get("qty", "0")))
        self.eff_edit.setText(format_with_commas(inputs.get("eff", "0")))
        self.hours_edit.setText(format_with_commas(inputs.get("hours", "0")))
        self.days_edit.setText(format_with_commas(inputs.get("days", "0")))
        self._update_target_ct(inputs)

        self.process_table.set_processes(item["processes"])
        self.ct_table.set_ct_status(item["ct_status"])

        image_path = self.state.resolve_image(item["cad"].get("image", ""))
        self.cad_zone.set_data(image_path, item["cad"].get("nodes", []))

    def _update_target_ct(self, inputs):
        target = compute_target_ct(inputs)
        self.target_ct_edit.setText(f"{target:.1f}" if target else "0.0")

    def _on_inputs_changed(self):
        item = self.state.current()
        item["inputs"]["car"] = self.car_edit.text()
        self._on_data_changed()

    def _on_numeric_input_finished(self):
        sender = self.sender()
        cleaned = sender.text().replace(",", "")
        sender.setText(format_with_commas(cleaned))

        item = self.state.current()
        inputs = item["inputs"]
        inputs["qty"] = self.qty_edit.text().replace(",", "")
        inputs["eff"] = self.eff_edit.text().replace(",", "")
        inputs["hours"] = self.hours_edit.text().replace(",", "")
        inputs["days"] = self.days_edit.text().replace(",", "")
        self._update_target_ct(inputs)
        self._on_data_changed()

    def _on_processes_changed(self):
        self.ct_table.refresh_process_options()
        self.cad_zone.refresh_all_nodes()
        self._on_data_changed()

    def _on_add_process_row(self):
        self.process_table.add_row()

    def _on_upload_image(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "레이아웃 이미지 선택", "", "이미지 파일 (*.png *.jpg *.jpeg *.bmp *.gif)"
        )
        if not path:
            return
        filename = self.state.copy_image(path)
        item = self.state.current()
        item["cad"]["image"] = filename
        self.cad_zone.set_image(self.state.resolve_image(filename))
        self._on_data_changed()

    def _on_data_changed(self):
        self.state.save()
