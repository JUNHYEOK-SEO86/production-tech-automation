"""입력 화면(MASTER 정보 기입, 공법 설계)이 같이 쓰는 스타일과 작은 위젯."""
from PySide6.QtWidgets import QFrame, QLabel, QSizePolicy, QVBoxLayout

CARD_STYLE = """
QFrame#masterCard {
    background: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 10px;
}
"""
INPUT_STYLE = """
QLineEdit {
    background: #f8fafc; border: 1px solid #cbd5e1; border-radius: 4px;
    padding: 4px 6px; font-size: 12px; color: #000000;
}
QLineEdit:focus { border-color: #2563eb; }
QLineEdit:read-only { background: #eef2f6; color: #1e3a8a; font-weight: 700; }
"""
COMBO_STYLE = """
QComboBox {
    background: #f8fafc; border: 1px solid #cbd5e1; border-radius: 4px;
    padding: 3px 6px; font-size: 12px; color: #000000; min-height: 20px;
}
QComboBox:focus { border-color: #2563eb; }
"""
TAB_STYLE = """
QTabWidget::pane { border: none; }
QTabBar::tab {
    background: transparent; color: #64748b; font-size: 13px; font-weight: 700;
    padding: 8px 18px; border-bottom: 3px solid transparent; margin-right: 4px;
}
QTabBar::tab:selected { color: #1e3a8a; border-bottom: 3px solid #2563eb; }
QTabBar::tab:hover { color: #1e3a8a; }
"""
PRIMARY_BTN = """
QPushButton { background: #2563eb; color: #ffffff; font-size: 11px; font-weight: 600; padding: 6px 14px; border-radius: 6px; border: none; }
QPushButton:hover { background: #1d4ed8; }
"""
SUB_BTN = """
QPushButton { background: #f1f5f9; color: #000000; font-size: 11px; font-weight: 600; padding: 5px 10px; border-radius: 5px; border: 1px solid #cbd5e1; }
QPushButton:hover { background: #e2e8f0; }
"""
DEL_BTN = """
QPushButton { background: #ffffff; color: #dc2626; font-size: 11px; font-weight: 700; border: 1px solid #fecaca; border-radius: 5px; padding: 3px 0; }
QPushButton:hover { background: #fee2e2; }
"""
CARD_TITLE = "color: #1e3a8a; font-weight: 700; font-size: 12px;"
FIELD_LABEL = "color: #475569; font-size: 11px; font-weight: 600;"
HEADER_LABEL = "color: #64748b; font-size: 10px; font-weight: 700;"
HINT_LABEL = "color: #94a3b8; font-size: 10px;"


def _label(text, style=FIELD_LABEL):
    """글자가 잘리지 않도록 글자 폭만큼은 항상 확보하는 라벨."""
    label = QLabel(text)
    label.setStyleSheet(style)
    label.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Preferred)
    label.setMinimumWidth(label.fontMetrics().horizontalAdvance(text) + 14)
    return label


def card(title):
    """제목이 있는 흰색 카드. (카드, 내용 레이아웃)을 돌려준다."""
    frame = QFrame()
    frame.setObjectName("masterCard")
    frame.setStyleSheet(CARD_STYLE)
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(14, 10, 14, 12)
    layout.setSpacing(8)
    layout.addWidget(_label("▶  " + title, CARD_TITLE))
    return frame, layout


def hint(text):
    """작은 안내 문구. 길면 줄바꿈하고, 화면 폭을 넓히지 않는다."""
    label = QLabel(text)
    label.setStyleSheet(HINT_LABEL)
    label.setWordWrap(True)
    label.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Minimum)
    return label
