from PySide6.QtCore import QMimeData, QPoint, Qt, Signal
from PySide6.QtGui import QColor, QDrag, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QComboBox, QHBoxLayout, QLabel, QPushButton, QWidget

NODE_MIME = "application/x-pe-ams-node"


class PaletteHandle(QPushButton):
    """레이아웃 위로 드래그하면 새 공정 노드를 생성하는 팔레트 버튼."""

    def __init__(self, text="공정 NO", parent=None):
        super().__init__(text, parent)
        self.setCursor(Qt.OpenHandCursor)
        self.setStyleSheet("""
            QPushButton {
                background: #334155;
                color: #ffffff;
                font-size: 11px;
                font-weight: 600;
                padding: 6px 12px;
                border: 1px solid #475569;
                border-radius: 6px;
            }
            QPushButton:hover { background: #475569; }
        """)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            drag = QDrag(self)
            mime = QMimeData()
            mime.setData(NODE_MIME, b"1")
            drag.setMimeData(mime)
            drag.exec(Qt.CopyAction)
        super().mousePressEvent(event)


class CadNodeWidget(QWidget):
    removed = Signal(object)
    changed = Signal()

    def __init__(self, node_data, get_processes, parent=None):
        super().__init__(parent)
        self.node_data = node_data
        self.get_processes = get_processes
        self._dragging = False
        self._drag_start_global = QPoint()
        self._drag_start_xy = (0.0, 0.0)

        self.setCursor(Qt.OpenHandCursor)
        self.setStyleSheet("""
            CadNodeWidget {
                background-color: #2563eb;
                border: 2px solid #ffffff;
                border-radius: 6px;
            }
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 5, 8, 5)
        layout.setSpacing(4)

        self.label = QLabel()
        self.label.setStyleSheet("color: #ffffff; font-weight: 700; font-size: 11px; background: transparent; border: none;")
        layout.addWidget(self.label)

        self.combo = QComboBox()
        self.combo.setStyleSheet("""
            QComboBox {
                background: #1d4ed8;
                color: #ffffff;
                font-size: 11px;
                font-weight: 600;
                border: 1px solid #1e40af;
                border-radius: 4px;
                padding: 2px 6px;
            }
            QComboBox QAbstractItemView {
                background: #ffffff;
                color: #000000;
                selection-background-color: #dbeafe;
                selection-color: #000000;
            }
        """)
        self.combo.currentIndexChanged.connect(self._on_combo_changed)
        self.combo.hide()
        layout.addWidget(self.combo)

        self.delete_btn = QPushButton("x")
        self.delete_btn.setFixedSize(18, 18)
        self.delete_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: #dbeafe;
                font-weight: 700;
                border: none;
            }
            QPushButton:hover { color: #fecaca; }
        """)
        self.delete_btn.clicked.connect(lambda: self.removed.emit(self))
        self.delete_btn.hide()
        layout.addWidget(self.delete_btn)

        self.refresh()

    def refresh(self):
        processes = self.get_processes()
        pid = self.node_data.get("process_id", "")
        ids = [p["id"] for p in processes]
        self.label.setText(pid if pid in ids else "(공정 선택)")

        self.combo.blockSignals(True)
        self.combo.clear()
        self.combo.addItem("(선택)", "")
        for p in processes:
            self.combo.addItem(p["id"], p["id"])
        idx = self.combo.findData(pid)
        self.combo.setCurrentIndex(idx if idx >= 0 else 0)
        self.combo.blockSignals(False)
        self.adjustSize()

    def _on_combo_changed(self, _index):
        self.node_data["process_id"] = self.combo.currentData() or ""
        self.refresh()
        self.changed.emit()

    def enterEvent(self, event):
        self.label.hide()
        self.combo.show()
        self.delete_btn.show()
        self.adjustSize()
        if self.parent():
            self.parent().reposition_node(self)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.combo.hide()
        self.delete_btn.hide()
        self.label.show()
        self.adjustSize()
        if self.parent():
            self.parent().reposition_node(self)
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            if event.modifiers() & Qt.ControlModifier:
                self.parent().duplicate_node(self)
                return
            self._dragging = True
            self.setCursor(Qt.ClosedHandCursor)
            self._drag_start_global = event.globalPosition().toPoint()
            self._drag_start_xy = (self.node_data["x"], self.node_data["y"])
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._dragging and self.parent():
            delta = event.globalPosition().toPoint() - self._drag_start_global
            parent_rect = self.parent().rect()
            if parent_rect.width() > 0 and parent_rect.height() > 0:
                dx_pct = delta.x() / parent_rect.width() * 100
                dy_pct = delta.y() / parent_rect.height() * 100
                new_x = max(0.0, min(100.0, self._drag_start_xy[0] + dx_pct))
                new_y = max(0.0, min(100.0, self._drag_start_xy[1] + dy_pct))
                self.node_data["x"] = new_x
                self.node_data["y"] = new_y
                self.parent().reposition_node(self)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self._dragging:
            self._dragging = False
            self.setCursor(Qt.OpenHandCursor)
            self.changed.emit()
        super().mouseReleaseEvent(event)


