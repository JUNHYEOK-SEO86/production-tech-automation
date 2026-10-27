"""고정값: 드롭다운에 쓰는 선택 목록(아이템, 품명, 단계, 팀명, 담당자/직급, 라인 구분, 설치장소, 상세공정명 등)을 보고 고친다.

여기서 고친 내용은 바로 저장되고, 1-1 MASTER 정보 기입 등의 드롭다운에 반영된다.
"""
import uuid

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView, QComboBox, QFrame, QHBoxLayout, QHeaderView, QLabel, QListWidget,
    QListWidgetItem, QMessageBox, QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

CARD_STYLE = """
QFrame#fvCard {
    background: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 12px;
}
"""
LIST_STYLE = """
QListWidget, QTableWidget { border: 1px solid #e2e8f0; border-radius: 6px; font-size: 13px; color: #000000; background: #ffffff; gridline-color: #e2e8f0; }
QListWidget::item { padding: 6px 8px; }
QListWidget::item:selected, QTableWidget::item:selected { background: #dbeafe; color: #000000; }
QListWidget QLineEdit, QTableWidget QLineEdit { color: #000000; background: #ffffff; border: 1px solid #2563eb; }
QHeaderView::section { background: #f1f5f9; color: #475569; border: none; border-bottom: 1px solid #e2e8f0; padding: 4px; font-weight: 600; }
"""
PRIMARY_BTN = """
QPushButton { background: #2563eb; color: #ffffff; font-size: 11px; font-weight: 600; padding: 6px 12px; border-radius: 6px; border: none; }
QPushButton:hover { background: #1d4ed8; }
"""
SUB_BTN = """
QPushButton { background: #f1f5f9; color: #000000; font-size: 11px; font-weight: 600; padding: 6px 10px; border-radius: 6px; border: 1px solid #cbd5e1; }
QPushButton:hover { background: #e2e8f0; }
"""
DANGER_BTN = SUB_BTN.replace("QPushButton:hover { background: #e2e8f0; }", "QPushButton:hover { background: #fee2e2; color: #b91c1c; }")
RANK_COMBO_STYLE = "QComboBox { color: #000000; background: #ffffff; border: none; padding: 2px 6px; font-size: 12px; }"

from app import method_calc as mc
from app.state import parse_number

NEW_ITEM_TEXT = "새 항목"
NO_RANK_TEXT = "(미지정)"

