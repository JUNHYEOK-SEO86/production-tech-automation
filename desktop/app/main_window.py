from datetime import datetime

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox, QDialog, QFileDialog, QHBoxLayout, QLabel, QLineEdit, QMainWindow,
    QMessageBox, QPushButton, QStackedWidget, QVBoxLayout, QWidget,
)

from app.screens.screen_ct import CtProcessScreen
from app.screens.screen_fixed import FixedValuesScreen
from app.screens.screen_docs import DocScreen
from app.screens.screen_master import MasterInfoScreen
from app.sidebar import Sidebar
from app.state import AppState

PLACEHOLDER_TITLES = {
    "1-3": "1-3. 설비 공법 검토",
    "2": "2. 품의 / 발주",
    "3": "3. 설치 / 품힉 (T/O)",
    "4": "4. 운송 & HTS 코드",
    "5": "5. 완료보고 & 집계",
}

TOP_BUTTON_STYLE = """
QPushButton {
    font-size: 11px;
    font-weight: 600;
    padding: 7px 14px;
    border-radius: 8px;
    border: none;
    color: #ffffff;
}
"""


class AddItemDialog(QDialog):
    """ITEM 품명 추가: 아이템(샤시/차체 ...)을 고르고 품명을 입력한다."""

    def __init__(self, parent, item_names, default_item=""):
        super().__init__(parent)
        self.setWindowTitle("ITEM 품명 추가")
        self.setMinimumWidth(360)
        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        layout.addWidget(QLabel("아이템"))
        self.item_combo = QComboBox()
        self.item_combo.addItems(item_names)
        if default_item in item_names:
            self.item_combo.setCurrentText(default_item)
        layout.addWidget(self.item_combo)

        layout.addWidget(QLabel("품명 (고정값의 품명 목록에도 추가됩니다)"))
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("예: FR C/MBR")
        layout.addWidget(self.name_edit)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        ok_btn = QPushButton("추가")
        ok_btn.clicked.connect(self._accept)
        cancel_btn = QPushButton("취소")
        cancel_btn.clicked.connect(self.reject)
        buttons.addWidget(ok_btn)
        buttons.addWidget(cancel_btn)
        layout.addLayout(buttons)

    def _accept(self):
        if not self.name_edit.text().strip():
            QMessageBox.warning(self, "알림", "품명을 입력해주세요.")
            return
        self.accept()

    def values(self):
        return self.item_combo.currentText().strip(), self.name_edit.text().strip()


