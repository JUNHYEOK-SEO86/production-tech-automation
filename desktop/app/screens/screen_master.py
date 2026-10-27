"""1-1. MASTER 정보 기입

마스터 입력폼(I. 프로젝트 관리 / II. 라인 관리 / III. 공법 설계 / IV. 공정 관리)의 정보를 ITEM 1개 기준으로 직접 기입한다.
입력한 내용은 바로 저장된다. 입력창 오른쪽 끝의 손잡이나 표 머리글 경계를 끌면 길이/너비를 조절할 수 있다.
"""
from datetime import datetime

from PySide6.QtCore import QRegularExpression, Qt
from PySide6.QtGui import QRegularExpressionValidator
from PySide6.QtWidgets import (
    QComboBox, QFrame, QGridLayout, QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPushButton,
    QScrollArea, QSizePolicy, QTabWidget, QVBoxLayout, QWidget,
)

from app.state import EFF_CHOICES, required_ct
from app.widgets.form_widgets import DateLineEdit, FormTable, cell, make_resizable
from app.screens.screen_method import MethodDesignTab
from app.screens.ui_common import (
    COMBO_STYLE, DEL_BTN, FIELD_LABEL, HEADER_LABEL, HINT_LABEL, INPUT_STYLE, PRIMARY_BTN, SUB_BTN, TAB_STYLE,
    _label, card,
)


