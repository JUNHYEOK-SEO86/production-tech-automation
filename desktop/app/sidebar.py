from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QButtonGroup, QFrame, QLabel, QPushButton, QScrollArea, QVBoxLayout, QWidget

NAV_ITEMS = [
    ("section", "1. 개발착수 (공법검토)"),
    ("nav", "1-1", "1-1. MASTER 정보 기입"),
    ("nav", "1-2", "1-2. 목표 C/T & 공정 수립"),
    ("nav", "1-3", "1-3. 설비 공법 검토"),
    ("nav", "1-4", "1-4. 관리문서 작성"),
    ("section", "다음 단계"),
    ("nav", "2", "2. 품의 / 발주"),
    ("nav", "3", "3. 설치 / 품힉 (T/O)"),
    ("nav", "4", "4. 운송 & HTS 코드"),
    ("nav", "5", "5. 완료보고 & 집계"),
]

FIXED_ITEMS = [
    ("fv:item", "아이템 / 품명"),
    ("fv:step", "단계"),
    ("fv:team", "팀명"),
    ("fv:person", "담당자"),
    ("fv:rank", "직급 / REV"),
    ("fv:line", "라인 구분 / 전용범용"),
    ("fv:site", "설치장소 / 근무조"),
    ("fv:code", "상세공정명"),
    ("fv:jig", "JIG 원가 리스트"),
    ("fv:equip", "설비 단가"),
]

NAV_BUTTON_STYLE = """
QPushButton {
    text-align: left;
    padding: 9px 12px;
    border-radius: 8px;
    color: #94a3b8;
    background: transparent;
    font-size: 13px;
    border: none;
}
QPushButton:hover {
    background: rgba(255, 255, 255, 0.06);
    color: #e2e8f0;
}
QPushButton:checked {
    background: #2563eb;
    color: #ffffff;
    font-weight: 600;
}
"""

SECTION_LABEL_STYLE = "color: #64748b; font-size: 11px; font-weight: 600; padding: 6px 4px 2px 4px;"


class Sidebar(QWidget):
    screenSelected = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(260)
        self.setStyleSheet("""
            Sidebar {
                background-color: #111827;
                border-right: 1px solid #1e293b;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        layout.addWidget(self._build_header())

        nav_container = QWidget()
        nav_layout = QVBoxLayout(nav_container)
        nav_layout.setContentsMargins(14, 16, 14, 16)
        nav_layout.setSpacing(4)

        self.button_group = QButtonGroup(self)
        self.button_group.setExclusive(True)
        self.buttons = {}

        def add_nav_button(screen_id, text):
            btn = QPushButton(text)
            btn.setCheckable(True)
            btn.setStyleSheet(NAV_BUTTON_STYLE)
            btn.clicked.connect(lambda _checked, sid=screen_id: self.screenSelected.emit(sid))
            self.button_group.addButton(btn)
            self.buttons[screen_id] = btn
            nav_layout.addWidget(btn)

        for entry in NAV_ITEMS:
            if entry[0] == "section":
                label = QLabel(entry[1])
                label.setStyleSheet(SECTION_LABEL_STYLE)
                nav_layout.addWidget(label)
            else:
                add_nav_button(entry[1], entry[2])

        nav_layout.addStretch(1)

        divider = QFrame()
        divider.setFixedHeight(1)
        divider.setStyleSheet("background: #1e293b;")
        nav_layout.addWidget(divider)
        fixed_label = QLabel("고정값 (드롭다운 항목 관리)")
        fixed_label.setStyleSheet(SECTION_LABEL_STYLE)
        nav_layout.addWidget(fixed_label)
        for screen_id, text in FIXED_ITEMS:
            add_nav_button(screen_id, text)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; } QScrollArea > QWidget > QWidget { background: transparent; }")
        scroll.setWidget(nav_container)
        layout.addWidget(scroll, 1)

        footer = QLabel("DB 보안 모드: 관리자 승인 필수")
        footer.setWordWrap(True)
        footer.setStyleSheet("""
            color: #34d399;
            font-size: 11px;
            font-weight: 500;
            padding: 14px;
            border-top: 1px solid #1e293b;
        """)
        layout.addWidget(footer)

    def _build_header(self):
        header = QWidget()
        header.setStyleSheet("border-bottom: 1px solid #1e293b;")
        layout = QVBoxLayout(header)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(2)

        title = QLabel("PE-AMS")
        title.setStyleSheet("color: #ffffff; font-size: 14px; font-weight: 700;")
        subtitle = QLabel("생산기술 개발 업무 자동화")
        subtitle.setStyleSheet("color: #94a3b8; font-size: 11px;")

        layout.addWidget(title)
        layout.addWidget(subtitle)
        return header

    def set_active(self, screen_id):
        btn = self.buttons.get(screen_id)
        if btn:
            btn.setChecked(True)