# mode
#   simple          목록 1개
#   grouped         왼쪽 목록의 값마다 하위 목록이 있음 (아이템 -> 품명)
#   groups_fixed    고정된 여러 목록 중 선택
#   groups_editable 목록 묶음 이름도 추가/수정/삭제 가능
#   derived         다른 목록(라인 구분)의 값마다 하위 목록이 있음
#   persons         소속(추가/삭제/이름변경) 아래에 이름 + 직급
#   priced_fixed    고정된 여러 목록 중 선택, 각 목록은 항목 + 단가
#   priced_editable 목록 이름도 추가/수정/삭제 가능, 각 목록은 항목 + 단가
CATEGORIES = {
    "item": dict(
        label="아이템 / 품명", mode="grouped", parent_title="아이템", parent_key="Item",
        child_title="품명 (아이템구분)", child_key="{}_품명",
        usage="상단 ITEM 선택(품명) 드롭다운과 1-1 MASTER 정보 기입 > 아이템 / 아이템구분 드롭다운. 아이템을 고르면 그 아이템의 품명 목록이 나옵니다.",
    ),
    "step": dict(
        label="단계", mode="simple", child_title="단계", child_key="DesStep",
        usage="1-1 MASTER 정보 기입 > 단계 드롭다운.",
    ),
    "team": dict(
        label="팀명", mode="simple", child_title="팀명", child_key="Team",
        usage="1-1 MASTER 정보 기입 > 팀명 드롭다운.",
    ),
    "person": dict(
        label="담당자", mode="persons", parent_title="소속",
        usage="1-1 MASTER 정보 기입 > 팀명을 고르면 같은 이름의 소속에 등록된 담당자가 나오고, 담당자를 고르면 직급이 자동으로 입력됩니다.",
    ),
    "rank": dict(
        label="직급 / REV", mode="groups_fixed", parent_title="목록 선택",
        groups=[("직급", "Rank"), ("REV", "Rev")],
        usage="직급: 담당자의 직급 드롭다운. REV: 1-1 MASTER 정보 기입 > Rev. 드롭다운.",
    ),
    "line": dict(
        label="라인 구분 / 전용범용", mode="groups_editable", parent_title="목록 선택", store="line",
        groups=[("라인 구분", "Line"), ("전용 / 범용", "전용범용")],
        usage="라인 구분: 1-1 MASTER 정보 기입 > II. 라인 관리 > 구분 드롭다운. 라인 구분 값은 '상세공정명' 목록과도 연결됩니다.",
    ),
    "site": dict(
        label="설치장소 / 근무조", mode="groups_editable", parent_title="목록 선택", store="site",
        groups=[("설치장소", "설치장소"), ("근무조", "Shift")],
        usage="1-1 MASTER 정보 기입 > II. 라인 관리 > Line Condition의 설치장, 용접/조립 근무조 드롭다운.",
    ),
    "jig": dict(
        label="JIG 원가 리스트", mode="priced_fixed", parent_title="목록 선택", store="Jig",
        groups=[(g, g) for g in mc.JIG_GROUPS],
        usage="MASTER 정보 기입 > III. 공법 설계 > 전용설비 금액 산출표의 JIG BASE / JIG TYPE / 차광막·안전센서 / EJECTOR / JIG UNIT / 기타(UTILITY) 드롭다운과 금액. 항목 이름과 단가를 고치면 공법 설계의 금액에 바로 반영됩니다.",
    ),
    "equip": dict(
        label="설비 단가", mode="priced_editable", parent_title="설비 종류 (전용/범용 · 종류)", store="Equip",
        usage="MASTER 정보 기입 > III. 공법 설계 > 설비 내역의 전/범용 → 설비 → 설비명 드롭다운과 단가. 목록 이름은 '전용 · 종류' 또는 '범용 · 종류' 형태로 적어주세요. 공정별로 고를 수 있는 설비 종류는 엑셀 마스터와 같게 가져왔고, 새로 추가한 종류는 모든 공정에서 보입니다.",
    ),
    "code": dict(
        label="상세공정명", mode="derived", parent_title="라인 구분", parent_source="Line",
        child_title="상세공정명", child_key="{}_공정Code",
        usage="1-1 MASTER 정보 기입 > III. 공정 관리 > 상세공정명 드롭다운. 라인 구분(라인 구분 목록)마다 목록이 따로 있습니다. 문서 생성용 고정값(STD)의 공정 이름과 같아야 문서에 반영됩니다.",
    ),
}


def _button_row(*buttons):
    row = QHBoxLayout()
    row.setSpacing(6)
    for btn in buttons:
        row.addWidget(btn)
    row.addStretch(1)
    return row


def _make_buttons():
    add_btn = QPushButton("+ 추가")
    add_btn.setStyleSheet(PRIMARY_BTN)
    up_btn = QPushButton("↑")
    up_btn.setStyleSheet(SUB_BTN)
    down_btn = QPushButton("↓")
    down_btn.setStyleSheet(SUB_BTN)
    delete_btn = QPushButton("삭제")
    delete_btn.setStyleSheet(DANGER_BTN)
    return add_btn, up_btn, down_btn, delete_btn


