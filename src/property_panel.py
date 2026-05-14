from PySide6.QtWidgets import (QWidget, QVBoxLayout, QLabel, QLineEdit, 
                             QPushButton, QColorDialog, QHBoxLayout, QFontComboBox, QSpinBox)
from PySide6.QtCore import Signal
from PySide6.QtGui import QColor, QFont

class PropertyPanel(QWidget):
    attribute_changed = Signal(str, dict) # id, {attr: value}
    delete_requested = Signal(str) # id

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_item_id = None
        self.current_color = "#ff0000"
        self._block_signals = False
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        layout.addWidget(QLabel("<b>オブジェクト属性</b>"))
        
        # ID (ReadOnly)
        self.id_label = QLabel("ID: -")
        layout.addWidget(self.id_label)
        
        # Type
        self.type_label = QLabel("種類: -")
        layout.addWidget(self.type_label)
        
        # Text attribute
        layout.addWidget(QLabel("テキスト / ラベル:"))
        self.text_edit = QLineEdit()
        self.text_edit.editingFinished.connect(self._on_text_changed)
        layout.addWidget(self.text_edit)

        # Font Family
        layout.addWidget(QLabel("フォント:"))
        self.font_combo = QFontComboBox()
        self.font_combo.currentFontChanged.connect(self._on_font_family_changed)
        layout.addWidget(self.font_combo)

        # Font Size
        layout.addWidget(QLabel("サイズ:"))
        self.size_spin = QSpinBox()
        self.size_spin.setRange(1, 200)
        self.size_spin.setValue(12)
        self.size_spin.valueChanged.connect(self._on_font_size_changed)
        layout.addWidget(self.size_spin)
        
        # Color attribute
        layout.addWidget(QLabel("色:"))
        color_layout = QHBoxLayout()
        self.color_preview = QWidget()
        self.color_preview.setFixedSize(20, 20)
        self.color_preview.setStyleSheet("background-color: transparent; border: 1px solid gray;")
        color_layout.addWidget(self.color_preview)
        
        self.color_btn = QPushButton("変更")
        self.color_btn.clicked.connect(self._on_color_clicked)
        color_layout.addWidget(self.color_btn)
        layout.addLayout(color_layout)
        
        layout.addStretch()
        
        # Delete button
        self.delete_btn = QPushButton("削除")
        self.delete_btn.setStyleSheet("background-color: #ffcccc;")
        self.delete_btn.clicked.connect(self._on_delete_clicked)
        layout.addWidget(self.delete_btn)
        
        self.setEnabled(False)

    def set_item_data(self, item_id, item_type, text, color_hex, font_family="Arial", font_size=12):
        self._block_signals = True
        self.current_item_id = item_id
        self.id_label.setText(f"ID: {item_id[:8]}...")
        self.type_label.setText(f"種類: {item_type}")
        self.text_edit.setText(text)
        self.color_preview.setStyleSheet(f"background-color: {color_hex}; border: 1px solid black;")
        self.current_color = color_hex
        
        self.font_combo.setCurrentFont(QFont(font_family))
        self.size_spin.setValue(font_size)
        
        # Font settings are primarily for text type
        is_text = (item_type == "text" or text != "")
        self.font_combo.setVisible(is_text)
        self.size_spin.setVisible(is_text)
        
        self.setEnabled(True)
        self._block_signals = False

    def clear_panel(self):
        self.current_item_id = None
        self.id_label.setText("ID: -")
        self.type_label.setText("種類: -")
        self.text_edit.setText("")
        self.color_preview.setStyleSheet("background-color: transparent; border: 1px solid gray;")
        self.setEnabled(False)

    def _on_text_changed(self):
        if not self._block_signals and self.current_item_id:
            self.attribute_changed.emit(self.current_item_id, {"text": self.text_edit.text()})

    def _on_font_family_changed(self, font):
        if not self._block_signals and self.current_item_id:
            self.attribute_changed.emit(self.current_item_id, {"font_family": font.family()})

    def _on_font_size_changed(self, size):
        if not self._block_signals and self.current_item_id:
            self.attribute_changed.emit(self.current_item_id, {"font_size": size})

    def _on_color_clicked(self):
        if not self.current_item_id: return
        color = QColorDialog.getColor(QColor(self.current_color))
        if color.isValid():
            hex_color = color.name()
            self.color_preview.setStyleSheet(f"background-color: {hex_color}; border: 1px solid black;")
            self.attribute_changed.emit(self.current_item_id, {"color": hex_color})

    def _on_delete_clicked(self):
        if self.current_item_id:
            self.delete_requested.emit(self.current_item_id)
            self.clear_panel()
