from PySide6.QtWidgets import QGraphicsView, QGraphicsScene, QGraphicsPixmapItem, QGraphicsLineItem, QGraphicsTextItem, QGraphicsEllipseItem, QGraphicsPolygonItem, QMenu
from PySide6.QtCore import Qt, Signal, QPointF
from PySide6.QtGui import QPainter, QPen, QColor, QPolygonF, QAction, QFont

class ToolMode:
    NONE = 0
    CALIBRATE = 1
    MEASURE_LINE = 2
    CIRCLE_FIXED = 3
    POLYGON_AREA = 4
    TEXT = 5
    SELECT = 6

class PDFCanvas(QGraphicsView):
    calibration_points_selected = Signal(QPointF, QPointF)
    measurement_complete = Signal(QPointF, QPointF)
    polygon_complete = Signal(list) # list of QPointF
    point_selected = Signal(QPointF) # For circle and text
    
    # Selection/Editing signals
    item_selected = Signal(str) # id
    selection_cleared = Signal()
    item_moved = Signal(str, QPointF) # id, delta
    request_delete = Signal(str) # id

    def __init__(self, parent=None):
        super().__init__(parent)
        self.scene = QGraphicsScene(self)
        self.setScene(self.scene)
        
        # Performance settings
        self.setRenderHint(QPainter.Antialiasing)
        self.setRenderHint(QPainter.SmoothPixmapTransform)
        self.setViewportUpdateMode(QGraphicsView.FullViewportUpdate)
        
        # Panning settings
        self.setDragMode(QGraphicsView.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        
        self.background_item = None
        self.tool_mode = ToolMode.NONE
        
        # Interaction state
        self.temp_points = []
        self.temp_line = None
        self.temp_poly = None

    def set_tool_mode(self, mode):
        self.tool_mode = mode
        self.temp_points = []
        self._clear_temp_items()

        if mode == ToolMode.SELECT:
            self.setDragMode(QGraphicsView.NoDrag)
            self.setCursor(Qt.ArrowCursor)
            self._set_items_interactive(True)
        elif mode == ToolMode.NONE:
            self.setDragMode(QGraphicsView.ScrollHandDrag)
            self.setCursor(Qt.ArrowCursor)
            self._set_items_interactive(False)
        else:
            self.setDragMode(QGraphicsView.NoDrag)
            self.setCursor(Qt.CrossCursor)
            self._set_items_interactive(False)

    def _set_items_interactive(self, interactive):
        for item in self.scene.items():
            if item == self.background_item: continue
            # Only enable for the main annotation items (those with IDs)
            if item.data(0):
                item.setFlag(QGraphicsLineItem.ItemIsSelectable, interactive)
                item.setFlag(QGraphicsLineItem.ItemIsMovable, interactive)
                # Ensure the text items attached to lines etc also move or are handled
                # For simplicity, we'll focus on the main shapes.

    def _clear_temp_items(self):
        if self.temp_line:
            self.scene.removeItem(self.temp_line)
            self.temp_line = None
        if self.temp_poly:
            self.scene.removeItem(self.temp_poly)
            self.temp_poly = None

    def set_page_image(self, pixmap):
        self.scene.clear()
        self.background_item = QGraphicsPixmapItem(pixmap)
        self.background_item.setZValue(-1)
        self.scene.addItem(self.background_item)
        self.scene.setSceneRect(self.background_item.boundingRect())

    def wheelEvent(self, event):
        if event.modifiers() & Qt.ControlModifier:
            zoom_in_factor = 1.25
            zoom_out_factor = 1 / zoom_in_factor
            zoom_factor = zoom_in_factor if event.angleDelta().y() > 0 else zoom_out_factor
            self.scale(zoom_factor, zoom_factor)
        else:
            super().wheelEvent(event)

    def mousePressEvent(self, event):
        if self.tool_mode == ToolMode.SELECT:
            if event.button() == Qt.LeftButton:
                pos = self.mapToScene(event.pos())
                item = self.scene.itemAt(pos, self.transform())
                if item and item != self.background_item:
                    while item and not item.data(0) and item.parentItem():
                        item = item.parentItem()
                    if item and item.data(0):
                        self.item_selected.emit(item.data(0))
                    else:
                        self.selection_cleared.emit()
                else:
                    self.selection_cleared.emit()
            super().mousePressEvent(event)
            return

        if self.tool_mode == ToolMode.NONE:
            super().mousePressEvent(event)
            return

        pos = self.mapToScene(event.pos())
        
        if event.button() == Qt.LeftButton:
            if self.tool_mode in [ToolMode.CALIBRATE, ToolMode.MEASURE_LINE]:
                self.temp_points.append(pos)
                if len(self.temp_points) == 1:
                    self.temp_line = QGraphicsLineItem(pos.x(), pos.y(), pos.x(), pos.y())
                    pen = QPen(QColor("red"), 2)
                    pen.setCosmetic(True)
                    self.temp_line.setPen(pen)
                    self.scene.addItem(self.temp_line)
                elif len(self.temp_points) == 2:
                    p1, p2 = self.temp_points
                    if self.tool_mode == ToolMode.CALIBRATE:
                        self.calibration_points_selected.emit(p1, p2)
                    else:
                        self.measurement_complete.emit(p1, p2)
                    self._finish_tool()

            elif self.tool_mode == ToolMode.POLYGON_AREA:
                self.temp_points.append(pos)
                if not self.temp_poly:
                    self.temp_poly = QGraphicsPolygonItem()
                    pen = QPen(QColor("blue"), 2)
                    pen.setCosmetic(True)
                    self.temp_poly.setPen(pen)
                    self.temp_poly.setBrush(QColor(0, 0, 255, 50))
                    self.scene.addItem(self.temp_poly)
                self.temp_poly.setPolygon(QPolygonF(self.temp_points))

            elif self.tool_mode in [ToolMode.CIRCLE_FIXED, ToolMode.TEXT]:
                self.point_selected.emit(pos)
                self._finish_tool()

        elif event.button() == Qt.RightButton:
            if self.tool_mode == ToolMode.POLYGON_AREA and len(self.temp_points) >= 3:
                self.polygon_complete.emit(self.temp_points)
                self._finish_tool()

    def _finish_tool(self):
        self._clear_temp_items()
        self.temp_points = []
        self.set_tool_mode(ToolMode.NONE)

    def mouseMoveEvent(self, event):
        pos = self.mapToScene(event.pos())
        if self.temp_line and len(self.temp_points) == 1:
            self.temp_line.setLine(self.temp_points[0].x(), self.temp_points[0].y(), pos.x(), pos.y())
        elif self.temp_poly and len(self.temp_points) >= 1:
            preview_points = self.temp_points + [pos]
            self.temp_poly.setPolygon(QPolygonF(preview_points))
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self.tool_mode == ToolMode.SELECT:
            # Check if any item moved
            for item in self.scene.selectedItems():
                item_id = item.data(0)
                last_pos = item.data(1)
                if item_id and last_pos is not None:
                    delta = item.pos() - last_pos
                    if delta.x() != 0 or delta.y() != 0:
                        self.item_moved.emit(item_id, delta)
                        # Store current pos as the new baseline
                        item.setData(1, item.pos())
        super().mouseReleaseEvent(event)

    def add_line_annotation(self, p1, p2, text="", color="red", item_id=None, font_family="Arial", font_size=12):
        line = QGraphicsLineItem(p1.x(), p1.y(), p2.x(), p2.y())
        pen = QPen(QColor(color), 2)
        pen.setCosmetic(True)
        line.setPen(pen)
        if item_id: 
            line.setData(0, item_id)
            line.setData(1, line.pos()) # store initial pos (0,0)
        self.scene.addItem(line)
        
        txt_item = self._add_text_item(text, (p1.x() + p2.x()) / 2, (p1.y() + p2.y()) / 2, color, font_family, font_size)
        if txt_item:
            txt_item.setParentItem(line) # Move with line

    def add_polygon_annotation(self, points, text="", color="blue", item_id=None, font_family="Arial", font_size=12):
        poly = QGraphicsPolygonItem(QPolygonF(points))
        pen = QPen(QColor(color), 2)
        pen.setCosmetic(True)
        poly.setPen(pen)
        poly.setBrush(QColor(QColor(color).red(), QColor(color).green(), QColor(color).blue(), 30))
        if item_id: 
            poly.setData(0, item_id)
            poly.setData(1, poly.pos()) # store initial pos (0,0)
        self.scene.addItem(poly)
        
        avg_x = sum(p.x() for p in points) / len(points)
        avg_y = sum(p.y() for p in points) / len(points)
        txt_item = self._add_text_item(text, avg_x, avg_y, color, font_family, font_size)
        if txt_item:
            txt_item.setParentItem(poly)

    def add_circle_annotation(self, center, radius_px, text="", color="green", item_id=None, font_family="Arial", font_size=12):
        circle = QGraphicsEllipseItem(center.x() - radius_px, center.y() - radius_px, radius_px * 2, radius_px * 2)
        pen = QPen(QColor(color), 2)
        pen.setCosmetic(True)
        circle.setPen(pen)
        if item_id: 
            circle.setData(0, item_id)
            circle.setData(1, circle.pos()) # store initial pos (0,0)
        self.scene.addItem(circle)
        
        txt_item = self._add_text_item(text, center.x(), center.y() - radius_px - 10, color, font_family, font_size)
        if txt_item:
            txt_item.setParentItem(circle)

    def add_text_annotation(self, pos, text, color="black", item_id=None, font_family="Arial", font_size=12):
        txt_item = self._add_text_item(text, pos.x(), pos.y(), color, font_family, font_size)
        if txt_item and item_id:
            txt_item.setData(0, item_id)
            txt_item.setData(1, txt_item.pos()) # store initial pos (x,y)

    def _add_text_item(self, text, x, y, color, font_family="Arial", font_size=12):
        if not text: return None
        text_item = QGraphicsTextItem(text)
        text_item.setDefaultTextColor(QColor(color))
        
        font = QFont(font_family, font_size)
        text_item.setFont(font)
        
        text_item.setPos(x, y)
        # Removed ItemIgnoresTransformations to make text scale with the drawing
        self.scene.addItem(text_item)
        return text_item

    def reset_view(self):
        self.resetTransform()
        if self.background_item:
            self.fitInView(self.background_item, Qt.KeepAspectRatio)