class _PanelBase(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("fvCard")
        self.setStyleSheet(CARD_STYLE)
        self.layout_ = QVBoxLayout(self)
        self.layout_.setContentsMargins(14, 12, 14, 12)
        self.layout_.setSpacing(8)
        head = QHBoxLayout()
        self.title = QLabel("")
        self.title.setStyleSheet("font-weight: 700; color: #000000; font-size: 13px;")
        head.addWidget(self.title)
        head.addStretch(1)
        self.count_label = QLabel("")
        self.count_label.setStyleSheet("color: #64748b; font-size: 11px;")
        head.addWidget(self.count_label)
        self.layout_.addLayout(head)
        self.hint = QLabel("")
        self.hint.setWordWrap(True)
        self.hint.setStyleSheet("color: #94a3b8; font-size: 10px;")


class ListEditor(_PanelBase):
    """값 목록을 보여주고 추가 / 이름 변경 / 삭제 / 순서 이동을 할 수 있는 패널."""

    changed = Signal(list)
    renamed = Signal(str, str)
    currentTextChanged = Signal(str)

    def __init__(self, editable=True, parent=None):
        super().__init__(parent)
        self.editable = editable
        self.confirm_text = None
        self._loading = False
        self._prev = []

        self.list = QListWidget()
        self.list.setStyleSheet(LIST_STYLE)
        self.list.currentTextChanged.connect(self._on_current_changed)
        self.list.itemChanged.connect(self._on_item_changed)
        self.list.itemDoubleClicked.connect(self._on_double_click)
        self.layout_.addWidget(self.list, 1)

        self.add_btn, self.up_btn, self.down_btn, self.delete_btn = _make_buttons()
        self.add_btn.clicked.connect(self._add)
        self.up_btn.clicked.connect(lambda: self._move(-1))
        self.down_btn.clicked.connect(lambda: self._move(1))
        self.delete_btn.clicked.connect(self._delete)
        self.layout_.addLayout(_button_row(self.add_btn, self.up_btn, self.down_btn, self.delete_btn))
        self.layout_.addWidget(self.hint)
        self.set_editable(editable)

    def set_editable(self, editable):
        self.editable = editable
        for btn in (self.add_btn, self.up_btn, self.down_btn, self.delete_btn):
            btn.setVisible(editable)
        self.hint.setText("항목을 두 번 클릭하면 이름을 고칠 수 있습니다." if editable else "")

    # ---------- 데이터 ----------
    def set_values(self, values, select=None):
        self._loading = True
        self.list.clear()
        for value in values:
            self._append_item(value)
        self._prev = list(values)
        self._loading = False
        self._update_count()
        if self.list.count():
            self.list.setCurrentRow(values.index(select) if select in values else 0)
        else:
            self.currentTextChanged.emit("")

    def values(self):
        return [self.list.item(i).text().strip() for i in range(self.list.count()) if self.list.item(i).text().strip()]

    def current_text(self):
        item = self.list.currentItem()
        return item.text().strip() if item else ""

    def _append_item(self, text):
        item = QListWidgetItem(text)
        flags = Qt.ItemIsEnabled | Qt.ItemIsSelectable
        if self.editable:
            flags |= Qt.ItemIsEditable
        item.setFlags(flags)
        self.list.addItem(item)
        return item

    def _update_count(self):
        self.count_label.setText(f"총 {self.list.count()}개")

    def _emit_changed(self):
        self._prev = [self.list.item(i).text().strip() for i in range(self.list.count())]
        self._update_count()
        self.changed.emit(self.values())

    # ---------- 이벤트 ----------
    def _on_current_changed(self, text):
        if not self._loading:
            self.currentTextChanged.emit(text.strip())

    def _on_double_click(self, item):
        if self.editable:
            self.list.editItem(item)

    def _on_item_changed(self, item):
        if self._loading or not self.editable:
            return
        row = self.list.row(item)
        new = item.text().strip()
        old = self._prev[row] if row < len(self._prev) else ""
        if not new:
            self._loading = True
            self.list.takeItem(row)
            self._loading = False
            self._emit_changed()
            return
        if new != old and old:
            self.renamed.emit(old, new)
        self._emit_changed()
        if item is self.list.currentItem():
            self.currentTextChanged.emit(new)

    def _add(self):
        item = self._append_item(NEW_ITEM_TEXT)
        self._prev.append("")
        self._update_count()
        self.list.setCurrentItem(item)
        self.list.editItem(item)

    def _delete(self):
        row = self.list.currentRow()
        if row < 0:
            return
        value = self.list.item(row).text().strip()
        message = self.confirm_text(value) if self.confirm_text else f"'{value}' 항목을 삭제할까요?"
        if QMessageBox.question(self, "삭제 확인", message) != QMessageBox.Yes:
            return
        self._loading = True
        self.list.takeItem(row)
        self._loading = False
        self._emit_changed()
        if self.list.count():
            self.list.setCurrentRow(min(row, self.list.count() - 1))
        else:
            self.currentTextChanged.emit("")

    def _move(self, direction):
        row = self.list.currentRow()
        target = row + direction
        if row < 0 or target < 0 or target >= self.list.count():
            return
        self._loading = True
        item = self.list.takeItem(row)
        self.list.insertItem(target, item)
        self.list.setCurrentRow(target)
        self._loading = False
        self._emit_changed()


class PersonEditor(_PanelBase):
    """소속 안의 담당자 목록: 이름(더블클릭으로 이름 변경) + 직급 드롭다운."""

    changed = Signal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.ranks = []
        self._loading = False

        self.table = QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels(["이름", "직급"])
        self.table.setStyleSheet(LIST_STYLE)
        self.table.verticalHeader().hide()
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.setColumnWidth(1, 130)
        self.table.itemChanged.connect(self._on_item_changed)
        self.layout_.addWidget(self.table, 1)

        self.add_btn, self.up_btn, self.down_btn, self.delete_btn = _make_buttons()
        self.add_btn.clicked.connect(self._add)
        self.up_btn.clicked.connect(lambda: self._move(-1))
        self.down_btn.clicked.connect(lambda: self._move(1))
        self.delete_btn.clicked.connect(self._delete)
        self.layout_.addLayout(_button_row(self.add_btn, self.up_btn, self.down_btn, self.delete_btn))
        self.hint.setText("이름을 두 번 클릭하면 이름을 고칠 수 있고, 오른쪽 드롭다운에서 직급을 고릅니다.")
        self.layout_.addWidget(self.hint)

    def set_people(self, people, ranks):
        self.ranks = list(ranks)
        self._loading = True
        self.table.setRowCount(0)
        for person in people:
            self._append_row(person["name"], person.get("rank", ""))
        self._loading = False
        self._update_count()

    def people(self):
        result = []
        for row in range(self.table.rowCount()):
            name = self.table.item(row, 0).text().strip()
            if name:
                combo = self.table.cellWidget(row, 1)
                rank = combo.currentText() if combo.currentText() != NO_RANK_TEXT else ""
                result.append({"name": name, "rank": rank})
        return result

    def _append_row(self, name, rank):
        row = self.table.rowCount()
        self.table.insertRow(row)
        self.table.setItem(row, 0, QTableWidgetItem(name))
        combo = QComboBox()
        combo.setStyleSheet(RANK_COMBO_STYLE)
        combo.addItems([NO_RANK_TEXT] + self.ranks)
        if rank and combo.findText(rank) < 0:
            combo.addItem(rank)
        combo.setCurrentText(rank if rank else NO_RANK_TEXT)
        combo.currentTextChanged.connect(lambda _t: self._emit())
        self.table.setCellWidget(row, 1, combo)
        return row

    def _update_count(self):
        self.count_label.setText(f"총 {self.table.rowCount()}명")

    def _emit(self):
        if self._loading:
            return
        self._update_count()
        self.changed.emit(self.people())

    def _on_item_changed(self, item):
        if self._loading or item.column() != 0:
            return
        if not item.text().strip():
            self._loading = True
            self.table.removeRow(item.row())
            self._loading = False
        self._emit()

    def _add(self):
        self._loading = True
        row = self._append_row(NEW_ITEM_TEXT, "")
        self._loading = False
        self._update_count()
        self.table.setCurrentCell(row, 0)
        self.table.editItem(self.table.item(row, 0))

    def _delete(self):
        row = self.table.currentRow()
        if row < 0:
            return
        name = self.table.item(row, 0).text().strip()
        if QMessageBox.question(self, "삭제 확인", f"'{name}' 담당자를 삭제할까요?") != QMessageBox.Yes:
            return
        self.table.removeRow(row)
        self._emit()

    def _move(self, direction):
        row = self.table.currentRow()
        target = row + direction
        if row < 0 or target < 0 or target >= self.table.rowCount():
            return
        people = self.people()
        if len(people) != self.table.rowCount():
            return
        people[row], people[target] = people[target], people[row]
        self.set_people(people, self.ranks)
        self.table.setCurrentCell(target, 0)
        self._emit()


class PricedEditor(_PanelBase):
    """항목 + 단가 목록: 이름/단가는 두 번 클릭해서 고치고, 추가 / 삭제 / 순서 이동을 할 수 있다."""

    changed = Signal(list)       # [{"name", "price"}, ...]
    renamed = Signal(str, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._loading = False
        self._prev = []

        self.table = QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels(["항목", "단가"])
        self.table.setStyleSheet(LIST_STYLE)
        self.table.verticalHeader().hide()
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.setColumnWidth(1, 120)
        self.table.itemChanged.connect(self._on_item_changed)
        self.layout_.addWidget(self.table, 1)

        self.add_btn, self.up_btn, self.down_btn, self.delete_btn = _make_buttons()
        self.add_btn.clicked.connect(self._add)
        self.up_btn.clicked.connect(lambda: self._move(-1))
        self.down_btn.clicked.connect(lambda: self._move(1))
        self.delete_btn.clicked.connect(self._delete)
        self.layout_.addLayout(_button_row(self.add_btn, self.up_btn, self.down_btn, self.delete_btn))
        self.hint.setText("항목 이름이나 단가를 두 번 클릭하면 고칠 수 있습니다. 단가는 숫자만 입력하세요.")
        self.layout_.addWidget(self.hint)

    def set_editable(self, editable):
        for btn in (self.add_btn, self.up_btn, self.down_btn, self.delete_btn):
            btn.setEnabled(editable)
        self.table.setEnabled(editable)

    @staticmethod
    def _price_text(price):
        number = parse_number(price)
        return f"{int(number):,}" if number == int(number) else f"{number:,}"

    def set_items(self, items):
        self._loading = True
        self.table.setRowCount(0)
        for item in items:
            self._append_row(item["name"], item.get("price", 0))
        self._prev = [item["name"] for item in items]
        self._loading = False
        self._update_count()

    def items(self):
        result = []
        for row in range(self.table.rowCount()):
            name = self.table.item(row, 0).text().strip()
            if name:
                number = parse_number(self.table.item(row, 1).text())
                result.append({"name": name, "price": int(number) if number == int(number) else number})
        return result

    def _append_row(self, name, price):
        row = self.table.rowCount()
        self.table.insertRow(row)
        self.table.setItem(row, 0, QTableWidgetItem(name))
        price_item = QTableWidgetItem(self._price_text(price))
        price_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.table.setItem(row, 1, price_item)
        return row

    def _update_count(self):
        self.count_label.setText(f"총 {self.table.rowCount()}개")

    def _emit(self):
        if self._loading:
            return
        self._prev = [self.table.item(r, 0).text().strip() for r in range(self.table.rowCount())]
        self._update_count()
        self.changed.emit(self.items())

    def _on_item_changed(self, item):
        if self._loading:
            return
        row = item.row()
        if item.column() == 0:
            new = item.text().strip()
            old = self._prev[row] if row < len(self._prev) else ""
            if not new:
                self._loading = True
                self.table.removeRow(row)
                self._loading = False
                self._emit()
                return
            if old and new != old:
                self.renamed.emit(old, new)
        else:
            text = item.text().replace(",", "").strip()
            try:
                float(text or 0)
            except ValueError:
                text = "0"
            self._loading = True
            item.setText(self._price_text(text or 0))
            self._loading = False
        self._emit()

    def _add(self):
        self._loading = True
        row = self._append_row(NEW_ITEM_TEXT, 0)
        self._loading = False
        self._prev.append("")
        self._update_count()
        self.table.setCurrentCell(row, 0)
        self.table.editItem(self.table.item(row, 0))

    def _delete(self):
        row = self.table.currentRow()
        if row < 0:
            return
        name = self.table.item(row, 0).text().strip()
        message = f"'{name}' 항목을 삭제할까요?\n이미 이 항목을 고른 공정에는 이름만 남고 금액은 0으로 계산됩니다."
        if QMessageBox.question(self, "삭제 확인", message) != QMessageBox.Yes:
            return
        self.table.removeRow(row)
        self._emit()

    def _move(self, direction):
        row = self.table.currentRow()
        target = row + direction
        if row < 0 or target < 0 or target >= self.table.rowCount():
            return
        items = self.items()
        if len(items) != self.table.rowCount():
            return
        items[row], items[target] = items[target], items[row]
        self.set_items(items)
        self.table.setCurrentCell(target, 0)
        self._emit()


class FixedValuesScreen(QWidget):
    def __init__(self, state, parent=None):
        super().__init__(parent)
        self.state = state
        self.category = None
        self._parent_values = []

        outer = QVBoxLayout(self)
        outer.setContentsMargins(4, 4, 4, 4)
        outer.setSpacing(10)

        self.title_label = QLabel("")
        self.title_label.setStyleSheet("color: #000000; font-weight: 700; font-size: 14px;")
        outer.addWidget(self.title_label)

        body = QHBoxLayout()
        body.setSpacing(14)
        self.parent_editor = ListEditor(editable=True)
        self.parent_editor.currentTextChanged.connect(self._on_parent_selected)
        self.parent_editor.changed.connect(self._on_parent_changed)
        self.parent_editor.renamed.connect(self._on_parent_renamed)
        self.child_editor = ListEditor(editable=True)
        self.child_editor.changed.connect(self._on_child_changed)
        self.person_editor = PersonEditor()
        self.person_editor.changed.connect(self._on_people_changed)
        self.priced_editor = PricedEditor()
        self.priced_editor.changed.connect(self._on_priced_changed)
        self.priced_editor.renamed.connect(self._on_priced_renamed)
        body.addWidget(self.parent_editor, 4)
        body.addWidget(self.child_editor, 5)
        body.addWidget(self.person_editor, 5)
        body.addWidget(self.priced_editor, 5)

        info = QFrame()
        info.setObjectName("fvCard")
        info.setStyleSheet(CARD_STYLE)
        info_layout = QVBoxLayout(info)
        info_layout.setContentsMargins(16, 14, 16, 14)
        info_layout.setSpacing(8)
        heading = QLabel("사용처")
        heading.setStyleSheet("font-weight: 700; color: #000000; font-size: 13px;")
        info_layout.addWidget(heading)
        self.usage_label = QLabel("")
        self.usage_label.setWordWrap(True)
        self.usage_label.setStyleSheet("color: #334155; font-size: 12px;")
        info_layout.addWidget(self.usage_label)
        note = QLabel("여기서 고친 내용은 바로 저장되며, 1-1 MASTER 정보 기입의 드롭다운에 바로 반영됩니다.\n\n"
                      "엑셀 마스터의 NameList 시트와는 자동으로 맞춰지지 않습니다.")
        note.setWordWrap(True)
        note.setStyleSheet("color: #64748b; font-size: 11px;")
        info_layout.addWidget(note)
        info_layout.addStretch(1)
        body.addWidget(info, 3)
        outer.addLayout(body, 1)

    # ---------- 카테고리 ----------
    def set_category(self, category_id):
        self.category = cat = CATEGORIES[category_id]
        mode = cat["mode"]
        self.title_label.setText(f"고정값 - {cat['label']}")
        self.usage_label.setText(cat["usage"])

        is_persons = mode == "persons"
        is_priced = mode.startswith("priced")
        self.person_editor.setVisible(is_persons)
        self.priced_editor.setVisible(is_priced)
        self.child_editor.setVisible(not is_persons and not is_priced)
        self.parent_editor.setVisible(mode != "simple")
        self.parent_editor.confirm_text = None

        if mode == "simple":
            self.child_editor.title.setText(cat["child_title"])
            self.child_editor.set_editable(True)
            self.child_editor.set_values(self.state.fixed_list(cat["child_key"]))
            return

        self.parent_editor.title.setText(cat["parent_title"])
        if mode == "grouped":
            self._parent_values = list(self.state.fixed_list(cat["parent_key"]))
            self.parent_editor.set_editable(True)
            self.parent_editor.confirm_text = self._confirm_grouped_delete
            values = self._parent_values
        elif mode == "groups_fixed":
            self.parent_editor.set_editable(False)
            values = [label for label, _ in cat["groups"]]
        elif mode == "groups_editable":
            self.parent_editor.set_editable(True)
            self.parent_editor.confirm_text = self._confirm_group_delete
            values = [g["label"] for g in self.state.fixed_groups(cat["store"], cat["groups"])]
        elif mode == "derived":
            self.parent_editor.set_editable(False)
            values = list(self.state.fixed_list(cat["parent_source"]))
        elif mode == "priced_fixed":
            self.parent_editor.set_editable(False)
            values = [label for label, _ in cat["groups"]]
        elif mode == "priced_editable":
            self.parent_editor.set_editable(True)
            self.parent_editor.confirm_text = self._confirm_equip_delete
            values = list(self.state.fixed_values.setdefault("Equip", {}))
        else:  # persons
            self.parent_editor.set_editable(True)
            self.parent_editor.confirm_text = self._confirm_person_team_delete
            values = list(self.state.fixed_values.setdefault("Persons", {}))
        self.parent_editor.set_values(values)

    def _child_key(self, parent_text):
        cat = self.category
        mode = cat["mode"]
        if not parent_text:
            return None
        if mode in ("grouped", "derived"):
            return cat["child_key"].format(parent_text)
        if mode == "groups_fixed":
            return next((key for label, key in cat["groups"] if label == parent_text), None)
        if mode == "groups_editable":
            groups = self.state.fixed_groups(cat["store"], cat["groups"])
            return next((g["key"] for g in groups if g["label"] == parent_text), None)
        return None

    def _priced_store(self, group):
        if not group:
            return None
        return self.state.fixed_values.setdefault(self.category["store"], {}).get(group)

    def _on_parent_selected(self, text):
        cat = self.category
        mode = cat["mode"]
        if mode.startswith("priced"):
            store = self._priced_store(text)
            self.priced_editor.title.setText(text)
            self.priced_editor.set_editable(store is not None)
            self.priced_editor.set_items(store or [])
            return
        if mode == "persons":
            self.person_editor.title.setText(f"담당자 - {text}" if text else "담당자")
            people = self.state.persons(text) if text else []
            self.person_editor.set_people(people, self.state.fixed_list("Rank"))
            return
        key = self._child_key(text)
        if mode in ("grouped", "derived"):
            self.child_editor.title.setText(f"{cat['child_title']} - {text}" if text else cat["child_title"])
        else:
            self.child_editor.title.setText(text)
        self.child_editor.set_editable(bool(key))
        self.child_editor.set_values(self.state.fixed_list(key) if key else [])

    def _on_child_changed(self, values):
        key = self._child_key(self.parent_editor.current_text()) if not self.parent_editor.isHidden() else self.category["child_key"]
        if key:
            self.state.set_fixed_list(key, values)

    def _on_priced_changed(self, items):
        group = self.parent_editor.current_text()
        if group:
            self.state.fixed_values.setdefault(self.category["store"], {})[group] = items
            self.state.save()

    def _on_priced_renamed(self, old, new):
        group = self.parent_editor.current_text()
        if self.category["mode"] == "priced_fixed":
            mc.rename_jig_item(self.state, group, old, new)
        else:
            mc.rename_equip_item(self.state, group, old, new)
        self.state.save()

    def _confirm_equip_delete(self, value):
        count = len(self.state.fixed_values.get("Equip", {}).get(value, []))
        return f"'{value}' 설비 종류와 그 안의 설비 {count}개를 함께 삭제할까요?" if count else f"'{value}' 설비 종류를 삭제할까요?"

    def _on_people_changed(self, people):
        team = self.parent_editor.current_text()
        if team:
            self.state.fixed_values.setdefault("Persons", {})[team] = people
            self.state.save()

    # ---------- 상위 목록 편집 ----------
    def _confirm_grouped_delete(self, value):
        children = self.state.fixed_list(self.category["child_key"].format(value))
        if children:
            return f"'{value}'와(과) 그 아래 {self.category['child_title']} {len(children)}개를 함께 삭제할까요?"
        return f"'{value}' 항목을 삭제할까요?"

    def _confirm_group_delete(self, value):
        return f"'{value}' 목록을 삭제할까요?\n이 목록을 쓰는 화면의 드롭다운에서도 사라집니다."

    def _confirm_person_team_delete(self, value):
        count = len(self.state.persons(value))
        return f"'{value}' 소속과 담당자 {count}명을 함께 삭제할까요?" if count else f"'{value}' 소속을 삭제할까요?"

    def _on_parent_renamed(self, old, new):
        cat = self.category
        mode = cat["mode"]
        fv = self.state.fixed_values
        if mode == "grouped":
            old_key, new_key = cat["child_key"].format(old), cat["child_key"].format(new)
            if old_key in fv and new_key not in fv:
                fv[new_key] = fv.pop(old_key)
            self._parent_values = [new if v == old else v for v in self._parent_values]
        elif mode == "groups_editable":
            for group in self.state.fixed_groups(cat["store"], cat["groups"]):
                if group["label"] == old:
                    group["label"] = new
            self.state.save()
        elif mode == "priced_editable":
            equip = fv.setdefault("Equip", {})
            fv["Equip"] = {(new if label == old else label): items for label, items in equip.items()}
            mc.rename_equip_group(self.state, old, new)
            self.state.save()
        elif mode == "persons":
            persons = fv.setdefault("Persons", {})
            fv["Persons"] = {(new if team == old else team): people for team, people in persons.items()}
            teams = self.state.fixed_list("Team")
            if old in teams and new not in teams:
                teams[teams.index(old)] = new
            self.state.save()

    def _on_parent_changed(self, values):
        cat = self.category
        mode = cat["mode"]
        fv = self.state.fixed_values
        if mode == "grouped":
            for removed in set(self._parent_values) - set(values):
                fv.pop(cat["child_key"].format(removed), None)
            self._parent_values = list(values)
            self.state.set_fixed_list(cat["parent_key"], values)
        elif mode == "groups_editable":
            entries = self.state.fixed_groups(cat["store"], cat["groups"])
            by_label = {g["label"]: g for g in entries}
            new_entries = [by_label.pop(v, None) or {"label": v, "key": f"custom_{uuid.uuid4().hex[:8]}"} for v in values]
            for dropped in by_label.values():
                if dropped["key"].startswith("custom_"):
                    fv.pop(dropped["key"], None)
            entries[:] = new_entries
            self.state.save()
        elif mode == "priced_editable":
            equip = fv.setdefault("Equip", {})
            fv["Equip"] = {label: equip.get(label, []) for label in values}
            self.state.save()
        elif mode == "persons":
            persons = fv.setdefault("Persons", {})
            fv["Persons"] = {team: persons.get(team, []) for team in values}
            teams = self.state.fixed_list("Team")
            for team in values:
                if team not in teams:
                    teams.append(team)
            self.state.save()
