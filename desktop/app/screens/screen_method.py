"""III. 공법 설계

마스터 1.1MASTER 시트의 공정 1개 블록(C/T → 용접시간 분석 → 설비내역 → 전용설비 금액 산출표)을 입력한다.
라인/공정번호/상세공정명/공정내용은 IV. 공정 관리에서 입력한 값을 그대로 보여 주고,
설비와 JIG 항목은 모두 고정값(설비 단가 리스트, JIG 원가 리스트)에서 드롭다운으로 고르게 해서
누가 입력해도 같은 투자비가 나오도록 한다.
"""
from PySide6.QtCore import QRegularExpression, Qt, QTimer
from PySide6.QtGui import QPixmap, QRegularExpressionValidator
from PySide6.QtWidgets import (
    QComboBox, QFrame, QGridLayout, QHBoxLayout, QLineEdit, QVBoxLayout, QWidget,
)

from app import method_calc as mc
from app.screens.ui_common import (
    COMBO_STYLE, FIELD_LABEL, HEADER_LABEL, HINT_LABEL, INPUT_STYLE, _label, card, hint,
)
from app.widgets.form_widgets import INPUT_PADDING_X, FormTable, cell
from app.widgets.weld_markup import WeldMarkupPanel

NUMBER = QRegularExpression(r"^\d*\.?\d*$")
INTEGER = QRegularExpression(r"^\d*$")
RESULT_STYLE = "color: #1e3a8a; font-weight: 700; font-size: 12px;"
PANEL_STYLE = "QFrame#modePanel { background: #ffffff; border: 1px solid #e2e8f0; border-radius: 8px; }"
PANEL_ACTIVE_STYLE = "QFrame#modePanel { background: #ffffff; border: 2px solid #2563eb; border-radius: 8px; }"


def _fill_combo(combo, items, current):
    """빈 선택 + 목록을 채우고 current 를 고른다. 목록에서 지워진 값이 저장돼 있으면 그대로 보이게 남겨 둔다."""
    combo.blockSignals(True)
    combo.clear()
    combo.addItem("")
    combo.addItems(items)
    if current and combo.findText(current) < 0:
        combo.addItem(current)
    combo.setCurrentIndex(max(combo.findText(current), 0))
    combo.blockSignals(False)