class CadDropZone(QWidget):
    """공정 레이아웃 이미지 + 자유롭게 드래그 가능한 공정 노드 캔버스."""

    changed = Signal()

    def __init__(self, get_processes, parent=None):
        super().__init__(parent)
        self.get_processes = get_processes
        self.image_path = ""
        self.nodes_data = []
        self.node_widgets = []
        self.setAcceptDrops(True)
        self.setMinimumHeight(320)

        self.placeholder = QLabel("드래그 가능\n레이아웃 업로드", self)
        self.placeholder.setAlignment(Qt.AlignCenter)
        self.placeholder.setStyleSheet("color: #94a3b8; font-size: 15px; font-weight: 700; background: transparent;")

    def set_data(self, image_path, nodes_data):
        self.image_path = image_path or ""
        self.nodes_data = nodes_data
        self.rebuild_nodes()
        self._update_placeholder()
        self.update()

    def set_image(self, image_path):
        self.image_path = image_path or ""
        self._update_placeholder()
        self.update()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.placeholder.setGeometry(self.rect())
        self.reposition_all_nodes()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#181d24"))

        pen = QPen(QColor("#2d3748"))
        pen.setWidth(1)
        painter.setPen(pen)
        step = 16
        for x in range(0, self.width(), step):
            for y in range(0, self.height(), step):
                painter.drawPoint(x, y)

        if self.image_path:
            pixmap = QPixmap(self.image_path)
            if not pixmap.isNull():
                scaled = pixmap.scaled(self.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
                x = (self.width() - scaled.width()) // 2
                y = (self.height() - scaled.height()) // 2
                painter.drawPixmap(x, y, scaled)
        painter.end()

    def dragEnterEvent(self, event):
        if event.mimeData().hasFormat(NODE_MIME):
            event.acceptProposedAction()

    def dragMoveEvent(self, event):
        if event.mimeData().hasFormat(NODE_MIME):
            event.acceptProposedAction()

    def dropEvent(self, event):
        pos = event.position().toPoint()
        x_pct = (pos.x() / self.width() * 100) if self.width() else 0
        y_pct = (pos.y() / self.height() * 100) if self.height() else 0
        processes = self.get_processes()
        default_pid = processes[0]["id"] if processes else ""
        node = {"x": x_pct, "y": y_pct, "process_id": default_pid}
        self.nodes_data.append(node)
        self.add_node_widget(node)
        event.acceptProposedAction()
        self.changed.emit()

    def add_node_widget(self, node):
        widget = CadNodeWidget(node, self.get_processes, self)
        widget.removed.connect(self.remove_node)
        widget.changed.connect(self.changed.emit)
        widget.show()
        self.node_widgets.append(widget)
        self.reposition_node(widget)

    def duplicate_node(self, node_widget):
        new_node = dict(node_widget.node_data)
        new_node["x"] = min(100.0, new_node["x"] + 3)
        new_node["y"] = min(100.0, new_node["y"] + 3)
        self.nodes_data.append(new_node)
        self.add_node_widget(new_node)
        self.changed.emit()

    def remove_node(self, node_widget):
        if node_widget.node_data in self.nodes_data:
            self.nodes_data.remove(node_widget.node_data)
        if node_widget in self.node_widgets:
            self.node_widgets.remove(node_widget)
        node_widget.deleteLater()
        self.changed.emit()

    def rebuild_nodes(self):
        for w in self.node_widgets:
            w.deleteLater()
        self.node_widgets = []
        for node in self.nodes_data:
            self.add_node_widget(node)

    def reposition_node(self, widget):
        size = widget.sizeHint()
        w, h = size.width(), size.height()
        x = int(widget.node_data["x"] / 100 * self.width() - w / 2)
        y = int(widget.node_data["y"] / 100 * self.height() - h / 2)
        widget.setGeometry(x, y, w, h)

    def reposition_all_nodes(self):
        for w in self.node_widgets:
            self.reposition_node(w)

    def refresh_all_nodes(self):
        for w in self.node_widgets:
            w.refresh()
            self.reposition_node(w)

    def _update_placeholder(self):
        self.placeholder.setVisible(not self.image_path)
