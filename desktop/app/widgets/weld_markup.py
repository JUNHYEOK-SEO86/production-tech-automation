"""제품 이미지 위에 용접 관련 표시를 그리는 위젯.

- 용접 비드(빨강): 시작점을 누르고 끌었다 떼면 직선이 그려지고, 뗄 때마다 나오는 작은 창에서 [종료]를 누르면 그 비드가 끝난다.
- 용접길이 표기(검정): 비드 끝에서 이어서 선을 긋고 용접길이 숫자를 적는다.
- 가접, 브러쉬 위치(선), LOT NO 타각, 육안 검사, 스패터 확인, 품질 확인(체크) 표시.
표시 위치는 이미지 크기에 대한 비율(0~1)로 저장하므로 화면 크기가 바뀌어도 같은 자리에 그려진다.
"""
import math

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import (
    QBrush, QColor, QFont, QGuiApplication, QKeySequence, QPainter, QPainterPath, QPen, QPixmap, QPolygonF, QShortcut,
)
from PySide6.QtWidgets import (
    QButtonGroup, QFileDialog, QFrame, QGridLayout, QHBoxLayout, QInputDialog, QLabel, QMessageBox, QPushButton,
    QSizePolicy, QVBoxLayout, QWidget,
)

TOOLS = [
    ("bead", "용접 비드 (빨강)"),
    ("dim", "용접길이 표기 (검정)"),
    ("tack", "가접 표시"),
    ("brush", "브러쉬 위치"),
    ("lot", "LOT NO 타각"),
    ("eye", "육안 검사"),
    ("spatter", "스패터 확인"),
    ("check", "품질 확인 ✓"),
    ("erase", "지우개"),
]
LINE_TOOLS = {"bead", "dim", "brush"}
POINT_TOOLS = {"tack", "lot", "eye", "spatter", "check"}
TOOL_HINTS = {
    "bead": "비드 시작점에서 마우스를 누른 채 끌었다가 떼세요. 뗄 때마다 나오는 [종료] 창에서 종료를 누를 때까지 이어서 그릴 수 있습니다.",
    "dim": "비드 끝점(자동으로 붙습니다)에서 끌어서 검은 선을 긋고, 떼면 용접길이 숫자를 입력합니다. 숫자는 더블클릭해서 고칠 수 있습니다.",
    "tack": "가접할 위치를 클릭하세요. (◆)",
    "brush": "브러쉬할 구간을 끌어서 선으로 표시하세요.",
    "lot": "LOT NO를 타각하는 위치를 클릭하세요.",
    "eye": "작업자가 육안으로 검사하는 위치를 클릭하세요.",
    "spatter": "스패터 중점 확인 부위를 클릭하세요.",
    "check": "그 밖에 중점 품질 확인이 필요한 부위를 클릭하세요.",
    "erase": "지울 표시를 클릭하세요. (비드는 한 번에 통째로 지워집니다)",
}

BEAD_COLOR = QColor("#dc2626")
DIM_COLOR = QColor("#000000")
BRUSH_COLOR = QColor("#0891b2")
HIT_PX = 10          # 지우개/더블클릭이 표시를 잡는 거리(픽셀)
SNAP_PX = 12         # 선 시작점이 앞 선 끝에 붙는 거리(픽셀)
MIN_DRAG_PX = 5      # 이보다 짧게 끌면 클릭으로 보고 무시

BUTTON_STYLE = """
QPushButton {
    background: #f1f5f9; color: #000000; font-size: 11px; font-weight: 600;
    padding: 5px 10px; border-radius: 5px; border: 1px solid #cbd5e1;
}
QPushButton:hover { background: #e2e8f0; }
QPushButton:checked { background: #2563eb; color: #ffffff; border-color: #1d4ed8; }
"""
PRIMARY_STYLE = """
QPushButton { background: #2563eb; color: #ffffff; font-size: 11px; font-weight: 600; padding: 5px 12px; border-radius: 5px; border: none; }
QPushButton:hover { background: #1d4ed8; }
"""
POPUP_STYLE = """
QFrame#beadPopup { background: #ffffff; border: 1px solid #94a3b8; border-radius: 6px; }
QLabel { color: #000000; font-size: 11px; background: transparent; }
QPushButton { font-size: 11px; font-weight: 700; padding: 3px 10px; border-radius: 4px; border: 1px solid #cbd5e1; background: #f1f5f9; color: #000000; }
QPushButton#endBtn { background: #dc2626; color: #ffffff; border: none; }
"""