class MethodDesignTab(QWidget):
    def __init__(self, state, parent=None):
        super().__init__(parent)
        self.state = state
        self._loading = False
        self._procs = []          # 선택한 라인의 공정 dict 목록
        self._proc = None
        self._method = None
        self._line_kind = ""
        self._bound = []          # (QLineEdit, method 안의 경로)
        self._outputs = {}        # 이름 -> 계산 결과를 보여 주는 읽기 전용 입력창
        self._work_sub, self._equip_price, self._equip_amount = [], [], []
        self._jig_amount, self._unit_price, self._unit_amount = [], [], []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 8, 4, 8)
        layout.setSpacing(12)
        layout.addWidget(self._build_select_card())
        self.empty_label = hint("")
        layout.addWidget(self.empty_label)

        self.body = QWidget()
        body = QVBoxLayout(self.body)
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(12)
        body.addWidget(self._build_image_card())
        body.addWidget(self._build_ct_card())
        body.addWidget(self._build_equip_card())
        body.addWidget(self._build_jig_card())
        body.addWidget(self._build_total_card())
        layout.addWidget(self.body)
        layout.addStretch(1)

    # ---------------- 위젯 도우미 ----------------
    def _fixed(self):
        return self.state.fixed_values

    def _edit(self, path, width=72, integer=False, placeholder=""):
        """width=None 이면 칸 폭에 맞춰 늘어난다 (표 안에서 쓸 때)."""
        edit = QLineEdit()
        edit.setStyleSheet(INPUT_STYLE)
        if width:
            edit.setFixedWidth(width)
        edit.setPlaceholderText(placeholder)
        edit.setValidator(QRegularExpressionValidator(INTEGER if integer else NUMBER, edit))
        edit.editingFinished.connect(lambda e=edit, p=path: self._on_edit(p, e.text()))
        return edit

    def _bind(self, path, **kwargs):
        edit = self._edit(path, **kwargs)
        self._bound.append((edit, path))
        return edit

    def _output(self, name, width=80):
        edit = self._read_only(width)
        self._outputs[name] = edit
        return edit

    @staticmethod
    def _read_only(width=80):
        edit = QLineEdit()
        edit.setReadOnly(True)
        edit.setStyleSheet(INPUT_STYLE)
        if width:
            edit.setFixedWidth(width)
        edit.setToolTip("자동 계산 (수정 불가)")
        return edit

    @staticmethod
    def _table_label(text):
        label = _label(text, FIELD_LABEL)
        label.setContentsMargins(INPUT_PADDING_X, 0, 0, 0)
        return label

    def _combo(self, handler):
        combo = QComboBox()
        combo.setStyleSheet(COMBO_STYLE)
        combo.activated.connect(lambda _i, c=combo: handler(c.currentText()))
        return combo

    @staticmethod
    def _grid():
        grid = QGridLayout()
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(6)
        return grid

    # ---------------- 경로로 method 값 읽고 쓰기 ----------------
    def _get(self, path):
        value = self._method
        for key in path:
            value = value[key]
        return value

    def _set(self, path, value):
        target = self._method
        for key in path[:-1]:
            target = target[key]
        target[path[-1]] = value

    def _on_edit(self, path, text):
        if self._loading or self._method is None:
            return
        text = text.strip()
        if self._get(path) == text:
            return
        self._set(path, text)
        self.state.save()
        self._recalc()

    # ---------------- 공정 선택 ----------------
    def _build_select_card(self):
        frame, lay = card("공법 설계 - 공정 선택")
        row = QHBoxLayout()
        row.setSpacing(10)
        row.addWidget(_label("라인 선택 :"))
        self.line_combo = QComboBox()
        self.line_combo.setStyleSheet(COMBO_STYLE)
        self.line_combo.setMinimumWidth(240)
        self.line_combo.activated.connect(lambda _i: self._on_line_selected())
        row.addWidget(self.line_combo)
        row.addSpacing(10)
        row.addWidget(_label("공정 선택 :"))
        self.proc_combo = QComboBox()
        self.proc_combo.setStyleSheet(COMBO_STYLE)
        self.proc_combo.setMinimumWidth(300)
        self.proc_combo.activated.connect(lambda _i: self._on_proc_selected())
        row.addWidget(self.proc_combo)
        row.addStretch(1)
        lay.addLayout(row)

        grid = self._grid()
        self.summary = {}
        for col, (key, title, width) in enumerate((
            ("line", "라인명", 200), ("no", "공정번호", 90), ("code", "상세공정명", 200), ("content", "공정 내용", 360),
        )):
            grid.addWidget(_label(title), 0, col)
            edit = self._read_only(width)
            edit.setToolTip("IV. 공정 관리에서 입력한 값입니다")
            self.summary[key] = edit
            grid.addWidget(edit, 1, col, Qt.AlignLeft)
        lay.addLayout(grid)
        lay.addWidget(hint("라인 / 공정번호 / 상세공정명 / 공정 내용은 IV. 공정 관리에서 입력합니다. 이 화면에서는 선택한 공정의 공법 내용을 입력합니다."))
        return frame

    def _on_line_selected(self):
        self._fill_proc_combo()
        self._load_process()

    def _on_proc_selected(self):
        index = self.proc_combo.currentData()
        self._proc = self._procs[index] if index is not None and 0 <= index < len(self._procs) else None
        self._load_process()

    def _fill_proc_combo(self):
        info = self.state.master_info()
        line = self.line_combo.currentText()
        self._procs = [p for p in info["processes"] if line and p["line"] == line]
        self.proc_combo.blockSignals(True)
        self.proc_combo.clear()
        for index, proc in enumerate(self._procs):
            self.proc_combo.addItem(f"{proc['no'] or '(번호 없음)'}  ·  {proc['code'] or '(상세공정명 없음)'}", index)
        keep = next((i for i, p in enumerate(self._procs) if p is self._proc), 0)
        self.proc_combo.setCurrentIndex(keep if self._procs else -1)
        self.proc_combo.blockSignals(False)
        self._proc = self._procs[keep] if self._procs else None

    def refresh(self):
        """다른 탭/고정값에서 바뀐 라인, 공정, 목록을 새로 읽는다."""
        info = self.state.master_info()
        lines = [l["name"] for l in info["lines"] if l.get("name")]
        current = self.line_combo.currentText()
        self.line_combo.blockSignals(True)
        self.line_combo.clear()
        self.line_combo.addItems(lines)
        index = self.line_combo.findText(current)
        self.line_combo.setCurrentIndex(index if index >= 0 else 0)
        self.line_combo.blockSignals(False)
        self._fill_proc_combo()
        self._load_process()

    # ---------------- 제품 이미지 / 용접 표기 ----------------
    def _build_image_card(self):
        frame, lay = card("제품 이미지 / 용접 표기")
        self.markup = WeldMarkupPanel()
        self.markup.imageChanged.connect(self._on_image_changed)
        self.markup.marksChanged.connect(self._on_marks_changed)
        lay.addWidget(self.markup)
        return frame

    def _on_image_changed(self, image):
        if self._loading or self._method is None:
            return
        self._method["image"] = self.state.save_qimage(image) if image is not None else ""
        self.state.save()

    def _on_marks_changed(self):
        if self._loading or self._method is None:
            return
        self.state.save()

    # ---------------- C/T ----------------
    def _panel(self, title):
        frame = QFrame()
        frame.setObjectName("modePanel")
        frame.setStyleSheet(PANEL_STYLE)
        lay = QVBoxLayout(frame)
        lay.setContentsMargins(12, 10, 12, 12)
        lay.setSpacing(8)
        head = _label(title, RESULT_STYLE)
        lay.addWidget(head)
        return frame, lay, head

    def _build_ct_card(self):
        frame, lay = card("C/T 분석")
        row = QHBoxLayout()
        row.setSpacing(10)
        row.addWidget(_label("적용 방식 :"))
        self.mode_combo = QComboBox()
        self.mode_combo.setStyleSheet(COMBO_STYLE)
        self.mode_combo.setMinimumWidth(320)
        for mode, text in mc.MODE_LABELS.items():
            self.mode_combo.addItem(text, mode)
        self.mode_combo.activated.connect(lambda _i: self._on_mode())
        row.addWidget(self.mode_combo)
        row.addStretch(1)
        lay.addLayout(row)
        lay.addWidget(hint("일반 / 용접 입력칸을 같이 보여 줍니다. 아래 LOAD'G · WORK'G · UNLOAD'G · TOTAL에는 '적용 방식'으로 고른 쪽(파란 테두리) 값이 쓰입니다. 상세공정명에 따라 적용 방식이 자동으로 정해지고, 필요하면 직접 바꿀 수 있습니다. 시간 단위는 모두 초입니다."))

        panels = QHBoxLayout()
        panels.setSpacing(12)
        self._panels = {}
        for mode, title, builder, stretch in ((mc.MODE_GENERAL, "일반", self._fill_general_panel, 1), (mc.MODE_WELD, "용접", self._fill_weld_panel, 1)):
            panel, panel_lay, head = self._panel(title)
            builder(panel_lay)
            panel_lay.addStretch(1)
            self._panels[mode] = (panel, head, title)
            panels.addWidget(panel, stretch)
        lay.addLayout(panels)

        grid = self._grid()
        self.arc_edit = self._bind(("arc_len",), width=90)
        grid.addWidget(_label("ARC 용접길이"), 0, 0)
        grid.addWidget(_label("SPOT (점)"), 0, 1)
        grid.addWidget(_label("P/J (점)"), 0, 2)
        grid.addWidget(self.arc_edit, 1, 0, Qt.AlignLeft)
        grid.addWidget(self._bind(("spot",), width=90), 1, 1, Qt.AlignLeft)
        grid.addWidget(self._bind(("pj",), width=90), 1, 2, Qt.AlignLeft)
        grid.setColumnStretch(3, 1)
        lay.addLayout(grid)

        result = QHBoxLayout()
        result.setSpacing(8)
        for key, title in (("load", "LOAD'G"), ("work", "WORK'G"), ("unload", "UNLOAD'G"), ("total", "TOTAL")):
            result.addWidget(_label(title + " :", RESULT_STYLE))
            result.addWidget(self._output("ct_" + key, 76))
            result.addSpacing(10)
        result.addWidget(_label("(초)", HINT_LABEL))
        result.addStretch(1)
        lay.addLayout(result)
        return frame

    def _mark_active_panel(self, mode):
        for key, (panel, head, title) in self._panels.items():
            active = key == mode
            panel.setStyleSheet(PANEL_ACTIVE_STYLE if active else PANEL_STYLE)
            head.setText(f"{title}   ▶ 적용 중" if active else title)

    def _fill_general_panel(self, lay):
        grid = self._grid()
        for col, title in enumerate(("", "작업자", "ROBOT", "기타", "합계")):
            grid.addWidget(_label(title, HEADER_LABEL), 0, col)
        for row, (key, title) in enumerate((("load", "LOAD'G (초)"), ("unload", "UNLOAD'G (초)")), start=1):
            grid.addWidget(_label(title), row, 0)
            for col, field in enumerate(("worker", "robot", "etc"), start=1):
                grid.addWidget(self._bind((key, field)), row, col, Qt.AlignLeft)
            grid.addWidget(self._output("gen_" + key), row, 4, Qt.AlignLeft)
        grid.setColumnStretch(5, 1)
        lay.addLayout(grid)

        lay.addWidget(_label("WORK'G (작업 항목 × 횟수 × 시간(초))", FIELD_LABEL))
        self.work_table = FormTable(self.state, "method_ct_work", ["작업 항목", "횟수", "시간", "소계"], [130, 60, 70, 70])
        lay.addWidget(self.work_table)

    def _fill_weld_panel(self, lay):
        lay.addWidget(_label("LOAD'G / UNLOAD'G", FIELD_LABEL))
        grid = self._grid()
        cells = (
            (("big", f"대물 (개 × {mc.LOAD_SECONDS['big']}초)"), ("mid", f"중물 (개 × {mc.LOAD_SECONDS['mid']}초)"),
             ("small", f"소물 (개 × {mc.LOAD_SECONDS['small']}초)")),
            (("load_etc", "기타 (초)"), ("_load_sum", "LOAD'G 합계 (초)"), ("unload", "UNLOAD'G (초)")),
        )
        for row, fields in enumerate(cells):
            for col, (field, title) in enumerate(fields):
                grid.addWidget(_label(title, HEADER_LABEL), row * 2, col)
                widget = self._output("weld_load") if field == "_load_sum" else self._bind(("weld", field))
                grid.addWidget(widget, row * 2 + 1, col, Qt.AlignLeft)
        grid.setColumnStretch(3, 1)
        lay.addLayout(grid)
        lay.addWidget(hint(f"LOAD'G 합계 = 개수 × 시간의 합 + 기타 + 고정 {mc.LOAD_FIXED}초 (합이 {mc.LOAD_FIXED}초 이하면 0)"))

        lay.addWidget(_label("용접시간 분석", FIELD_LABEL))
        cond = self._grid()
        fields = (
            ("speed", "용접속도 (mm/초)"), ("beads", "비드수"), ("tack", f"가접 (회 × {mc.TACK_SECONDS}초)"),
            ("turn", "JIG 회전 (회)"), ("turn_sec", "회전 1회 (초)"), ("home", f"원점복귀 (회 × {mc.HOME_SECONDS}초)"),
            ("extra", "추가시간 (초)"),
        )
        for index, (field, title) in enumerate(fields):
            row, col = divmod(index, 3)
            cond.addWidget(_label(title, HEADER_LABEL), row * 2, col)
            cond.addWidget(self._bind(("weld", field), width=80), row * 2 + 1, col, Qt.AlignLeft)
        cond.setColumnStretch(3, 1)
        lay.addLayout(cond)

        lengths = self._grid()
        for col, title in enumerate(("", "용접길이 (mm)", "용접시간 (초)")):
            lengths.addWidget(_label(title, HEADER_LABEL), 0, col)
        for row, (field, title, out) in enumerate((("r1_len", "R1", "weld_r1"), ("r2_len", "R2", "weld_r2")), start=1):
            lengths.addWidget(_label(title), row, 0)
            lengths.addWidget(self._bind(("weld", field), width=100), row, 1, Qt.AlignLeft)
            lengths.addWidget(self._output(out, 100), row, 2, Qt.AlignLeft)
        lengths.setColumnStretch(3, 1)
        lay.addLayout(lengths)
        lay.addWidget(hint("용접시간 = 용접길이 ÷ 용접속도 + 2×(비드수-1) + 가접 + JIG 회전 + 원점복귀 + 추가시간 (올림). WORK'G = R1, R2 중 큰 값. ARC 용접길이 = R1 + R2"))

    def _on_mode(self):
        if self._loading or self._method is None:
            return
        self._method["mode"] = self.mode_combo.currentData()
        self.state.save()
        self._recalc()

    def _rebuild_work(self):
        rows = self._method["work"]
        self.work_table.set_rows(len(rows))
        self._work_sub = []
        for index in range(len(rows)):
            label = QLineEdit(rows[index]["label"])
            label.setStyleSheet(INPUT_STYLE)
            label.editingFinished.connect(lambda e=label, i=index: self._on_edit(("work", i, "label"), e.text()))
            self.work_table.setCellWidget(index, 0, cell(label))
            for col, field in ((1, "count"), (2, "time")):
                edit = self._edit(("work", index, field), width=None)
                edit.setText(rows[index][field])
                self.work_table.setCellWidget(index, col, cell(edit))
            sub = self._read_only(None)
            self._work_sub.append(sub)
            self.work_table.setCellWidget(index, 3, cell(sub))

    # ---------------- 설비 내역 ----------------
    def _build_equip_card(self):
        frame, lay = card("설비 내역")
        self.equip_table = FormTable(
            self.state, "method_equip", ["전/범용", "설비", "설비명", "단가", "수량", "총 금액"], [100, 170, 300, 100, 80, 120],
        )
        lay.addWidget(self.equip_table)
        lay.addWidget(hint("전/범용 → 설비 → 설비명 순서로 고르면 단가가 자동으로 들어갑니다. 목록과 단가는 고정값의 '설비 단가'에서 관리합니다."))

        grid = self._grid()
        grid.addWidget(_label("설비 합계 :", RESULT_STYLE), 0, 0)
        grid.addWidget(self._output("equip_total", 120), 0, 1, Qt.AlignLeft)
        grid.addWidget(_label("설비명 :"), 1, 0)
        self.equip_names = self._read_only(None)
        self.equip_names.setMinimumWidth(480)
        grid.addWidget(self.equip_names, 1, 1)
        grid.addWidget(_label("JIG명 :"), 2, 0)
        self.jig_names = self._read_only(None)
        self.jig_names.setMinimumWidth(480)
        grid.addWidget(self.jig_names, 2, 1)
        grid.setColumnStretch(2, 1)
        lay.addLayout(grid)
        return frame

    def _rebuild_equip(self):
        fv = self._fixed()
        kinds = fv.get("전용범용") or ["전용", "범용"]
        rows = self._method["equip"]
        self.equip_table.set_rows(len(rows))
        self._equip_price, self._equip_amount = [], []
        for index, row in enumerate(rows):
            kind = self._combo(lambda text, i=index: self._on_equip_kind(i, text))
            _fill_combo(kind, kinds, row["kind"])
            self.equip_table.setCellWidget(index, 0, cell(kind))

            cat = self._combo(lambda text, i=index: self._on_equip_cat(i, text))
            _fill_combo(cat, mc.equip_categories(fv, row["kind"], self._line_kind, self._code()) if row["kind"] else [], row["cat"])
            self.equip_table.setCellWidget(index, 1, cell(cat))

            name = self._combo(lambda text, i=index: self._on_equip_name(i, text))
            names = [item["name"] for item in mc.equip_items(fv, row["kind"], row["cat"])] if row["cat"] else []
            _fill_combo(name, names, row["name"])
            self.equip_table.setCellWidget(index, 2, cell(name))

            price = self._read_only(None)
            self._equip_price.append(price)
            self.equip_table.setCellWidget(index, 3, cell(price))

            qty = self._edit(("equip", index, "qty"), width=None, integer=True)
            qty.setText(row["qty"])
            self.equip_table.setCellWidget(index, 4, cell(qty))

            amount = self._read_only(None)
            self._equip_amount.append(amount)
            self.equip_table.setCellWidget(index, 5, cell(amount))

    def _code(self):
        return self._proc["code"] if self._proc else ""

    def _on_equip_kind(self, index, text):
        row = self._method["equip"][index]
        if row["kind"] != text:
            row.update(kind=text, cat="", name="")
            self.state.save()
            QTimer.singleShot(0, self._rebuild_equip_and_recalc)

    def _on_equip_cat(self, index, text):
        row = self._method["equip"][index]
        if row["cat"] != text:
            row.update(cat=text, name="")
            self.state.save()
            QTimer.singleShot(0, self._rebuild_equip_and_recalc)

    def _on_equip_name(self, index, text):
        self._on_edit(("equip", index, "name"), text)

    def _rebuild_equip_and_recalc(self):
        if self._method is not None:
            self._rebuild_equip()
            self._recalc()

    # ---------------- 전용설비 금액 산출표 ----------------
    def _build_jig_card(self):
        frame, lay = card("전용설비 금액 산출표")
        self.jig_table = FormTable(self.state, "method_jig", ["구분", "항목", "금액"], [160, 340, 120])
        lay.addWidget(self.jig_table)
        self.unit_table = FormTable(self.state, "method_unit", ["JIG UNIT 항목", "단가", "수량", "금액"], [340, 110, 80, 120])
        lay.addWidget(self.unit_table)
        lay.addWidget(hint("항목은 고정값의 'JIG 원가 리스트'에서 고르면 금액이 자동으로 들어갑니다. (기타 = UTILITY 목록)"))
        grid = self._grid()
        grid.addWidget(_label("JIG 금액 :", RESULT_STYLE), 0, 0)
        grid.addWidget(self._output("jig_total", 120), 0, 1, Qt.AlignLeft)
        grid.setColumnStretch(2, 1)
        lay.addLayout(grid)
        return frame

    def _rebuild_jig(self):
        fv = self._fixed()
        jig = self._method["jig"]
        self.jig_table.set_rows(len(mc.JIG_ROWS))
        self._jig_amount = []
        for index, (title, key, group) in enumerate(mc.JIG_ROWS):
            self.jig_table.setCellWidget(index, 0, cell(self._table_label(title)))
            combo = self._combo(lambda text, k=key: self._on_edit(("jig", k), text))
            _fill_combo(combo, [i["name"] for i in mc.jig_list(fv, group)], jig[key])
            self.jig_table.setCellWidget(index, 1, cell(combo))
            amount = self._read_only(None)
            self._jig_amount.append(amount)
            self.jig_table.setCellWidget(index, 2, cell(amount))

        units = jig["units"]
        self.unit_table.set_rows(len(units))
        self._unit_price, self._unit_amount = [], []
        names = [i["name"] for i in mc.jig_list(fv, "JIG UNIT")]
        for index, row in enumerate(units):
            combo = self._combo(lambda text, i=index: self._on_edit(("jig", "units", i, "name"), text))
            _fill_combo(combo, names, row["name"])
            self.unit_table.setCellWidget(index, 0, cell(combo))
            price = self._read_only(None)
            self._unit_price.append(price)
            self.unit_table.setCellWidget(index, 1, cell(price))
            qty = self._edit(("jig", "units", index, "qty"), width=None, integer=True)
            qty.setText(row["qty"])
            self.unit_table.setCellWidget(index, 2, cell(qty))
            amount = self._read_only(None)
            self._unit_amount.append(amount)
            self.unit_table.setCellWidget(index, 3, cell(amount))

    # ---------------- 투자비 합계 ----------------
    def _build_total_card(self):
        frame, lay = card("공정 투자비 합계")
        grid = self._grid()
        grid.addWidget(_label("설비 합계"), 0, 0)
        grid.addWidget(_label("JIG 금액"), 0, 1)
        grid.addWidget(_label("투자비 합계", RESULT_STYLE), 0, 2)
        grid.addWidget(self._output("sum_equip", 120), 1, 0, Qt.AlignLeft)
        grid.addWidget(self._output("sum_jig", 120), 1, 1, Qt.AlignLeft)
        grid.addWidget(self._output("sum_all", 140), 1, 2, Qt.AlignLeft)
        grid.setColumnStretch(3, 1)
        lay.addLayout(grid)
        lay.addWidget(hint("금액 단위는 고정값 목록에 입력한 단가와 같습니다. (엑셀 마스터와 동일한 단위)"))
        return frame

    # ---------------- 공정을 바꿨을 때 전체 불러오기 ----------------
    def _load_process(self):
        proc = self._proc
        has_proc = proc is not None
        self.body.setVisible(has_proc)
        if not has_proc:
            self._method = None
            for edit in self.summary.values():
                edit.setText("")
            self.empty_label.setText("IV. 공정 관리에서 라인과 공정을 먼저 추가해주세요." if not self.line_combo.count()
                                     else "선택한 라인에 공정이 없습니다. IV. 공정 관리에서 공정을 추가해주세요.")
            self.empty_label.setVisible(True)
            return
        self.empty_label.setVisible(False)
        info = self.state.master_info()
        self._line_kind = next((l.get("kind", "") for l in info["lines"] if l.get("name") == proc["line"]), "")
        self._loading = True
        self._method = mc.get_method(proc)
        for key, edit in self.summary.items():
            edit.setText(proc.get(key, ""))
        for edit, path in self._bound:
            edit.setText(str(self._get(path)))
        mode = mc.mode_of(self._method, self._line_kind, proc["code"])
        self.mode_combo.setCurrentIndex(self.mode_combo.findData(mode))
        pixmap = QPixmap(self.state.resolve_image(self._method["image"])) if self._method["image"] else QPixmap()
        self.markup.set_content(pixmap, self._method["marks"])
        self._rebuild_work()
        self._rebuild_equip()
        self._rebuild_jig()
        self._loading = False
        self._recalc()

    # ---------------- 계산 결과 갱신 ----------------
    def _recalc(self):
        if self._method is None:
            return
        method, fv = self._method, self._fixed()
        mode = mc.mode_of(method, self._line_kind, self._code())
        self._mark_active_panel(mode)
        if self.mode_combo.currentData() != mode:
            self.mode_combo.setCurrentIndex(self.mode_combo.findData(mode))

        general = mc.compute_ct(method, mode=mc.MODE_GENERAL)
        weld = mc.compute_ct(method, mode=mc.MODE_WELD)
        active = weld if mode == mc.MODE_WELD else general
        out = self._outputs
        out["gen_load"].setText(mc.fmt(general["load"]))
        out["gen_unload"].setText(mc.fmt(general["unload"]))
        for edit, value in zip(self._work_sub, general["rows"]):
            edit.setText(mc.fmt(value))
        out["weld_load"].setText(mc.fmt(weld["load"]))
        out["weld_r1"].setText(mc.fmt(weld["r1"]))
        out["weld_r2"].setText(mc.fmt(weld["r2"]))
        for key in ("load", "work", "unload", "total"):
            out["ct_" + key].setText(mc.fmt(active[key]))

        self.arc_edit.setReadOnly(mode == mc.MODE_WELD)
        self.arc_edit.setText(mc.fmt(weld["arc_len"]) if mode == mc.MODE_WELD else method["arc_len"])

        equip = mc.compute_equipment(method, fv)
        for index, row in enumerate(equip["rows"]):
            self._equip_price[index].setText(mc.money(row["price"]))
            self._equip_amount[index].setText(mc.money(row["amount"]))
        out["equip_total"].setText(mc.money(equip["total"]))
        general_names, dedicated_names = mc.equipment_summary(method)
        self.equip_names.setText(general_names)
        self.jig_names.setText(dedicated_names)

        jig = mc.compute_jig(method, fv)
        for index, (_title, key, _group) in enumerate(mc.JIG_ROWS):
            self._jig_amount[index].setText(mc.money(jig["lines"][key]))
        for index, row in enumerate(jig["units"]):
            self._unit_price[index].setText(mc.money(row["price"]))
            self._unit_amount[index].setText(mc.money(row["amount"]))
        out["jig_total"].setText(mc.money(jig["total"]))

        out["sum_equip"].setText(mc.money(equip["total"]))
        out["sum_jig"].setText(mc.money(jig["total"]))
        out["sum_all"].setText(mc.money(equip["total"] + jig["total"]))
