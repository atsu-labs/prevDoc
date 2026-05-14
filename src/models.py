import math
import uuid

class DrawingModel:
    def __init__(self):
        self.scale_factor = 1.0  # mm per pixel
        self.is_calibrated = False
        self.annotations = [] # List of annotation objects
        self.pdf_path = ""

    def set_calibration(self, p1, p2, real_distance_mm):
        pixel_dist = math.sqrt((p2.x() - p1.x())**2 + (p2.y() - p1.y())**2)
        if pixel_dist > 0:
            self.scale_factor = real_distance_mm / pixel_dist
            self.is_calibrated = True
            return True
        return False

    def calculate_real_distance(self, p1, p2):
        pixel_dist = math.sqrt((p2.x() - p1.x())**2 + (p2.y() - p1.y())**2)
        return pixel_dist * self.scale_factor

    def calculate_real_area(self, points):
        if len(points) < 3:
            return 0.0
        area = 0.0
        n = len(points)
        for i in range(n):
            j = (i + 1) % n
            area += points[i].x() * points[j].y()
            area -= points[j].x() * points[i].y()
        pixel_area = abs(area) / 2.0
        return pixel_area * (self.scale_factor ** 2)

    def to_dict(self):
        return {
            "scale_factor": self.scale_factor,
            "is_calibrated": self.is_calibrated,
            "pdf_path": self.pdf_path,
            "annotations": [a.to_dict() for a in self.annotations]
        }

    @classmethod
    def from_dict(cls, data):
        model = cls()
        model.scale_factor = data.get("scale_factor", 1.0)
        model.is_calibrated = data.get("is_calibrated", False)
        model.pdf_path = data.get("pdf_path", "")
        for a_data in data.get("annotations", []):
            model.annotations.append(Annotation.from_dict(a_data))
        return model

class Annotation:
    def __init__(self, type):
        self.id = str(uuid.uuid4())
        self.type = type # 'line', 'polygon', 'circle', 'text'
        self.points = [] # List of QPointF or (x,y) tuples? internally let's use QPointF
        self.color = "red"
        self.text = ""
        self.font_family = "Arial"
        self.font_size = 12
        self.real_value = 0.0
        self.page_num = 0

    def to_dict(self):
        from PySide6.QtCore import QPointF
        pts = []
        for p in self.points:
            if isinstance(p, QPointF):
                pts.append((p.x(), p.y()))
            else:
                pts.append(p)
        return {
            "id": self.id,
            "type": self.type,
            "points": pts,
            "color": self.color,
            "text": self.text,
            "font_family": self.font_family,
            "font_size": self.font_size,
            "real_value": self.real_value,
            "page_num": self.page_num
        }

    @classmethod
    def from_dict(cls, data):
        from PySide6.QtCore import QPointF
        ann = cls(data["type"])
        ann.id = data.get("id", str(uuid.uuid4()))
        ann.points = [QPointF(p[0], p[1]) for p in data.get("points", [])]
        ann.color = data.get("color", "red")
        ann.text = data.get("text", "")
        ann.font_family = data.get("font_family", "Arial")
        ann.font_size = data.get("font_size", 12)
        ann.real_value = data.get("real_value", 0.0)
        ann.page_num = data.get("page_num", 0)
        return ann