class PlaceholderScreen(QWidget):
    def __init__(self, title, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        label = QLabel(f"{title}\n\n준비 중인 화면입니다.")
        label.setStyleSheet("color: #94a3b8; font-size: 14px; font-weight: 600;")
        label.setAlignment(Qt.AlignCenter)
        layout.addWidget(label)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PE-AMS Process Development Automation System")
        self.resize(1440, 900)

        self.state = AppState()

        central = QWidget()
        self.setCentralWidget(central)
        root_layout = QHBoxLayout(central)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        self.sidebar = Sidebar()
        self.sidebar.screenSelected.connect(self._on_screen_selected)
        root_layout.addWidget(self.sidebar)

        main_area = QWidget()
        main_area.setStyleSheet("background: #eef2f6;")
        main_layout = QVBoxLayout(main_area)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(16)
        root_layout.addWidget(main_area, 1)

        main_layout.addWidget(self._build_top_bar())

        self.stack = QStackedWidget()
        self.screen_master = MasterInfoScreen(self.state)
        self.screens = {"1-1": self.screen_master}
        self.stack.addWidget(self.screen_master)

        self.screen_ct = CtProcessScreen(self.state)
        self.screen_ct.delete_item_btn.clicked.connect(self._delete_current_item)
        self.screens["1-2"] = self.screen_ct
        self.stack.addWidget(self.screen_ct)

        for screen_id, title in PLACEHOLDER_TITLES.items():
            placeholder = PlaceholderScreen(title)
            self.screens[screen_id] = placeholder
            self.stack.addWidget(placeholder)

        self.screen_fixed = FixedValuesScreen(self.state)
        self.stack.addWidget(self.screen_fixed)

        self.screen_docs = DocScreen(self.state)
        self.screen_docs.itemsChanged.connect(self._refresh_item_selector)
        self.screens["1-4"] = self.screen_docs
        self.stack.addWidget(self.screen_docs)

        main_layout.addWidget(self.stack, 1)

        self.sidebar.set_active("1-1")
        self._refresh_item_selector()
        self._refresh_item_screens()

    def _build_top_bar(self):
        bar = QWidget()
        bar.setStyleSheet("background: #ffffff; border: 1px solid #e2e8f0; border-radius: 12px;")
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(16, 10, 16, 10)
        layout.setSpacing(10)

        title_box = QVBoxLayout()
        title = QLabel("ITEM 선택 (품명)")
        title.setStyleSheet("font-weight: 700; color: #1e293b; font-size: 12px;")
        subtitle = QLabel("고정값의 품명을 선택하면 아래 화면이 바뀝니다")
        subtitle.setStyleSheet("color: #94a3b8; font-size: 10px;")
        title_box.addWidget(title)
        title_box.addWidget(subtitle)
        layout.addLayout(title_box)

        self.item_combo = QComboBox()
        self.item_combo.setMinimumWidth(300)
        self.item_combo.setStyleSheet(
            "QComboBox { background: #f8fafc; border: 1px solid #cbd5e1; border-radius: 6px;"
            " padding: 6px 10px; font-size: 13px; font-weight: 600; color: #000000; }"
            "QComboBox:focus { border-color: #2563eb; }")
        self.item_combo.activated.connect(self._on_item_chosen)
        layout.addWidget(self.item_combo)
        layout.addStretch(1)

        add_btn = QPushButton("ITEM 품명 추가")
        add_btn.setStyleSheet(TOP_BUTTON_STYLE + "QPushButton { background: #059669; } QPushButton:hover { background: #047857; }")
        add_btn.clicked.connect(self._on_add_item)
        layout.addWidget(add_btn)

        save_btn = QPushButton("데이터 저장")
        save_btn.setStyleSheet(TOP_BUTTON_STYLE + "QPushButton { background: #2563eb; } QPushButton:hover { background: #1d4ed8; }")
        save_btn.clicked.connect(self._on_save_manual)
        layout.addWidget(save_btn)

        backup_btn = QPushButton("백업")
        backup_btn.setStyleSheet(TOP_BUTTON_STYLE + "QPushButton { background: #334155; } QPushButton:hover { background: #1e293b; }")
        backup_btn.clicked.connect(self._on_export_backup)
        layout.addWidget(backup_btn)

        load_btn = QPushButton("불러오기")
        load_btn.setStyleSheet(TOP_BUTTON_STYLE + "QPushButton { background: #cbd5e1; color: #334155; } QPushButton:hover { background: #94a3b8; color: #ffffff; }")
        load_btn.clicked.connect(self._on_import_backup)
        layout.addWidget(load_btn)

        return bar

    # ---------------- 화면 전환 ----------------
    def _on_screen_selected(self, screen_id):
        self.sidebar.set_active(screen_id)
        self.screen_docs.flush()
        self._refresh_item_selector()
        if screen_id.startswith("fv:"):
            self.screen_fixed.set_category(screen_id[3:])
            self.stack.setCurrentWidget(self.screen_fixed)
            return
        widget = self.screens.get(screen_id)
        if widget:
            self.stack.setCurrentWidget(widget)
            if widget is self.screen_docs:
                self.screen_docs.refresh()
            elif widget is self.screen_master:
                self.screen_master.refresh()

    def _refresh_item_screens(self):
        """현재 ITEM 기준으로 입력 화면들을 다시 채운다."""
        self.screen_master.refresh()
        self.screen_ct.refresh()

    def closeEvent(self, event):
        self.screen_docs.flush()
        super().closeEvent(event)

    # ---------------- ITEM 선택 (품명) ----------------
    def _refresh_item_selector(self):
        choices = self.state.item_choices()
        self.item_combo.blockSignals(True)
        self.item_combo.clear()
        self.item_combo.addItems(choices)
        self.item_combo.setCurrentIndex(choices.index(self.state.current_item) if self.state.current_item in choices else -1)
        self.item_combo.blockSignals(False)

    def _on_item_chosen(self, _index):
        name = self.item_combo.currentText().strip()
        if name and name != self.state.current_item:
            self._select_item(name)

    def _select_item(self, name):
        if name not in self.state.items:
            self.state.add_item(name)
        else:
            self.state.current_item = name
            self.state.save()
        self._prefill_master_project(name)
        self._refresh_item_selector()
        self._refresh_item_screens()

    def _prefill_master_project(self, name):
        """처음 선택한 품명이면 MASTER 정보의 아이템 / 아이템구분을 고정값 기준으로 채운다."""
        project = self.state.master_info()["project"]
        item_class = self.state.item_class_of(name)
        changed = False
        if item_class and not project["item"]:
            project["item"] = item_class
            changed = True
        if not project["item_class"]:
            project["item_class"] = name
            changed = True
        if changed:
            self.state.save()

    def _on_item_deleted(self, name):
        if len(self.state.item_order) <= 1:
            QMessageBox.warning(self, "알림", "마지막 남은 ITEM은 삭제할 수 없습니다.")
            return
        reply = QMessageBox.question(
            self, "삭제 확인", f"'{name}' ITEM의 입력 내용을 삭제하시겠습니까?\n(고정값의 품명 목록에서는 삭제되지 않습니다)"
        )
        if reply != QMessageBox.Yes:
            return
        self.state.delete_item(name)
        self._refresh_item_selector()
        self._refresh_item_screens()

    def _delete_current_item(self):
        self._on_item_deleted(self.state.current_item)

    def _on_add_item(self):
        current_class = self.state.item_class_of(self.state.current_item)
        dialog = AddItemDialog(self, self.state.fixed_list("Item"), current_class)
        if dialog.exec() != QDialog.Accepted:
            return
        item_class, name = dialog.values()
        names = self.state.fixed_list(f"{item_class}_품명")
        if name not in names:
            names.append(name)
            self.state.save()
        self._select_item(name)

    # ---------------- 저장/백업/불러오기 ----------------
    def _export_with_dialog(self, dialog_title, success_title, success_message):
        default_name = f"PE_AMS_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        path, _ = QFileDialog.getSaveFileName(self, dialog_title, default_name, "JSON 파일 (*.json)")
        if not path:
            return
        self.state.export_to(path)
        QMessageBox.information(self, success_title, success_message)

    def _on_save_manual(self):
        self.state.save()
        self._export_with_dialog(
            "데이터 저장 - 저장 위치 선택",
            "저장 완료",
            "현재까지 작업된 정보가 지정하신 위치에 저장되었습니다.",
        )

    def _on_export_backup(self):
        self._export_with_dialog(
            "백업 파일 저장",
            "백업 완료",
            "백업 파일을 저장했습니다.",
        )

    def _on_import_backup(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "백업 파일 불러오기", "", "JSON 파일 (*.json)"
        )
        if not path:
            return
        try:
            self.state.import_from(path)
        except (OSError, ValueError) as e:
            QMessageBox.critical(self, "오류", f"파일을 불러오는 중 오류가 발생했습니다.\n{e}")
            return
        self._refresh_item_selector()
        self._refresh_item_screens()
        QMessageBox.information(self, "복원 완료", "백업 파일 복원이 완료되었습니다.")