def _seg_distance(p, a, b):
    ax, ay, bx, by = a.x(), a.y(), b.x(), b.y()
    dx, dy = bx - ax, by - ay
    length_sq = dx * dx + dy * dy
    t = 0 if length_sq == 0 else max(0, min(1, ((p.x() - ax) * dx + (p.y() - ay) * dy) / length_sq))
    return math.hypot(p.x() - (ax + t * dx), p.y() - (ay + t * dy))


class MarkupCanvas(QWidget):
    changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(380)
        self.setMouseTracking(True)
        self.setCursor(Qt.CrossCursor)
        self.pixmap = QPixmap()
        self.marks = []
        self.tool = "bead"
        self._start = None        # 끌기 시작점 (비율 좌표)
        self._cursor = None       # 끌고 있는 현재 위치 (비율 좌표)
        self._bead = None         # 지금 그리고 있는 비드 mark

        self.popup = QFrame(self)
        self.popup.setObjectName("beadPopup")
        self.popup.setStyleSheet(POPUP_STYLE)
        row = QHBoxLayout(self.popup)
        row.setContentsMargins(8, 5, 8, 5)
        row.setSpacing(6)
        row.addWidget(QLabel("비드 그리기를 끝낼까요?"))
        self.end_btn = QPushButton("종료")
        self.end_btn.setObjectName("endBtn")
        self.end_btn.clicked.connect(self.end_bead)
        row.addWidget(self.end_btn)
        self.continue_btn = QPushButton("계속")
        self.continue_btn.clicked.connect(self.popup.hide)
        row.addWidget(self.continue_btn)
        self.popup.hide()

    # ---------------- 데이터 ----------------
    def set_content(self, pixmap, marks):
        self.end_bead()
        self.pixmap = pixmap if pixmap is not None else QPixmap()
        self.marks = marks      # 공정 데이터의 목록을 그대로 붙잡고 제자리에서 고친다
        self._start = self._cursor = None
        self.update()

    def has_image(self):
        return not self.pixmap.isNull()

    def set_tool(self, tool):
        self.end_bead()
        self._start = self._cursor = None
        self.tool = tool
        self.update()

    def end_bead(self):
        self._bead = None
        self.popup.hide()

    def undo(self):
        if self._bead is not None and self._bead["segs"]:
            self._bead["segs"].pop()
            if not self._bead["segs"]:
                self.marks.remove(self._bead)
                self.end_bead()
        elif self.marks:
            removed = self.marks.pop()
            if removed is self._bead:
                self.end_bead()
        else:
            return
        self.popup.hide()
        self.update()
        self.changed.emit()

    def clear_marks(self):
        self.end_bead()
        self.marks.clear()
        self.update()
        self.changed.emit()

    # ---------------- 좌표 ----------------
    def _image_rect(self):
        area = QRectF(self.rect()).adjusted(4, 4, -4, -4)
        if self.pixmap.isNull():
            return area
        size = self.pixmap.size().scaled(int(area.width()), int(area.height()), Qt.KeepAspectRatio)
        rect = QRectF(0, 0, size.width(), size.height())
        rect.moveCenter(area.center())
        return rect

    def to_widget(self, norm):
        rect = self._image_rect()
        return QPointF(rect.x() + norm[0] * rect.width(), rect.y() + norm[1] * rect.height())

    def to_norm(self, point):
        rect = self._image_rect()
        x = min(max((point.x() - rect.x()) / rect.width(), 0.0), 1.0)
        y = min(max((point.y() - rect.y()) / rect.height(), 0.0), 1.0)
        return [x, y]

    def _snap_targets(self):
        if self.tool == "bead":
            return [self._bead["segs"][-1][2:]] if self._bead and self._bead["segs"] else []
        if self.tool == "dim":
            targets = []
            for mark in self.marks:
                if mark["t"] == "bead":
                    for seg in mark["segs"]:
                        targets += [seg[:2], seg[2:]]
            return targets
        return []

    def _snap(self, point):
        best, best_distance = None, SNAP_PX
        for target in self._snap_targets():
            where = self.to_widget(target)
            distance = math.hypot(point.x() - where.x(), point.y() - where.y())
            if distance < best_distance:
                best, best_distance = list(target), distance
        return best if best is not None else self.to_norm(point)

    # ---------------- 마우스 ----------------
    def mousePressEvent(self, event):
        if event.button() == Qt.RightButton:
            self.end_bead()
            return
        if event.button() != Qt.LeftButton or not self.has_image():
            return
        if not self._image_rect().contains(event.position()):
            return
        if self.tool in LINE_TOOLS:
            self._start = self._snap(event.position())
            self._cursor = self.to_norm(event.position())
        elif self.tool in POINT_TOOLS:
            self.marks.append({"t": self.tool, "pts": [self.to_norm(event.position())]})
            self.update()
            self.changed.emit()
        elif self.tool == "erase":
            self._erase_at(event.position())

    def mouseMoveEvent(self, event):
        if self._start is not None:
            self._cursor = self.to_norm(event.position())
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() != Qt.LeftButton or self._start is None:
            return
        start, end = self._start, self.to_norm(event.position())
        self._start = self._cursor = None
        a, b = self.to_widget(start), self.to_widget(end)
        if math.hypot(a.x() - b.x(), a.y() - b.y()) < MIN_DRAG_PX:
            self.update()
            return
        if self.tool == "bead":
            if self._bead is None:
                self._bead = {"t": "bead", "segs": []}
                self.marks.append(self._bead)
            self._bead["segs"].append(start + end)
            self._show_popup(b)
        elif self.tool == "brush":
            self.marks.append({"t": "brush", "pts": [start, end]})
        elif self.tool == "dim":
            text, ok = QInputDialog.getText(self, "용접길이 표기", "용접길이 (숫자만, 단위 mm):")
            if ok and text.strip():
                self.marks.append({"t": "dim", "pts": [start, end], "text": text.strip()})
        self.update()
        self.changed.emit()

    def mouseDoubleClickEvent(self, event):
        if event.button() != Qt.LeftButton:
            return
        mark = self._hit(event.position(), kinds=("dim",))
        if mark is None:
            return
        text, ok = QInputDialog.getText(self, "용접길이 표기", "용접길이 (숫자만, 단위 mm):", text=mark.get("text", ""))
        if ok:
            if text.strip():
                mark["text"] = text.strip()
            else:
                self.marks.remove(mark)
            self.update()
            self.changed.emit()

    def _show_popup(self, anchor):
        self.popup.adjustSize()
        x = min(max(int(anchor.x()) + 12, 0), max(self.width() - self.popup.width(), 0))
        y = min(max(int(anchor.y()) + 12, 0), max(self.height() - self.popup.height(), 0))
        self.popup.move(x, y)
        self.popup.show()
        self.popup.raise_()

    # ---------------- 지우기 / 찾기 ----------------
    def _distance(self, mark, point):
        kind = mark["t"]
        if kind == "bead":
            return min((_seg_distance(point, self.to_widget(s[:2]), self.to_widget(s[2:])) for s in mark["segs"]), default=1e9)
        if kind in ("dim", "brush"):
            return _seg_distance(point, self.to_widget(mark["pts"][0]), self.to_widget(mark["pts"][1]))
        center = self.to_widget(mark["pts"][0])
        return math.hypot(point.x() - center.x(), point.y() - center.y()) - 6

    def _hit(self, point, kinds=None):
        best, best_distance = None, HIT_PX
        for mark in self.marks:
            if kinds and mark["t"] not in kinds:
                continue
            distance = self._distance(mark, point)
            if distance <= best_distance:
                best, best_distance = mark, distance
        return best

    def _erase_at(self, point):
        mark = self._hit(point)
        if mark is None:
            return
        if mark is self._bead:
            self.end_bead()
        self.marks.remove(mark)
        self.update()
        self.changed.emit()

    # ---------------- 그리기 ----------------
    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)
        painter.fillRect(self.rect(), QColor("#e2e8f0"))
        if self.pixmap.isNull():
            painter.setPen(QColor("#475569"))
            painter.setFont(QFont(self.font().family(), 11))
            painter.drawText(self.rect(), Qt.AlignCenter, "제품 이미지를 복사(Ctrl+C)한 뒤  [이미지 붙여넣기]  또는 Ctrl+V 를 눌러주세요.")
            return
        painter.drawPixmap(self._image_rect().toRect(), self.pixmap)
        for mark in self.marks:
            self._paint_mark(painter, mark)
        if self._start is not None and self._cursor is not None:
            pen = QPen(BEAD_COLOR if self.tool == "bead" else DIM_COLOR if self.tool == "dim" else BRUSH_COLOR, 2, Qt.DashLine)
            painter.setPen(pen)
            painter.drawLine(self.to_widget(self._start), self.to_widget(self._cursor))

    def _paint_mark(self, painter, mark):
        kind = mark["t"]
        if kind == "bead":
            pen = QPen(BEAD_COLOR, 3.5, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
            painter.setPen(pen)
            for seg in mark["segs"]:
                painter.drawLine(self.to_widget(seg[:2]), self.to_widget(seg[2:]))
        elif kind == "dim":
            a, b = self.to_widget(mark["pts"][0]), self.to_widget(mark["pts"][1])
            painter.setPen(QPen(DIM_COLOR, 2, Qt.SolidLine, Qt.RoundCap))
            painter.drawLine(a, b)
            self._paint_text(painter, mark.get("text", ""), a, b)
        elif kind == "brush":
            painter.setPen(QPen(BRUSH_COLOR, 3, Qt.DashLine, Qt.RoundCap))
            a, b = self.to_widget(mark["pts"][0]), self.to_widget(mark["pts"][1])
            painter.drawLine(a, b)
            painter.setPen(QPen(BRUSH_COLOR, 2))
            for end in (a, b):
                painter.drawEllipse(end, 3.5, 3.5)
        else:
            self._paint_marker(painter, kind, self.to_widget(mark["pts"][0]))

    @staticmethod
    def _paint_text(painter, text, a, b):
        if not text:
            return
        font = QFont(painter.font())
        font.setPixelSize(13)
        font.setBold(True)
        painter.setFont(font)
        width = painter.fontMetrics().horizontalAdvance(text) + 10
        height = painter.fontMetrics().height() + 2
        # 선이 오른쪽으로 가면 끝점 오른쪽에, 왼쪽으로 가면 끝점 왼쪽에 적는다
        x = b.x() + 6 if b.x() >= a.x() else b.x() - 6 - width
        rect = QRectF(x, b.y() - height / 2, width, height)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(255, 255, 255, 215))
        painter.drawRoundedRect(rect, 3, 3)
        painter.setPen(DIM_COLOR)
        painter.drawText(rect, Qt.AlignCenter, text)
        painter.setBrush(Qt.NoBrush)

    @staticmethod
    def _paint_marker(painter, kind, c):
        painter.setBrush(Qt.NoBrush)
        if kind == "tack":      # 가접: 노란 마름모
            painter.setPen(QPen(QColor("#000000"), 1.5))
            painter.setBrush(QColor("#facc15"))
            painter.drawPolygon(QPolygonF([QPointF(c.x(), c.y() - 9), QPointF(c.x() + 9, c.y()),
                                           QPointF(c.x(), c.y() + 9), QPointF(c.x() - 9, c.y())]))
        elif kind == "lot":     # LOT NO 타각: 보라색 네모 + LOT
            rect = QRectF(c.x() - 18, c.y() - 9, 36, 18)
            painter.setPen(QPen(QColor("#ffffff"), 1.5))
            painter.setBrush(QColor("#7c3aed"))
            painter.drawRoundedRect(rect, 3, 3)
            font = QFont(painter.font())
            font.setPixelSize(10)
            font.setBold(True)
            painter.setFont(font)
            painter.setPen(QColor("#ffffff"))
            painter.drawText(rect, Qt.AlignCenter, "LOT")
        elif kind == "eye":     # 육안 검사: 눈 모양
            painter.setPen(QPen(QColor("#1d4ed8"), 2))
            painter.setBrush(QColor("#ffffff"))
            painter.drawEllipse(c, 15, 9)
            painter.setBrush(QColor("#1d4ed8"))
            painter.drawEllipse(c, 4.5, 4.5)
        elif kind == "spatter":  # 스패터 확인: 주황 별
            points = []
            for i in range(16):
                radius = 12 if i % 2 == 0 else 5
                angle = math.pi * i / 8 - math.pi / 2
                points.append(QPointF(c.x() + radius * math.cos(angle), c.y() + radius * math.sin(angle)))
            painter.setPen(QPen(QColor("#9a3412"), 1.2))
            painter.setBrush(QColor("#f97316"))
            painter.drawPolygon(QPolygonF(points))
        elif kind == "check":   # 품질 확인: 초록 원 + 체크
            painter.setPen(QPen(QColor("#ffffff"), 1.5))
            painter.setBrush(QColor("#16a34a"))
            painter.drawEllipse(c, 11, 11)
            path = QPainterPath()
            path.moveTo(c.x() - 5, c.y())
            path.lineTo(c.x() - 1, c.y() + 4)
            path.lineTo(c.x() + 6, c.y() - 4)
            painter.setPen(QPen(QColor("#ffffff"), 2.5, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            painter.setBrush(Qt.NoBrush)
            painter.drawPath(path)


class WeldMarkupPanel(QWidget):
    """이미지 붙여넣기 + 도구 모음 + 그림판."""

    imageChanged = Signal(object)   # QImage, 지우면 None
    marksChanged = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        actions = QHBoxLayout()
        actions.setSpacing(6)
        self.paste_btn = QPushButton("이미지 붙여넣기 (Ctrl+V)")
        self.paste_btn.setStyleSheet(PRIMARY_STYLE)
        self.paste_btn.clicked.connect(self.paste_image)
        self.file_btn = QPushButton("파일 선택")
        self.file_btn.setStyleSheet(BUTTON_STYLE)
        self.file_btn.clicked.connect(self.choose_file)
        self.remove_btn = QPushButton("이미지 삭제")
        self.remove_btn.setStyleSheet(BUTTON_STYLE)
        self.remove_btn.clicked.connect(self.remove_image)
        self.undo_btn = QPushButton("되돌리기")
        self.undo_btn.setStyleSheet(BUTTON_STYLE)
        self.clear_btn = QPushButton("표시 전체 지우기")
        self.clear_btn.setStyleSheet(BUTTON_STYLE)
        for button in (self.paste_btn, self.file_btn, self.remove_btn):
            actions.addWidget(button)
        actions.addSpacing(12)
        actions.addWidget(self.undo_btn)
        actions.addWidget(self.clear_btn)
        actions.addStretch(1)
        layout.addLayout(actions)

        tools = QGridLayout()
        tools.setHorizontalSpacing(6)
        tools.setVerticalSpacing(6)
        self.group = QButtonGroup(self)
        self.group.setExclusive(True)
        self.tool_buttons = {}
        for index, (key, text) in enumerate(TOOLS):
            button = QPushButton(text)
            button.setCheckable(True)
            button.setStyleSheet(BUTTON_STYLE)
            button.clicked.connect(lambda _c=False, k=key: self.set_tool(k))
            self.group.addButton(button)
            self.tool_buttons[key] = button
            tools.addWidget(button, index // 5, index % 5)
        tools.setColumnStretch(5, 1)
        layout.addLayout(tools)

        self.hint = QLabel("")
        self.hint.setWordWrap(True)
        self.hint.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Minimum)
        self.hint.setStyleSheet("color: #64748b; font-size: 10px;")
        layout.addWidget(self.hint)

        self.canvas = MarkupCanvas()
        self.canvas.changed.connect(self.marksChanged)
        layout.addWidget(self.canvas)
        self.undo_btn.clicked.connect(self.canvas.undo)
        self.clear_btn.clicked.connect(self._confirm_clear)

        shortcut = QShortcut(QKeySequence.Paste, self)
        shortcut.setContext(Qt.WidgetWithChildrenShortcut)
        shortcut.activated.connect(self.paste_image)
        self.set_tool("bead")

    def set_content(self, pixmap, marks):
        self.canvas.set_content(pixmap, marks)

    def set_tool(self, tool):
        self.tool_buttons[tool].setChecked(True)
        self.canvas.set_tool(tool)
        self.hint.setText(TOOL_HINTS[tool])

    # ---------------- 이미지 ----------------
    def paste_image(self):
        image = QGuiApplication.clipboard().image()
        if image.isNull():
            QMessageBox.information(self, "이미지 붙여넣기", "클립보드에 이미지가 없습니다.\n제품 이미지를 복사(Ctrl+C)한 뒤 다시 눌러주세요.")
            return
        self._set_image(image)

    def choose_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "제품 이미지 선택", "", "이미지 (*.png *.jpg *.jpeg *.bmp *.gif)")
        if path:
            pixmap = QPixmap(path)
            if pixmap.isNull():
                QMessageBox.warning(self, "알림", "이미지를 열 수 없습니다.")
                return
            self._set_image(pixmap.toImage())

    def remove_image(self):
        if self.canvas.has_image():
            if QMessageBox.question(self, "삭제 확인", "제품 이미지를 삭제할까요? (그려 둔 표시는 남습니다)") != QMessageBox.Yes:
                return
            self.canvas.set_content(QPixmap(), self.canvas.marks)
            self.imageChanged.emit(None)

    def _set_image(self, image):
        self.canvas.set_content(QPixmap.fromImage(image), self.canvas.marks)
        self.imageChanged.emit(image)

    def _confirm_clear(self):
        if self.canvas.marks and QMessageBox.question(self, "삭제 확인", "그려 둔 표시를 모두 지울까요?") != QMessageBox.Yes:
            return
        self.canvas.clear_marks()