class MasterInfoScreen(QWidget):
    def __init__(self, state, parent=None):
        super().__init__(parent)
        self.state = state
        self._loading = False
        self._bindings = []
        self._list_combos = []
        self._need_ct_edits = []

        outer = QVBoxLayout(self)
        outer.setContentsMargins(4, 4, 4, 4)
        outer.setSpacing(6)

        top = QHBoxLayout()
        self.title_label = _label("", "color: #000000; font-weight: 700; font-size: 14px;")
        top.addWidget(self.title_label)
        top.addStretch(1)
        self.saved_label = _label("", "color: #059669; font-size: 11px; font-weight: 600;")
        top.addWidget(self.saved_label)
        outer.addLayout(top)

        self.tabs = QTabWidget()
        self.tabs.setStyleSheet(TAB_STYLE)
        self.tabs.addTab(self._scrolled(self._build_project_tab()), "I. 프로젝트 관리")
        self.tabs.addTab(self._scrolled(self._build_line_tab()), "II. 라인 관리")
        self.method_tab = MethodDesignTab(self.state)
        self._method_scroll = self._scrolled(self.method_tab)
        self.tabs.addTab(self._method_scroll, "III. 공법 설계")
        self.tabs.addTab(self._scrolled(self._build_process_tab()), "IV. 공정 관리")
        self.tabs.currentChanged.connect(self._on_tab_changed)
        outer.addWidget(self.tabs, 1)

    # ---------------- 공통 도우미 ----------------
    @staticmethod
    def _scrolled(widget):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        scroll.setWidget(widget)
        return scroll

    @staticmethod
    def _card(title):
        return card(title)

    def _on_tab_changed(self, _index):
        """다른 탭에서 바꾼 공정/라인/고정값이 공법 설계에 보이도록 탭을 열 때 새로 읽는다."""
        if self.tabs.widget(_index) is self._method_scroll:
            self.method_tab.refresh()

    @property
    def names(self):
        return self.state.fixed_values

    def _info(self):
        return self.state.master_info()

    def _get(self, path):
        node = self._info()
        for key in path:
            node = node[key]
        return node

    def _set(self, path, value):
        node = self._info()
        for key in path[:-1]:
            node = node[key]
        node[path[-1]] = value
        self._save()

    def _save(self):
        self.state.save()
        self.saved_label.setText(f"자동 저장됨 · {datetime.now().strftime('%H:%M:%S')}")

    def _edit(self, path, placeholder="", readonly=False):
        edit = QLineEdit()
        edit.setStyleSheet(INPUT_STYLE)
        edit.setPlaceholderText(placeholder)
        edit.setReadOnly(readonly)
        edit.setProperty("field_key", "/".join(str(p) for p in path))
        edit.editingFinished.connect(lambda e=edit, p=path: self._on_edit(e, p))
        self._bindings.append((edit, path))
        return edit

    def _combo(self, path, list_key=None, editable=True):
        combo = QComboBox()
        combo.setEditable(editable)
        combo.setStyleSheet(COMBO_STYLE)
        combo.setProperty("field_key", "/".join(str(p) for p in path))
        if list_key:
            combo.addItems(self.names.get(list_key, []))
            self._list_combos.append((combo, list_key))
        combo.setCurrentIndex(-1)
        combo.activated.connect(lambda _i, c=combo, p=path: self._on_combo(c, p))
        if editable:
            combo.lineEdit().editingFinished.connect(lambda c=combo, p=path: self._on_combo(c, p))
        self._bindings.append((combo, path))
        return combo

    @staticmethod
    def _set_combo_text(combo, text):
        if combo.isEditable():
            combo.setEditText(text)
        else:
            combo.setCurrentIndex(combo.findText(text))

    @classmethod
    def _set_items(cls, combo, items):
        text = combo.currentText()
        combo.blockSignals(True)
        combo.clear()
        combo.addItems(list(items))
        cls._set_combo_text(combo, text)
        combo.blockSignals(False)

    def _resizable(self, widget, default_width=None):
        key = widget.property("field_key")
        return make_resizable(widget, self.state, f"field:{key}", default_width) if key else widget

    def _after_value_change(self, path):
        if path[0] == "line_condition":
            self._recompute_need_ct()

    def _on_edit(self, edit, path):
        if self._loading:
            return
        self._set(path, edit.text().strip())
        self._after_value_change(path)

    def _on_combo(self, combo, path):
        if self._loading:
            return
        value = combo.currentText().strip()
        if value == self._get(path):
            return
        self._set(path, value)
        self._after_value_change(path)
        if path == ("project", "item"):
            self._set(("project", "item_class"), "")
            self._refresh_item_class_items()
            self.item_class_combo.setEditText("")
        elif path == ("report", "team"):
            self._set(("report", "person"), "")
            self._set(("report", "rank"), "")
            self._refresh_person_items()
            self.person_combo.setEditText("")
            self._set_combo_text(self.rank_combo, "")
        elif path == ("report", "person"):
            team = self._info()["report"]["team"]
            rank = next((p["rank"] for p in self.state.persons(team) if p["name"] == value and p.get("rank")), "")
            if rank:
                self._set(("report", "rank"), rank)
                self._set_combo_text(self.rank_combo, rank)

    def _grid_fields(self, grid, fields, columns=2):
        """[(라벨, 위젯), ...]을 라벨/입력 쌍으로 columns 개씩 나란히 배치한다. 입력창은 길이를 조절할 수 있다."""
        for index, (text, widget) in enumerate(fields):
            row, col = divmod(index, columns)
            grid.addWidget(_label(text), row, col * 2)
            grid.addWidget(self._resizable(widget), row, col * 2 + 1)
            grid.setColumnStretch(col * 2 + 1, 1)

    def _stack_fields(self, grid, fields, default_width=None, columns=2):
        """라벨을 입력창 위에 놓는 배치 (라벨이 길어도 잘리지 않는다)."""
        for index, (text, widget) in enumerate(fields):
            row, col = divmod(index, columns)
            grid.addWidget(_label(text), row * 2, col)
            holder = widget if widget.property("field_key") is None else self._resizable(widget, default_width)
            grid.addWidget(holder, row * 2 + 1, col, Qt.AlignLeft)

    # ---------------- 화면 갱신 ----------------
    def refresh(self):
        self._loading = True
        info = self._info()
        self.title_label.setText(f"MASTER 정보 기입 - {self.state.current_item}")

        for combo, key in self._list_combos:
            self._set_items(combo, self.names.get(key, []))
        self._refresh_item_class_items()
        self._refresh_person_items()
        for widget, path in self._bindings:
            value = self._get(path)
            if isinstance(widget, QComboBox):
                self._set_combo_text(widget, str(value))
            else:
                widget.setText(str(value))

        self._rebuild_history()
        self._rebuild_lines()
        self._rebuild_work_conditions()
        self._refresh_proc_line_combo()
        self._rebuild_processes()
        self.method_tab.refresh()
        self.line_count_label.setText(str(len(info["lines"])))
        self._loading = False

    def _refresh_item_class_items(self):
        item = self._info()["project"]["item"]
        self._set_items(self.item_class_combo, self.names.get(f"{item}_품명", []))

    def _refresh_person_items(self):
        team = self._info()["report"]["team"]
        self._set_items(self.person_combo, [p["name"] for p in self.state.persons(team)])

    def _update_recent_eo(self):
        info = self._info()
        for hist_key, recent_key, edit in (("weld_history", "weld_eo", self.weld_eo_edit),
                                           ("asm_history", "asm_eo", self.asm_eo_edit)):
            latest = next((r["eo"] for r in reversed(info[hist_key]) if r["eo"] and r["eo"] != "-"), "")
            if latest != info["recent"][recent_key]:
                info["recent"][recent_key] = latest
                edit.setText(latest)
        self._save()

    # ---------------- I. 프로젝트 관리 ----------------
    def _build_project_tab(self):
        page = QWidget()
        outer = QHBoxLayout(page)
        outer.setContentsMargins(4, 8, 4, 8)
        outer.setSpacing(14)
        left, right = QVBoxLayout(), QVBoxLayout()
        left.setSpacing(12)
        right.setSpacing(12)

        card, lay = self._card("Project Information")
        grid = QGridLayout()
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(8)
        self.item_combo = self._combo(("project", "item"), "Item")
        self.item_class_combo = self._combo(("project", "item_class"))
        self.step_combo = self._combo(("project", "step"), "DesStep")
        self._grid_fields(grid, [
            ("고 객 :", self._edit(("project", "customer"))),
            ("품 번 :", self._edit(("project", "part_no"))),
            ("아이템 :", self.item_combo),
            ("아이템구분 :", self.item_class_combo),
            ("차 종 :", self._edit(("project", "car"))),
            ("아이템명 :", self._edit(("project", "item_name"))),
            ("단 계 :", self.step_combo),
        ])
        lay.addLayout(grid)
        left.addWidget(card)

        card, lay = self._card("Report Information")
        grid = QGridLayout()
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(8)
        self.team_combo = self._combo(("report", "team"), "Team")
        self.person_combo = self._combo(("report", "person"))
        self.rank_combo = self._combo(("report", "rank"), "Rank", editable=False)
        self.rev_combo = self._combo(("report", "rev"), "Rev", editable=False)
        self._grid_fields(grid, [
            ("팀 명 :", self.team_combo),
            ("담 당 :", self.person_combo),
            ("직 급 :", self.rank_combo),
            ("Rev. :", self.rev_combo),
        ])
        lay.addLayout(grid)
        left.addWidget(card)

        card, lay = self._card("Recent History")
        grid = QGridLayout()
        grid.setHorizontalSpacing(10)
        self.weld_eo_edit = self._edit(("recent", "weld_eo"), "-")
        self.asm_eo_edit = self._edit(("recent", "asm_eo"), "-")
        self._grid_fields(grid, [("용접 EO No. :", self.weld_eo_edit), ("조립 EO No. :", self.asm_eo_edit)])
        lay.addLayout(grid)
        lay.addWidget(_label("개정 이력(오른쪽)에 입력하면 가장 최근 EO No.가 자동으로 채워집니다.", HINT_LABEL))
        left.addWidget(card)

        update_btn = QPushButton("Update (저장)")
        update_btn.setStyleSheet(PRIMARY_BTN)
        update_btn.clicked.connect(self._on_update)
        left.addWidget(update_btn, 0, Qt.AlignLeft)
        left.addStretch(1)

        self.history_tables = {}
        for title, hist_key in (("Welding History", "weld_history"), ("Assembly History", "asm_history")):
            card, lay = self._card(title)
            table = FormTable(self.state, hist_key, ["", "개정일자", "EO No.", "내 역", "삭제"], [36, 130, 130, 200, 70])
            lay.addWidget(table)
            add_row_btn = QPushButton("+ 칸 추가")
            add_row_btn.setStyleSheet(SUB_BTN)
            add_row_btn.clicked.connect(lambda _c=False, k=hist_key: self._add_history_row(k))
            lay.addWidget(add_row_btn, 0, Qt.AlignLeft)
            lay.addWidget(_label("개정일자는 숫자만 입력하면 0000.00.00 형태로 점이 자동으로 들어갑니다.", HINT_LABEL))
            self.history_tables[hist_key] = table
            right.addWidget(card)
        right.addStretch(1)

        outer.addLayout(left, 5)
        outer.addLayout(right, 6)
        return page

    def _rebuild_history(self):
        for hist_key, table in self.history_tables.items():
            rows = self._info()[hist_key]
            table.set_rows(len(rows))
            for index, row in enumerate(rows):
                table.setCellWidget(index, 0, cell(_label(str(index + 1), HEADER_LABEL)))
                for col, key in enumerate(("date", "eo", "note"), start=1):
                    edit = DateLineEdit() if key == "date" else QLineEdit()
                    edit.setStyleSheet(INPUT_STYLE)
                    edit.setText(row[key])
                    edit.editingFinished.connect(lambda r=row, k=key, e=edit: self._on_history_edit(r, k, e.text()))
                    table.setCellWidget(index, col, cell(edit))
                table.setCellWidget(index, 4, self._delete_button(lambda _c=False, k=hist_key, r=row: self._delete_history_row(k, r)))

    def _on_history_edit(self, row, key, value):
        if self._loading:
            return
        value = value.strip()
        if row[key] == value:
            return
        row[key] = value
        self._update_recent_eo()

    def _add_history_row(self, hist_key):
        self._info()[hist_key].append({"date": "", "eo": "", "note": ""})
        self._save()
        self._rebuild_history()

    def _delete_history_row(self, hist_key, row):
        if any(row[k] for k in ("date", "eo", "note")):
            if QMessageBox.question(self, "삭제 확인", "이 개정 이력 줄을 삭제할까요?") != QMessageBox.Yes:
                return
        self._info()[hist_key].remove(row)
        self._save()
        self._rebuild_history()
        self._update_recent_eo()

    def _on_update(self):
        self._save()
        QMessageBox.information(self, "저장 완료", f"'{self.state.current_item}'의 MASTER 정보가 저장되었습니다.")

    def _delete_button(self, handler):
        button = QPushButton("삭제")
        button.setStyleSheet(DEL_BTN)
        button.setFixedWidth(52)
        button.clicked.connect(handler)
        return cell(button, Qt.AlignLeft)

    # ---------------- II. 라인 관리 ----------------
    def _build_line_tab(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(4, 8, 4, 8)
        layout.setSpacing(12)

        card, lay = self._card("Line Condition")
        grid = QGridLayout()
        grid.setHorizontalSpacing(28)
        grid.setVerticalSpacing(4)
        qty_edit = self._edit(("line_condition", "qty_man"), "예: 9.0")
        qty_row = QWidget()
        qty_layout = QHBoxLayout(qty_row)
        qty_layout.setContentsMargins(0, 0, 0, 0)
        qty_layout.addWidget(self._resizable(qty_edit, 150))
        qty_layout.addWidget(_label("만대"))
        qty_layout.addStretch(1)
        self._stack_fields(grid, [
            ("생산대 (고객 생산대수)", qty_row),
            ("설치장소", self._combo(("line_condition", "site"), "설치장소")),
            ("용접 근무조", self._combo(("line_condition", "weld_shift"), "Shift")),
            ("조립 근무조", self._combo(("line_condition", "asm_shift"), "Shift")),
        ], default_width=150, columns=4)
        grid.setColumnStretch(4, 1)
        lay.addLayout(grid)
        layout.addWidget(card)

        card, lay = self._card("근무 조건")
        top = QHBoxLayout()
        top.addWidget(_label("설치장소별 근무일 / 근무시간 / 라인효율 (필요 C/T 계산에 사용)", HINT_LABEL))
        top.addStretch(1)
        add_site_btn = QPushButton("+ 설치장소 추가")
        add_site_btn.setStyleSheet(PRIMARY_BTN)
        add_site_btn.clicked.connect(self._add_work_condition)
        top.addWidget(add_site_btn)
        lay.addLayout(top)
        self.control_table = FormTable(
            self.state, "work", ["설치장소", "근무일 (일/년)", "근무시간 (HR/일)", "라인효율 (%)", "삭제"],
            [170, 150, 160, 150, 70],
        )
        lay.addWidget(self.control_table)
        lay.addWidget(_label("라인효율은 60%~100% 중에서 선택합니다. Line Condition의 설치장소와 같은 행이 필요 C/T 계산에 쓰입니다.", HINT_LABEL))
        layout.addWidget(card)

        card, lay = self._card("Line List")
        count_row = QHBoxLayout()
        count_row.addWidget(_label("Number of Line :"))
        self.line_count_label = _label("0", "color: #000000; font-weight: 700; font-size: 12px;")
        count_row.addWidget(self.line_count_label)
        count_row.addStretch(1)
        add_btn = QPushButton("+ 라인 추가")
        add_btn.setStyleSheet(PRIMARY_BTN)
        add_btn.clicked.connect(self._add_line)
        count_row.addWidget(add_btn)
        lay.addLayout(count_row)

        self.lines_table = FormTable(
            self.state, "lines",
            ["구분", "라인명", "필요 C/T (초/대)", "Line C/T", "주간인", "야간인", "삭제"],
            [120, 260, 150, 100, 90, 90, 70],
        )
        lay.addWidget(self.lines_table)
        self.ct_hint = _label("", HINT_LABEL)
        self.ct_hint.setWordWrap(True)
        lay.addWidget(self.ct_hint)
        layout.addWidget(card)
        layout.addStretch(1)
        return page

    # ----- 근무 조건 (설치장소 행 추가/삭제) -----
    def _rebuild_work_conditions(self):
        rows = self._info()["work_conditions"]
        self.control_table.set_rows(len(rows))
        for index, row in enumerate(rows):
            site = QComboBox()
            site.setEditable(True)
            site.setStyleSheet(COMBO_STYLE)
            site.addItems(self.names.get("설치장소", []))
            site.setEditText(row["site"])
            site.activated.connect(lambda _i, r=row, c=site: self._on_work_field(r, "site", c.currentText()))
            site.lineEdit().editingFinished.connect(lambda r=row, c=site: self._on_work_field(r, "site", c.currentText()))
            self.control_table.setCellWidget(index, 0, cell(site))

            for col, key in ((1, "days"), (2, "hours")):
                edit = QLineEdit(row[key])
                edit.setStyleSheet(INPUT_STYLE)
                edit.editingFinished.connect(lambda r=row, k=key, e=edit: self._on_work_field(r, k, e.text()))
                self.control_table.setCellWidget(index, col, cell(edit))

            eff = QComboBox()
            eff.setStyleSheet(COMBO_STYLE)
            eff.addItems(EFF_CHOICES)
            eff.setCurrentIndex(eff.findText(row["eff"]))
            eff.activated.connect(lambda _i, r=row, c=eff: self._on_work_field(r, "eff", c.currentText()))
            self.control_table.setCellWidget(index, 3, cell(eff))

            self.control_table.setCellWidget(index, 4, self._delete_button(lambda _c=False, r=row: self._delete_work_condition(r)))

    def _on_work_field(self, row, key, value):
        if self._loading:
            return
        value = value.strip()
        if row[key] == value:
            return
        row[key] = value
        self._save()
        self._recompute_need_ct()

    def _add_work_condition(self):
        self._info()["work_conditions"].append({"site": "", "days": "", "hours": "", "eff": ""})
        self._save()
        self._rebuild_work_conditions()

    def _delete_work_condition(self, row):
        label = row["site"] or "이 행"
        if any(row[k] for k in ("days", "hours", "eff")):
            if QMessageBox.question(self, "삭제 확인", f"'{label}' 근무 조건을 삭제할까요?") != QMessageBox.Yes:
                return
        self._info()["work_conditions"].remove(row)
        self._save()
        self._rebuild_work_conditions()
        self._recompute_need_ct()

    # ----- 필요 C/T / Line List -----
    def _recompute_need_ct(self):
        """필요 C/T = 3600 x 근무시간(HR/일) x 라인효율 x 근무일(일/년) / 고객 생산대수"""
        info = self._info()
        value = required_ct(info)
        text = f"{value:.1f}" if value else ""
        for row in info["lines"]:
            row["need_ct"] = text
        for edit in self._need_ct_edits:
            edit.setText(text)
        if value:
            self.ct_hint.setText("필요 C/T = 3600초/시간 × 근무시간(HR/일) × 라인효율 × 근무일(일/년) ÷ 고객 생산대수  (자동 계산)")
        else:
            self.ct_hint.setText("생산대, 설치장소, 해당 설치장소의 근무 조건(근무일, 근무시간, 라인효율)을 모두 입력하면 필요 C/T가 자동으로 계산됩니다.")
        self.state.save()

    def _add_line(self):
        self._info()["lines"].append({"kind": "", "name": "", "need_ct": "", "line_ct": "", "day": "", "night": ""})
        self._save()
        self._rebuild_lines()
        self._refresh_proc_line_combo()
        self._rebuild_processes()
        self.line_count_label.setText(str(len(self._info()["lines"])))

    def _rebuild_lines(self):
        lines = self._info()["lines"]
        self._need_ct_edits = []
        self.lines_table.set_rows(len(lines))
        for index, row in enumerate(lines):
            kind = QComboBox()
            kind.setEditable(True)
            kind.setStyleSheet(COMBO_STYLE)
            kind.addItems(self.names.get("Line", []))
            kind.setEditText(row.get("kind", ""))
            kind.activated.connect(lambda _i, r=row, c=kind: self._on_line_field(r, "kind", c.currentText()))
            kind.lineEdit().editingFinished.connect(lambda r=row, c=kind: self._on_line_field(r, "kind", c.currentText()))
            self.lines_table.setCellWidget(index, 0, cell(kind))

            name = QLineEdit(row.get("name", ""))
            name.setStyleSheet(INPUT_STYLE)
            name.editingFinished.connect(lambda r=row, e=name: self._on_line_field(r, "name", e.text()))
            self.lines_table.setCellWidget(index, 1, cell(name))

            need = QLineEdit(row.get("need_ct", ""))
            need.setReadOnly(True)
            need.setStyleSheet(INPUT_STYLE)
            need.setToolTip("자동 계산 (수정 불가)")
            self._need_ct_edits.append(need)
            self.lines_table.setCellWidget(index, 2, cell(need))

            for col, key in ((3, "line_ct"), (4, "day"), (5, "night")):
                edit = QLineEdit(row.get(key, ""))
                edit.setStyleSheet(INPUT_STYLE)
                edit.editingFinished.connect(lambda r=row, k=key, e=edit: self._on_line_field(r, k, e.text()))
                self.lines_table.setCellWidget(index, col, cell(edit))

            self.lines_table.setCellWidget(index, 6, self._delete_button(lambda _c=False, r=row: self._delete_line(r)))
        self._recompute_need_ct()

    def _on_line_field(self, row, key, value):
        if self._loading:
            return
        value = value.strip()
        old = row.get(key, "")
        if value == old:
            return
        row[key] = value
        selected = self.proc_line_combo.currentText()
        if key == "name":
            for proc in self._info()["processes"]:
                if proc["line"] == old:
                    proc["line"] = value
            if selected == old:
                selected = value
        self._save()
        if key in ("name", "kind"):
            self._refresh_proc_line_combo(selected)
            self._rebuild_processes()

    def _delete_line(self, row):
        info = self._info()
        owned = [p for p in info["processes"] if row.get("name") and p["line"] == row["name"]]
        if owned:
            reply = QMessageBox.question(
                self, "라인 삭제",
                f"'{row['name']}' 라인에 등록된 공정 {len(owned)}개도 함께 삭제됩니다. 삭제할까요?",
            )
            if reply != QMessageBox.Yes:
                return
            info["processes"] = [p for p in info["processes"] if p not in owned]
        info["lines"].remove(row)
        self._save()
        self._rebuild_lines()
        self._refresh_proc_line_combo()
        self._rebuild_processes()
        self.line_count_label.setText(str(len(info["lines"])))

    # ---------------- IV. 공정 관리 ----------------
    def _build_process_tab(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(4, 8, 4, 8)
        layout.setSpacing(12)

        card, lay = self._card("Process")
        row = QHBoxLayout()
        row.setSpacing(10)
        row.addWidget(_label("라인 선택 :"))
        self.proc_line_combo = QComboBox()
        self.proc_line_combo.setStyleSheet(COMBO_STYLE)
        self.proc_line_combo.setMinimumWidth(240)
        self.proc_line_combo.activated.connect(lambda _i: self._on_proc_line_selected())
        row.addWidget(self.proc_line_combo)
        row.addSpacing(10)
        row.addWidget(_label("공정 수 :"))
        self.proc_count_edit = QLineEdit("1")
        # 1~20만 입력되도록 (21 이상 숫자는 아예 입력되지 않는다)
        self.proc_count_edit.setValidator(QRegularExpressionValidator(QRegularExpression(r"^(20|1[0-9]|[1-9])?$"), self))
        self.proc_count_edit.setAlignment(Qt.AlignCenter)
        self.proc_count_edit.setFixedWidth(56)
        self.proc_count_edit.setStyleSheet(INPUT_STYLE)
        row.addWidget(self.proc_count_edit)
        row.addWidget(_label("최대 20개까지 한 번에 추가", HINT_LABEL))
        add_btn = QPushButton("추가")
        add_btn.setStyleSheet(PRIMARY_BTN)
        add_btn.clicked.connect(self._add_processes)
        row.addWidget(add_btn)
        row.addStretch(1)
        lay.addLayout(row)
        lay.addWidget(_label("라인을 선택하고 공정 수를 적은 뒤 [추가]를 누르면 그 라인에 빈 줄이 생깁니다. (라인은 II. 라인 관리에서 먼저 추가)", HINT_LABEL))
        layout.addWidget(card)

        card, lay = self._card("공정 목록")
        self.proc_card_title = lay.itemAt(0).widget()
        self.proc_table = FormTable(
            self.state, "proc", ["라인명", "공정번호", "상세공정명", "공정내용", "삭제"],
            [190, 90, 220, 330, 70],
        )
        lay.addWidget(self.proc_table)
        lay.addWidget(_label("선택한 라인의 공정만 표시되고, 라인명은 선택한 라인으로 고정됩니다. 표 머리글 경계를 끌면 열 너비를 조절할 수 있습니다.", HINT_LABEL))
        layout.addWidget(card)
        layout.addStretch(1)
        return page

    def _line_names(self):
        return [l["name"] for l in self._info()["lines"] if l.get("name")]

    def _refresh_proc_line_combo(self, select=None):
        current = select if select is not None else self.proc_line_combo.currentText()
        self.proc_line_combo.blockSignals(True)
        self.proc_line_combo.clear()
        self.proc_line_combo.addItems(self._line_names())
        index = self.proc_line_combo.findText(current)
        self.proc_line_combo.setCurrentIndex(index if index >= 0 else 0)
        self.proc_line_combo.blockSignals(False)

    def _on_proc_line_selected(self):
        self._rebuild_processes()

    def _codes_for_line(self, line_name):
        kind = next((l.get("kind", "") for l in self._info()["lines"] if l.get("name") == line_name), "")
        return self.names.get(f"{kind}_공정Code", [])

    def _add_processes(self):
        line = self.proc_line_combo.currentText()
        if not line:
            QMessageBox.warning(self, "알림", "II. 라인 관리에서 라인(라인명)을 먼저 추가해주세요.")
            return
        text = self.proc_count_edit.text().strip()
        count = int(text) if text.isdigit() else 0
        if not 1 <= count <= 20:
            QMessageBox.warning(self, "알림", "공정 수는 1~20 사이의 숫자로 입력해주세요.")
            return
        for _ in range(count):
            self._info()["processes"].append({"line": line, "no": "", "code": "", "content": ""})
        self._save()
        self._rebuild_processes()

    def _rebuild_processes(self):
        line = self.proc_line_combo.currentText()
        visible = [p for p in self._info()["processes"] if line and p["line"] == line]
        self.proc_card_title.setText(f"▶  공정 목록 - {line}" if line else "▶  공정 목록")
        self.proc_table.set_rows(len(visible))
        for index, proc in enumerate(visible):
            fixed_line = QLineEdit(proc["line"])
            fixed_line.setReadOnly(True)
            fixed_line.setStyleSheet(INPUT_STYLE)
            fixed_line.setToolTip("위에서 선택한 라인으로 고정됩니다")
            self.proc_table.setCellWidget(index, 0, cell(fixed_line))

            no_edit = QLineEdit(proc["no"])
            no_edit.setStyleSheet(INPUT_STYLE)
            no_edit.editingFinished.connect(lambda p=proc, e=no_edit: self._on_proc_field(p, "no", e.text()))
            self.proc_table.setCellWidget(index, 1, cell(no_edit))

            code_combo = QComboBox()
            code_combo.setEditable(True)
            code_combo.setStyleSheet(COMBO_STYLE)
            code_combo.addItems(self._codes_for_line(proc["line"]))
            code_combo.setEditText(proc["code"])
            code_combo.activated.connect(lambda _i, p=proc, c=code_combo: self._on_proc_field(p, "code", c.currentText()))
            code_combo.lineEdit().editingFinished.connect(lambda p=proc, c=code_combo: self._on_proc_field(p, "code", c.currentText()))
            self.proc_table.setCellWidget(index, 2, cell(code_combo))

            content = QLineEdit(proc.get("content", ""))
            content.setStyleSheet(INPUT_STYLE)
            content.editingFinished.connect(lambda p=proc, e=content: self._on_proc_field(p, "content", e.text()))
            self.proc_table.setCellWidget(index, 3, cell(content))

            self.proc_table.setCellWidget(index, 4, self._delete_button(lambda _c=False, p=proc: self._delete_process(p)))

    def _on_proc_field(self, proc, key, value):
        if self._loading:
            return
        value = value.strip()
        if proc.get(key) != value:
            proc[key] = value
            self._save()

    def _delete_process(self, proc):
        self._info()["processes"].remove(proc)
        self._save()
        self._rebuild_processes()
