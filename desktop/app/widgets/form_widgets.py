"""입력 화면에서 같이 쓰는 위젯: 길이 조절 가능한 입력창, 날짜 자동 서식 입력창, 열 너비 조절 표."""
import re

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter
from PySide6.QtWidgets import (
    QAbstractItemView, QHBoxLayout, QHeaderView, QLineEdit, QTableWidget, QWidget,
)

MAX_WIDGET_WIDTH = 16777215
HEADER_HEIGHT = 32


class ResizeGrip(QWidget):
    """입력창 오른쪽 끝의 손잡이. 좌우로 끌면 입력창 길이가 바뀌고, 더블클릭하면 원래대로 돌아온다."""

    released = Signal(int)  # 0이면 기본 길이

    def __init__(self, target, default_width=None, min_width=60, max_width=800, parent=None):
        super().__init__(parent)
        self.target = target
        self.default_width = default_width
        self.min_width = min_width
        self.max_width = max_width
        self._press_x = None
        self._start_width = 0
        self.setFixedWidth(9)
        self.setCursor(Qt.SizeHorCursor)
        self.setToolTip("좌우로 끌어서 입력창 길이 조정 (더블클릭: 원래 길이)")

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setPen(QColor("#94a3b8"))
        x, mid = self.width() // 2, self.height() // 2
        for dy in (-4, 0, 4):
            painter.drawPoint(x - 1, mid + dy)
            painter.drawPoint(x + 1, mid + dy)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._press_x = event.globalPosition().x()
            self._start_width = self.target.width()

    def mouseMoveEvent(self, event):
        if self._press_x is not None:
            width = int(self._start_width + event.globalPosition().x() - self._press_x)
            self.target.setFixedWidth(max(self.min_width, min(self.max_width, width)))

    def mouseReleaseEvent(self, _event):
        if self._press_x is not None:
            self._press_x = None
            self.released.emit(self.target.width())

    def mouseDoubleClickEvent(self, _event):
        apply_width(self.target, self.default_width)
        self.released.emit(0)


def apply_width(widget, width):
    if width:
        widget.setFixedWidth(int(width))
    else:
        widget.setMinimumWidth(0)
        widget.setMaximumWidth(MAX_WIDGET_WIDTH)


def make_resizable(widget, state, key, default_width=None):
    """widget 오른쪽에 길이 조절 손잡이를 붙인 컨테이너를 돌려준다. 조절한 길이는 key로 저장된다."""
    container = QWidget()
    layout = QHBoxLayout(container)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(2)
    layout.addWidget(widget, 1)
    grip = ResizeGrip(widget, default_width)
    layout.addWidget(grip)
    apply_width(widget, state.get_width(key) or default_width)
    grip.released.connect(lambda width, k=key: state.set_width(k, width))
    return container


CELL_MARGIN_X = 4      # 칸 안쪽 좌우 여백 (입력창이 칸 경계에서 떨어진 거리)
INPUT_PADDING_X = 6    # 입력창 안쪽 글자 시작 위치
HEADER_FONT_PX = 11


def cell(widget, align=None, margins=(CELL_MARGIN_X, 3, CELL_MARGIN_X, 3)):
    """표 칸에 넣을 위젯에 여백을 준다. align을 주면 위젯이 칸 폭만큼 늘어나지 않고 그 위치에 놓인다."""
    holder = QWidget()
    layout = QHBoxLayout(holder)
    layout.setContentsMargins(*margins)
    if align is None:
        layout.addWidget(widget)
    else:
        layout.addWidget(widget, 0, align)
    return holder


class DateLineEdit(QLineEdit):
    """숫자만 입력하면 0000.00.00 형태로 점을 자동으로 넣어주는 날짜 입력창."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMaxLength(10)
        self.setPlaceholderText("0000.00.00")
        self.textEdited.connect(self._format)

    @staticmethod
    def format_digits(text):
        digits = re.sub(r"\D", "", text)[:8]
        formatted = digits[:4]
        if len(digits) > 4:
            formatted += "." + digits[4:6]
        if len(digits) > 6:
            formatted += "." + digits[6:8]
        return formatted

    def _format(self, text):
        formatted = self.format_digits(text)
        if formatted != text:
            self.setText(formatted)
            self.setCursorPosition(len(formatted))


class FormTable(QTableWidget):
    """입력창을 칸에 넣는 표. 머리글 경계를 끌어서 열 너비를 조절하고, 조절한 너비는 저장된다."""

    def __init__(self, state, key, headers, widths, row_height=36, parent=None):
        super().__init__(0, len(headers), parent)
        self.state = state
        self.key = f"table:{key}"
        self.row_height = row_height

        self.setHorizontalHeaderLabels(headers)
        self.verticalHeader().hide()
        self.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.setSelectionMode(QAbstractItemView.NoSelection)
        self.setFocusPolicy(Qt.NoFocus)
        self.setShowGrid(False)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setStyleSheet("""
            QTableWidget { background: #ffffff; border: 1px solid #e2e8f0; border-radius: 6px; }
            QHeaderView::section {
                background: #f1f5f9; color: #334155; font-size: 11px; font-weight: 700;
                border: none; border-right: 1px solid #e2e8f0; border-bottom: 1px solid #e2e8f0;
                padding: 4px 6px 4px %dpx;
            }
        """ % (CELL_MARGIN_X + INPUT_PADDING_X))

        header = self.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Interactive)
        header.setStretchLastSection(True)
        header.setMinimumSectionSize(36)
        header.setHighlightSections(False)
        header.setFixedHeight(HEADER_HEIGHT)
        header.setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        font = QFont(header.font())
        font.setPixelSize(HEADER_FONT_PX)
        font.setBold(True)
        metrics = QFontMetrics(font)
        saved = state.get_width(self.key)
        use_saved = saved and len(saved) == len(headers)
        for index, width in enumerate(saved if use_saved else widths):
            if use_saved and index == len(headers) - 1:
                width = widths[index]  # 마지막 열은 남는 폭을 채우므로 저장된 폭을 쓰지 않는다
            needed = metrics.horizontalAdvance(headers[index]) + CELL_MARGIN_X + INPUT_PADDING_X + 22
            self.setColumnWidth(index, max(int(width), needed))

        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.setInterval(400)
        self._save_timer.timeout.connect(self._save_widths)
        header.sectionResized.connect(lambda *_: self._save_timer.start())
        self.fit_height()

    def _save_widths(self):
        self.state.set_width(self.key, [self.columnWidth(i) for i in range(self.columnCount())])

    def set_rows(self, count):
        self.setRowCount(0)
        self.setRowCount(count)
        for row in range(count):
            self.setRowHeight(row, self.row_height)
        self.fit_height()

    def fit_height(self):
        self.setFixedHeight(HEADER_HEIGHT + self.rowCount() * self.row_height + 4)
