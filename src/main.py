import sys
import os
import json
import fitz # PyMuPDF
from PySide6.QtWidgets import (QApplication, QMainWindow, QFileDialog, 
                             QToolBar, QLabel, QSpinBox, QHBoxLayout, 
                             QWidget, QVBoxLayout, QInputDialog, QMessageBox,
                             QColorDialog, QDockWidget)
from PySide6.QtGui import QAction
from PySide6.QtCore import Qt

from pdf_handler import PDFHandler
from canvas import PDFCanvas, ToolMode
from models import DrawingModel, Annotation
from property_panel import PropertyPanel

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("建築図面注釈・計測ツール")
        self.resize(1200, 800)

        self.pdf_handler = PDFHandler()
        self.model = DrawingModel()
        self.current_page = 0

        self.setup_ui()

    def setup_ui(self):
        # Canvas
        self.canvas = PDFCanvas()
        self.canvas.calibration_points_selected.connect(self.on_calibration_selected)
        self.canvas.measurement_complete.connect(self.on_measurement_complete)
        self.canvas.polygon_complete.connect(self.on_polygon_complete)
        self.canvas.point_selected.connect(self.on_point_selected)
        
        # Selection/Property signals
        self.canvas.item_selected.connect(self.on_item_selected)
        self.canvas.selection_cleared.connect(self.on_selection_cleared)
        self.canvas.item_moved.connect(self.on_item_moved)
        
        self.setCentralWidget(self.canvas)

        # Property Panel (Dock)
        self.prop_dock = QDockWidget("プロパティ", self)
        self.prop_panel = PropertyPanel()
        self.prop_panel.attribute_changed.connect(self.on_property_changed)
        self.prop_panel.delete_requested.connect(self.on_delete_item)
        self.prop_dock.setWidget(self.prop_panel)
        self.addDockWidget(Qt.RightDockWidgetArea, self.prop_dock)

        # Toolbar
        self.toolbar = QToolBar("Main Toolbar")
        self.addToolBar(self.toolbar)

        # File Actions
        open_action = QAction("PDFを開く", self)
        open_action.triggered.connect(self.open_pdf)
        self.toolbar.addAction(open_action)

        swap_action = QAction("背景差し替え", self)
        swap_action.triggered.connect(self.swap_pdf)
        self.toolbar.addAction(swap_action)

        save_action = QAction("保存", self)
        save_action.triggered.connect(self.save_project)
        self.toolbar.addAction(save_action)

        load_action = QAction("読込", self)
        load_action.triggered.connect(self.load_project)
        self.toolbar.addAction(load_action)

        export_action = QAction("PDF書き出し", self)
        export_action.triggered.connect(self.export_pdf)
        self.toolbar.addAction(export_action)

        self.toolbar.addSeparator()

        # Selection Tool
        select_action = QAction("選択・移動", self)
        select_action.triggered.connect(lambda: self.canvas.set_tool_mode(ToolMode.SELECT))
        self.toolbar.addAction(select_action)

        self.toolbar.addSeparator()

        # Tools
        calibrate_action = QAction("キャリブレーション", self)
        calibrate_action.triggered.connect(lambda: self.canvas.set_tool_mode(ToolMode.CALIBRATE))
        self.toolbar.addAction(calibrate_action)

        measure_action = QAction("距離計測", self)
        measure_action.triggered.connect(lambda: self._check_calib_and_set_mode(ToolMode.MEASURE_LINE))
        self.toolbar.addAction(measure_action)

        area_action = QAction("面積計測", self)
        area_action.triggered.connect(lambda: self._check_calib_and_set_mode(ToolMode.POLYGON_AREA))
        self.toolbar.addAction(area_action)

        circle_action = QAction("15m円", self)
        circle_action.triggered.connect(lambda: self._check_calib_and_set_mode(ToolMode.CIRCLE_FIXED))
        self.toolbar.addAction(circle_action)

        text_action = QAction("テキスト", self)
        text_action.triggered.connect(lambda: self.canvas.set_tool_mode(ToolMode.TEXT))
        self.toolbar.addAction(text_action)

        self.toolbar.addSeparator()

        # Page Navigation
        self.prev_btn = QAction("前へ", self)
        self.prev_btn.triggered.connect(self.prev_page)
        self.prev_btn.setEnabled(False)
        self.toolbar.addAction(self.prev_btn)

        self.page_label = QLabel(" ページ: 0 / 0 ")
        self.toolbar.addWidget(self.page_label)

        self.next_btn = QAction("次へ", self)
        self.next_btn.triggered.connect(self.next_page)
        self.next_btn.setEnabled(False)
        self.toolbar.addAction(self.next_btn)

        self.toolbar.addSeparator()

        reset_btn = QAction("表示リセット", self)
        reset_btn.triggered.connect(self.canvas.reset_view)
        self.toolbar.addAction(reset_btn)

        # Scale Label
        self.scale_label = QLabel(" スケール: 未設定 ")
        self.statusBar().addPermanentWidget(self.scale_label)

    def _check_calib_and_set_mode(self, mode):
        if not self.model.is_calibrated:
            QMessageBox.warning(self, "警告", "先にキャリブレーションを行ってください。")
            return
        self.canvas.set_tool_mode(mode)

    def on_calibration_selected(self, p1, p2):
        dist_mm, ok = QInputDialog.getDouble(self, "キャリブレーション", "実寸法を入力してください (mm):", 1000, 0, 1000000, 1)
        if ok:
            if self.model.set_calibration(p1, p2, dist_mm):
                self._update_scale_label()
                QMessageBox.information(self, "完了", "キャリブレーションが完了しました。")

    def _update_scale_label(self):
        if self.model.is_calibrated:
            self.scale_label.setText(f" スケール: {self.model.scale_factor:.4f} mm/px ")
        else:
            self.scale_label.setText(" スケール: 未設定 ")

    def on_measurement_complete(self, p1, p2):
        dist_mm = self.model.calculate_real_distance(p1, p2)
        text = f"{dist_mm:.1f} mm"
        ann = self._add_to_model("line", [p1, p2], dist_mm, text=text)
        self.canvas.add_line_annotation(p1, p2, text=text, item_id=ann.id, font_family=ann.font_family, font_size=ann.font_size)

    def on_polygon_complete(self, points):
        area_mm2 = self.model.calculate_real_area(points)
        area_m2 = area_mm2 / 1_000_000.0
        text = f"{area_m2:.2f} m²"
        ann = self._add_to_model("polygon", points, area_mm2, text=text)
        self.canvas.add_polygon_annotation(points, text=text, item_id=ann.id, font_family=ann.font_family, font_size=ann.font_size)

    def on_point_selected(self, pos):
        if self.canvas.tool_mode == ToolMode.CIRCLE_FIXED:
            radius_mm = 15000 
            radius_px = radius_mm / self.model.scale_factor
            text = "R=15m"
            ann = self._add_to_model("circle", [pos], radius_mm, text=text)
            self.canvas.add_circle_annotation(pos, radius_px, text=text, item_id=ann.id, font_family=ann.font_family, font_size=ann.font_size)
        elif self.canvas.tool_mode == ToolMode.TEXT:
            text, ok = QInputDialog.getText(self, "テキスト入力", "注釈を入力してください:")
            if ok and text:
                ann = self._add_to_model("text", [pos], text=text)
                self.canvas.add_text_annotation(pos, text, item_id=ann.id, font_family=ann.font_family, font_size=ann.font_size)

    def _add_to_model(self, type, points, real_value=0.0, text=""):
        ann = Annotation(type)
        ann.points = points
        ann.real_value = real_value
        ann.text = text
        ann.page_num = self.current_page
        self.model.annotations.append(ann)
        return ann

    def on_item_selected(self, item_id):
        for ann in self.model.annotations:
            if ann.id == item_id:
                self.prop_panel.set_item_data(ann.id, ann.type, ann.text, ann.color, ann.font_family, ann.font_size)
                break

    def on_selection_cleared(self):
        self.prop_panel.clear_panel()

    def on_property_changed(self, item_id, attrs):
        for ann in self.model.annotations:
            if ann.id == item_id:
                if "text" in attrs:
                    ann.text = attrs["text"]
                if "color" in attrs:
                    ann.color = attrs["color"]
                if "font_family" in attrs:
                    ann.font_family = attrs["font_family"]
                if "font_size" in attrs:
                    ann.font_size = attrs["font_size"]
                self.update_page_view()
                break

    def on_item_moved(self, item_id, delta):
        for ann in self.model.annotations:
            if ann.id == item_id:
                ann.points = [p + delta for p in ann.points]
                break

    def on_delete_item(self, item_id):
        self.model.annotations = [a for a in self.model.annotations if a.id != item_id]
        self.update_page_view()

    def open_pdf(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "PDF図面を開く", "", "PDF Files (*.pdf)")
        if file_path:
            if self.pdf_handler.open_file(file_path):
                self.model.pdf_path = file_path
                self.current_page = 0
                self.update_page_view()
                self.canvas.reset_view()

    def swap_pdf(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "背景PDFを差し替え", "", "PDF Files (*.pdf)")
        if file_path:
            if self.pdf_handler.open_file(file_path):
                self.model.pdf_path = file_path
                self.update_page_view()

    def save_project(self):
        file_path, _ = QFileDialog.getSaveFileName(self, "プロジェクトを保存", "", "JSON Files (*.json)")
        if file_path:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(self.model.to_dict(), f, ensure_ascii=False, indent=2)
            QMessageBox.information(self, "保存", "プロジェクトを保存しました。")

    def load_project(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "プロジェクトを読み込み", "", "JSON Files (*.json)")
        if file_path:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            self.model = DrawingModel.from_dict(data)
            self._update_scale_label()
            
            if self.model.pdf_path and os.path.exists(self.model.pdf_path):
                self.pdf_handler.open_file(self.model.pdf_path)
            else:
                QMessageBox.warning(self, "警告", "PDFファイルが見つかりません。再選択してください。")
                self.open_pdf()
            
            self.current_page = 0
            self.update_page_view()
            self.canvas.reset_view()

    def export_pdf(self):
        if not self.pdf_handler.doc or not self.model.pdf_path:
            return
        
        file_path, _ = QFileDialog.getSaveFileName(self, "PDFを書き出し", "", "PDF Files (*.pdf)")
        if not file_path:
            return

        dpi_factor = 72.0 / 150.0
        try:
            export_doc = fitz.open(self.model.pdf_path)
        except Exception as e:
            QMessageBox.critical(self, "エラー", f"元のPDFファイルを開けませんでした: {e}")
            return
        
        for ann in self.model.annotations:
            if ann.page_num >= len(export_doc):
                continue
                
            page = export_doc[ann.page_num]
            from PySide6.QtGui import QColor
            c = QColor(ann.color)
            color = (c.red()/255.0, c.green()/255.0, c.blue()/255.0)
            
            def to_pdf_pt(qp):
                return fitz.Point(qp.x() * dpi_factor, qp.y() * dpi_factor)

            if ann.type == "line":
                p1 = to_pdf_pt(ann.points[0])
                p2 = to_pdf_pt(ann.points[1])
                page.draw_line(p1, p2, color=color, width=1)
                if ann.text:
                    mid = (p1 + p2) / 2
                    page.insert_text(mid, ann.text, color=color, fontsize=ann.font_size, fontname="helv")
            
            elif ann.type == "polygon":
                pts = [to_pdf_pt(p) for p in ann.points]
                page.draw_polyline(pts + [pts[0]], color=color, width=1)
                if ann.text:
                    avg_x = sum(p.x for p in pts) / len(pts)
                    avg_y = sum(p.y for p in pts) / len(pts)
                    page.insert_text((avg_x, avg_y), ann.text, color=color, fontsize=ann.font_size, fontname="helv")
            
            elif ann.type == "circle":
                center = to_pdf_pt(ann.points[0])
                radius = (ann.real_value / self.model.scale_factor) * dpi_factor
                page.draw_circle(center, radius, color=color, width=1)
                if ann.text:
                    page.insert_text((center.x, center.y - radius - 5), ann.text, color=color, fontsize=ann.font_size, fontname="helv")
            
            elif ann.type == "text":
                pos = to_pdf_pt(ann.points[0])
                page.insert_text(pos, ann.text, color=color, fontsize=ann.font_size, fontname="helv")

        export_doc.save(file_path)
        export_doc.close()
        QMessageBox.information(self, "書き出し", f"PDFを書き出しました: {file_path}")

    def update_page_view(self):
        pixmap = self.pdf_handler.get_page_pixmap(self.current_page)
        if pixmap:
            self.canvas.set_page_image(pixmap)
            for ann in self.model.annotations:
                if ann.page_num == self.current_page:
                    if ann.type == "line":
                        self.canvas.add_line_annotation(ann.points[0], ann.points[1], text=ann.text, color=ann.color, item_id=ann.id, font_family=ann.font_family, font_size=ann.font_size)
                    elif ann.type == "polygon":
                        self.canvas.add_polygon_annotation(ann.points, text=ann.text, color=ann.color, item_id=ann.id, font_family=ann.font_family, font_size=ann.font_size)
                    elif ann.type == "circle":
                        radius_px = ann.real_value / self.model.scale_factor
                        self.canvas.add_circle_annotation(ann.points[0], radius_px, text=ann.text, color=ann.color, item_id=ann.id, font_family=ann.font_family, font_size=ann.font_size)
                    elif ann.type == "text":
                        self.canvas.add_text_annotation(ann.points[0], ann.text, color=ann.color, item_id=ann.id, font_family=ann.font_family, font_size=ann.font_size)
            
            total_pages = self.pdf_handler.get_page_count()
            self.page_label.setText(f" ページ: {self.current_page + 1} / {total_pages} ")
            self.prev_btn.setEnabled(self.current_page > 0)
            self.next_btn.setEnabled(self.current_page < total_pages - 1)
            
            # Re-apply interactive flags if in SELECT mode
            self.canvas.set_tool_mode(self.canvas.tool_mode)

    def prev_page(self):
        if self.current_page > 0:
            self.current_page -= 1
            self.update_page_view()

    def next_page(self):
        if self.current_page < self.pdf_handler.get_page_count() - 1:
            self.current_page += 1
            self.update_page_view()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
