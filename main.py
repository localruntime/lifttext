import sys
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                               QHBoxLayout, QPushButton, QLabel, QTextEdit,
                               QFileDialog, QScrollArea, QListWidget, QListWidgetItem, QProgressBar, QComboBox)
from PySide6.QtCore import Qt, QThread, Signal, QRect, QPoint, QSettings
from PySide6.QtGui import QPixmap, QPainter, QPen, QColor, QFont
from paddleocr import PaddleOCR
import os


class ImageWithBoxes(QLabel):
    """Custom widget that displays an image with clickable word boxes"""
    word_clicked = Signal(dict)  # Emits word data when a box is clicked
    zoom_changed = Signal(float)  # Emits current zoom level
    selection_changed = Signal(bool)  # Emits when selection becomes active/inactive

    def __init__(self):
        super().__init__()
        self.original_pixmap = None
        self.scaled_pixmap = None
        self.word_data = []
        self.selected_word_index = None
        self.scale_factor = 1.0
        self.offset_x = 0
        self.offset_y = 0
        self.setMouseTracking(True)
        self.hovered_word_index = None
        self.zoom_level = 1.0  # 1.0 = 100%, 2.0 = 200%, etc.
        self.min_zoom = 0.1
        self.max_zoom = 10.0

        # Panning support
        self.pan_offset_x = 0
        self.pan_offset_y = 0
        self.is_panning = False
        self.pan_start_pos = None
        self.pan_start_offset_x = 0
        self.pan_start_offset_y = 0

        # Selection mode state
        self.selection_mode = False  # Whether selection mode is active
        self.selection_rect_original = None  # (x, y, w, h) in ORIGINAL image coords (not display coords)
        self.selection_handles = []  # List of handle rects in display coords (recalculated on paint)

        # Interaction state
        self.drawing_selection = False  # Currently drawing new selection
        self.dragging_handle = None  # Which handle is being dragged (0-7 or None)
        self.moving_selection = False  # Currently moving entire selection
        self.drag_start_pos = None  # QPoint where drag started (display coords)
        self.drag_start_rect = None  # Original rect when drag started (original coords)

        # Minimum selection size (prevent too-small selections)
        self.MIN_SELECTION_SIZE = 20  # pixels in original image space

    def set_image(self, pixmap):
        """Set the image to display"""
        self.original_pixmap = pixmap
        self.word_data = []
        self.selected_word_index = None
        self.hovered_word_index = None
        self.zoom_level = 1.0  # Reset zoom when loading new image
        self.pan_offset_x = 0  # Reset pan when loading new image
        self.pan_offset_y = 0
        # Debug: Print original image dimensions
        print(f"QPixmap dimensions: {pixmap.width()} x {pixmap.height()}")
        self.update_display()

    def set_word_data(self, words):
        """Set word bounding box data"""
        self.word_data = words
        self.update()

    def update_display(self):
        """Update the scaled pixmap and display"""
        if self.original_pixmap:
            # Scale image to fit while maintaining aspect ratio, then apply zoom
            base_scaled = self.original_pixmap.scaled(
                self.size(),
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            )

            # Apply zoom level
            zoomed_width = int(base_scaled.width() * self.zoom_level)
            zoomed_height = int(base_scaled.height() * self.zoom_level)

            self.scaled_pixmap = self.original_pixmap.scaled(
                zoomed_width,
                zoomed_height,
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            )

            # Calculate scale factor and offset for centering
            self.scale_factor = self.scaled_pixmap.width() / self.original_pixmap.width()
            self.offset_x = (self.width() - self.scaled_pixmap.width()) // 2
            self.offset_y = (self.height() - self.scaled_pixmap.height()) // 2

            self.zoom_changed.emit(self.zoom_level)
            self.update()

    def resizeEvent(self, event):
        """Handle resize events"""
        super().resizeEvent(event)
        self.update_display()

    def paintEvent(self, event):
        """Custom paint to draw image and word boxes"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # Draw the scaled image centered with pan offset
        if self.scaled_pixmap:
            draw_x = self.offset_x + self.pan_offset_x
            draw_y = self.offset_y + self.pan_offset_y
            painter.drawPixmap(draw_x, draw_y, self.scaled_pixmap)

            # Debug: Print paint info
            print(f"Painting {len(self.word_data)} word boxes, scale: {self.scale_factor}, offset: ({draw_x}, {draw_y})")

            # Draw word boxes
            boxes_drawn = 0
            for idx, word_info in enumerate(self.word_data):
                if 'bbox' in word_info and word_info['bbox']:
                    bbox = word_info['bbox']
                    print(f"Drawing box {idx}: {bbox}")

                    # Convert bbox coordinates to scaled display coordinates with pan offset
                    scaled_points = []
                    for point in bbox:
                        x = int(point[0] * self.scale_factor + self.offset_x + self.pan_offset_x)
                        y = int(point[1] * self.scale_factor + self.offset_y + self.pan_offset_y)
                        scaled_points.append(QPoint(x, y))

                    print(f"Scaled points: {[(p.x(), p.y()) for p in scaled_points]}")

                    # Determine box color based on state
                    if idx == self.selected_word_index:
                        pen_color = QColor(25, 118, 210)  # Blue for selected
                        fill_color = QColor(187, 222, 251, 100)  # Light blue fill
                        pen_width = 3
                    elif idx == self.hovered_word_index:
                        pen_color = QColor(33, 150, 243)  # Lighter blue for hover
                        fill_color = QColor(227, 242, 253, 80)  # Very light blue fill
                        pen_width = 2
                    else:
                        pen_color = QColor(76, 175, 80)  # Green for normal
                        fill_color = QColor(76, 175, 80, 50)  # Light green fill
                        pen_width = 2

                    # Draw filled polygon
                    painter.setPen(Qt.NoPen)
                    painter.setBrush(fill_color)
                    painter.drawPolygon(scaled_points)

                    # Draw border
                    pen = QPen(pen_color, pen_width)
                    painter.setPen(pen)
                    painter.setBrush(Qt.NoBrush)
                    painter.drawPolygon(scaled_points)
                    boxes_drawn += 1
                else:
                    print(f"Word {idx} has no bbox: {word_info}")

            print(f"Drew {boxes_drawn} boxes")

        # Draw selection rectangle and overlay (if selection exists)
        if self.selection_rect_original:
            display_rect = self.get_selection_display_rect()

            if display_rect:
                # 1. Draw semi-transparent overlay on non-selected area
                overlay_color = QColor(0, 0, 0, 120)  # Dark overlay

                painter.setPen(Qt.NoPen)
                painter.setBrush(overlay_color)

                # Draw overlay in 4 rectangles around selection
                # Top
                painter.drawRect(QRect(0, 0, self.width(), display_rect.top()))
                # Bottom
                painter.drawRect(QRect(0, display_rect.bottom(), self.width(), self.height() - display_rect.bottom()))
                # Left
                painter.drawRect(QRect(0, display_rect.top(), display_rect.left(), display_rect.height()))
                # Right
                painter.drawRect(QRect(display_rect.right(), display_rect.top(), self.width() - display_rect.right(), display_rect.height()))

                # 2. Draw selection rectangle border
                # Check if selection is too small (invalid)
                is_valid = self.validate_selection()

                if is_valid:
                    border_color = QColor(255, 165, 0)  # Orange for valid selection
                    border_style = Qt.SolidLine
                else:
                    border_color = QColor(255, 0, 0)  # Red for invalid selection
                    border_style = Qt.DashLine

                pen = QPen(border_color, 3, border_style)
                painter.setPen(pen)
                painter.setBrush(Qt.NoBrush)
                painter.drawRect(display_rect)

                # 3. Draw resize handles (8 handles: corners + midpoints)
                self.update_selection_handles()  # Recalculate handle positions

                painter.setPen(Qt.NoPen)
                painter.setBrush(QColor(255, 165, 0))  # Orange handles

                for handle_rect in self.selection_handles:
                    painter.drawRect(handle_rect)

                # 4. Draw size label inside selection (if large enough)
                if display_rect.width() > 60 and display_rect.height() > 30:
                    x, y, w, h = self.selection_rect_original
                    size_text = f"{w} x {h}"

                    painter.setPen(QColor(255, 255, 255))
                    painter.setFont(QFont("Arial", 12, QFont.Bold))
                    text_rect = QRect(display_rect.left() + 5, display_rect.top() + 5,
                                    display_rect.width() - 10, 25)

                    # Draw semi-transparent background for text
                    painter.fillRect(text_rect, QColor(0, 0, 0, 150))
                    painter.drawText(text_rect, Qt.AlignCenter, size_text)

                # 5. Draw "too small" warning if invalid
                if not is_valid:
                    warning_text = f"Min: {self.MIN_SELECTION_SIZE}px"
                    painter.setPen(QColor(255, 0, 0))
                    painter.setFont(QFont("Arial", 14, QFont.Bold))
                    text_rect = display_rect.adjusted(0, 0, 0, 30)
                    painter.drawText(text_rect, Qt.AlignCenter, warning_text)

    def mousePressEvent(self, event):
        """Handle mouse clicks for panning, selection, and word box clicking"""
        # PRIORITY 1: Pan always works (middle/right button)
        if event.button() in (Qt.MiddleButton, Qt.RightButton):
            # Start panning with middle or right mouse button
            self.is_panning = True
            self.pan_start_pos = event.pos()
            self.pan_start_offset_x = self.pan_offset_x
            self.pan_start_offset_y = self.pan_offset_y
            self.setCursor(Qt.ClosedHandCursor)
            event.accept()
            return

        # PRIORITY 2: Selection mode (left button)
        if self.selection_mode and event.button() == Qt.LeftButton:
            click_pos = event.pos()

            # Check if clicking resize handle (in display coords)
            handle_idx = self.find_handle_at_pos(click_pos)
            if handle_idx is not None:
                self.dragging_handle = handle_idx
                self.drag_start_pos = click_pos
                self.drag_start_rect = self.selection_rect_original
                return

            # Check if clicking inside selection (move)
            if self.point_in_selection(click_pos):
                self.moving_selection = True
                self.drag_start_pos = click_pos
                self.drag_start_rect = self.selection_rect_original
                return

            # Otherwise, start new selection
            self.drawing_selection = True
            self.drag_start_pos = click_pos
            self.selection_rect_original = None
            return

        # PRIORITY 3: Word box clicking (only if NOT in selection mode)
        if event.button() == Qt.LeftButton:
            click_pos = event.pos()

            # Check which word box was clicked (in reverse order for top-most)
            for idx in range(len(self.word_data) - 1, -1, -1):
                word_info = self.word_data[idx]
                if 'bbox' in word_info and word_info['bbox']:
                    bbox = word_info['bbox']

                    # Convert bbox to scaled coordinates with pan offset
                    scaled_points = []
                    for point in bbox:
                        x = int(point[0] * self.scale_factor + self.offset_x + self.pan_offset_x)
                        y = int(point[1] * self.scale_factor + self.offset_y + self.pan_offset_y)
                        scaled_points.append(QPoint(x, y))

                    # Check if click is inside polygon
                    if self.point_in_polygon(click_pos, scaled_points):
                        self.selected_word_index = idx
                        self.word_clicked.emit(word_info)
                        self.update()
                        break

    def mouseReleaseEvent(self, event):
        """Handle mouse release to end panning and finalize selection"""
        # Handle pan release
        if event.button() in (Qt.MiddleButton, Qt.RightButton):
            if self.is_panning:
                self.is_panning = False
                self.setCursor(Qt.ArrowCursor)
                event.accept()
                return

        # Handle selection finalization
        if event.button() == Qt.LeftButton:
            if self.drawing_selection or self.moving_selection or self.dragging_handle:
                # Clamp and validate selection
                self.clamp_selection_to_image()

                # Emit signal only once on release (emit True if selection exists)
                has_selection = self.selection_rect_original is not None
                self.selection_changed.emit(has_selection)

                # Reset interaction state
                self.drawing_selection = False
                self.moving_selection = False
                self.dragging_handle = None
                self.drag_start_pos = None
                self.drag_start_rect = None

                self.update_cursor()
                self.update()
                return

    def mouseMoveEvent(self, event):
        """Handle mouse move for panning, selection, and word box hover"""
        # Handle panning first
        if self.is_panning:
            # Update pan offset based on mouse movement
            current_pos = event.pos()
            delta_x = current_pos.x() - self.pan_start_pos.x()
            delta_y = current_pos.y() - self.pan_start_pos.y()

            self.pan_offset_x = self.pan_start_offset_x + delta_x
            self.pan_offset_y = self.pan_start_offset_y + delta_y

            self.update()
            event.accept()
            return

        # Handle selection operations
        if self.dragging_handle is not None:
            # Resize selection with constraints
            self.resize_selection_with_handle(event.pos())
            self.update_cursor()  # Change cursor based on handle
            self.update()
            return

        if self.moving_selection:
            # Move entire selection
            self.move_selection(event.pos())
            self.setCursor(Qt.SizeAllCursor)
            self.update()
            return

        if self.drawing_selection:
            # Expand selection from drag start
            self.update_selection_from_drag(event.pos())
            self.update()
            return

        # Handle hover feedback in selection mode
        if self.selection_mode:
            # Update cursor based on position (handle/inside/outside)
            self.update_cursor()
            return

        # Fall back to existing word box hover logic
        # Handle word box hover
        hover_pos = event.pos()
        found_hover = False

        # Check which word box is hovered (in reverse order for top-most)
        for idx in range(len(self.word_data) - 1, -1, -1):
            word_info = self.word_data[idx]
            if 'bbox' in word_info and word_info['bbox']:
                bbox = word_info['bbox']

                # Convert bbox to scaled coordinates with pan offset
                scaled_points = []
                for point in bbox:
                    x = int(point[0] * self.scale_factor + self.offset_x + self.pan_offset_x)
                    y = int(point[1] * self.scale_factor + self.offset_y + self.pan_offset_y)
                    scaled_points.append(QPoint(x, y))

                # Check if hover is inside polygon
                if self.point_in_polygon(hover_pos, scaled_points):
                    if self.hovered_word_index != idx:
                        self.hovered_word_index = idx
                        self.setCursor(Qt.PointingHandCursor)
                        self.update()
                    found_hover = True
                    break

        if not found_hover and self.hovered_word_index is not None:
            self.hovered_word_index = None
            self.setCursor(Qt.ArrowCursor)
            self.update()

    def point_in_polygon(self, point, polygon):
        """Check if a point is inside a polygon using ray casting algorithm"""
        x, y = point.x(), point.y()
        n = len(polygon)
        inside = False

        p1 = polygon[0]
        for i in range(1, n + 1):
            p2 = polygon[i % n]
            if y > min(p1.y(), p2.y()):
                if y <= max(p1.y(), p2.y()):
                    if x <= max(p1.x(), p2.x()):
                        if p1.y() != p2.y():
                            xinters = (y - p1.y()) * (p2.x() - p1.x()) / (p2.y() - p1.y()) + p1.x()
                        if p1.x() == p2.x() or x <= xinters:
                            inside = not inside
            p1 = p2

        return inside


    def zoom_in(self):
        """Zoom in by 20%"""
        if self.original_pixmap:
            new_zoom = min(self.max_zoom, self.zoom_level * 1.2)
            if new_zoom != self.zoom_level:
                self.zoom_level = new_zoom
                self.update_display()

    def zoom_out(self):
        """Zoom out by 20%"""
        if self.original_pixmap:
            new_zoom = max(self.min_zoom, self.zoom_level / 1.2)
            if new_zoom != self.zoom_level:
                self.zoom_level = new_zoom
                self.update_display()

    def zoom_reset(self):
        """Reset zoom to 100% and clear pan offset"""
        if self.original_pixmap:
            self.zoom_level = 1.0
            self.pan_offset_x = 0
            self.pan_offset_y = 0
            self.update_display()

    # Coordinate conversion methods for selection tool
    def display_to_original_coords(self, display_x, display_y):
        """Convert display coordinates to original image coordinates"""
        if not self.original_pixmap:
            return (0, 0)

        orig_x = (display_x - self.offset_x - self.pan_offset_x) / self.scale_factor
        orig_y = (display_y - self.offset_y - self.pan_offset_y) / self.scale_factor
        return (int(orig_x), int(orig_y))

    def original_to_display_coords(self, orig_x, orig_y):
        """Convert original image coordinates to display coordinates"""
        display_x = int(orig_x * self.scale_factor + self.offset_x + self.pan_offset_x)
        display_y = int(orig_y * self.scale_factor + self.offset_y + self.pan_offset_y)
        return (display_x, display_y)

    def get_selection_display_rect(self):
        """Get selection rectangle in display coordinates (recalculated from original coords)"""
        if not self.selection_rect_original:
            return None

        x, y, w, h = self.selection_rect_original
        dx, dy = self.original_to_display_coords(x, y)
        dw = int(w * self.scale_factor)
        dh = int(h * self.scale_factor)
        return QRect(dx, dy, dw, dh)

    # Selection management methods
    def set_selection_mode(self, enabled):
        """Enable/disable selection mode"""
        self.selection_mode = enabled
        if not enabled:
            self.clear_selection()
            # IMPORTANT: Stop any in-progress dragging
            self.drawing_selection = False
            self.moving_selection = False
            self.dragging_handle = None
        self.update_cursor()
        self.update()

    def clear_selection(self):
        """Clear current selection"""
        self.selection_rect_original = None
        self.selection_handles = []
        self.update()

    # Selection validation methods
    def clamp_selection_to_image(self):
        """Ensure selection rect stays within original image bounds"""
        if not self.selection_rect_original or not self.original_pixmap:
            return

        x, y, w, h = self.selection_rect_original
        img_w = self.original_pixmap.width()
        img_h = self.original_pixmap.height()

        # Clamp position and size
        x = max(0, min(x, img_w - 1))
        y = max(0, min(y, img_h - 1))
        w = min(w, img_w - x)
        h = min(h, img_h - y)

        self.selection_rect_original = (x, y, max(1, w), max(1, h))

    def validate_selection(self):
        """Check if selection meets minimum size requirements"""
        if not self.selection_rect_original:
            return False

        x, y, w, h = self.selection_rect_original
        return w >= self.MIN_SELECTION_SIZE and h >= self.MIN_SELECTION_SIZE

    # Handle management methods
    def update_selection_handles(self):
        """Update resize handle positions (8 handles: corners + midpoints)"""
        self.selection_handles = []

        if not self.selection_rect_original:
            return

        rect = self.get_selection_display_rect()
        if not rect:
            return

        handle_size = 10
        half = handle_size // 2

        # 8 handles: TL, T, TR, R, BR, B, BL, L
        positions = [
            (rect.left(), rect.top()),           # 0: Top-left
            (rect.center().x(), rect.top()),     # 1: Top
            (rect.right(), rect.top()),          # 2: Top-right
            (rect.right(), rect.center().y()),   # 3: Right
            (rect.right(), rect.bottom()),       # 4: Bottom-right
            (rect.center().x(), rect.bottom()),  # 5: Bottom
            (rect.left(), rect.bottom()),        # 6: Bottom-left
            (rect.left(), rect.center().y()),    # 7: Left
        ]

        for x, y in positions:
            self.selection_handles.append(QRect(x - half, y - half, handle_size, handle_size))

    def find_handle_at_pos(self, pos):
        """Find which handle (if any) is at the given position. Returns handle index (0-7) or None"""
        for idx, handle_rect in enumerate(self.selection_handles):
            if handle_rect.contains(pos):
                return idx
        return None

    def point_in_selection(self, pos):
        """Check if a display coordinate point is inside the selection rectangle"""
        rect = self.get_selection_display_rect()
        return rect.contains(pos) if rect else False

    # Interaction helper methods
    def update_selection_from_drag(self, current_pos):
        """Update selection rectangle while drawing (from drag_start_pos to current_pos)"""
        if not self.drag_start_pos or not self.original_pixmap:
            return

        # Convert both points to original coords
        start_orig = self.display_to_original_coords(self.drag_start_pos.x(), self.drag_start_pos.y())
        end_orig = self.display_to_original_coords(current_pos.x(), current_pos.y())

        # Create rectangle (handle negative dimensions)
        x1, y1 = start_orig
        x2, y2 = end_orig

        x = min(x1, x2)
        y = min(y1, y2)
        w = abs(x2 - x1)
        h = abs(y2 - y1)

        self.selection_rect_original = (x, y, w, h)
        self.update_selection_handles()

    def move_selection(self, current_pos):
        """Move the entire selection rectangle"""
        if not self.drag_start_pos or not self.drag_start_rect:
            return

        # Calculate delta in display coords, then convert to original coords
        delta_x = current_pos.x() - self.drag_start_pos.x()
        delta_y = current_pos.y() - self.drag_start_pos.y()

        # Convert delta to original image space
        delta_orig_x = delta_x / self.scale_factor
        delta_orig_y = delta_y / self.scale_factor

        x, y, w, h = self.drag_start_rect
        self.selection_rect_original = (int(x + delta_orig_x), int(y + delta_orig_y), w, h)
        self.update_selection_handles()

    def resize_selection_with_handle(self, current_pos):
        """Resize selection by dragging a handle"""
        if self.dragging_handle is None or not self.drag_start_rect:
            return

        # Convert current position to original coords
        curr_orig = self.display_to_original_coords(current_pos.x(), current_pos.y())
        x, y, w, h = self.drag_start_rect

        # Adjust rectangle based on which handle is being dragged
        # Handles: 0=TL, 1=T, 2=TR, 3=R, 4=BR, 5=B, 6=BL, 7=L
        if self.dragging_handle in [0, 6, 7]:  # Left side
            new_x = curr_orig[0]
            new_w = (x + w) - new_x
            x, w = new_x, new_w
        elif self.dragging_handle in [2, 3, 4]:  # Right side
            w = curr_orig[0] - x

        if self.dragging_handle in [0, 1, 2]:  # Top side
            new_y = curr_orig[1]
            new_h = (y + h) - new_y
            y, h = new_y, new_h
        elif self.dragging_handle in [4, 5, 6]:  # Bottom side
            h = curr_orig[1] - y

        # Normalize (handle negative dimensions)
        if w < 0:
            x, w = x + w, abs(w)
        if h < 0:
            y, h = y + h, abs(h)

        self.selection_rect_original = (int(x), int(y), int(w), int(h))
        self.update_selection_handles()

    def update_cursor(self):
        """Update cursor based on current state and mouse position"""
        if self.is_panning:
            self.setCursor(Qt.ClosedHandCursor)
        elif self.dragging_handle is not None:
            # Use appropriate resize cursor based on handle
            cursors = [
                Qt.SizeFDiagCursor,  # 0: TL
                Qt.SizeVerCursor,    # 1: T
                Qt.SizeBDiagCursor,  # 2: TR
                Qt.SizeHorCursor,    # 3: R
                Qt.SizeFDiagCursor,  # 4: BR
                Qt.SizeVerCursor,    # 5: B
                Qt.SizeBDiagCursor,  # 6: BL
                Qt.SizeHorCursor,    # 7: L
            ]
            self.setCursor(cursors[self.dragging_handle])
        elif self.moving_selection:
            self.setCursor(Qt.SizeAllCursor)
        elif self.selection_mode:
            self.setCursor(Qt.CrossCursor)
        elif self.hovered_word_index is not None:
            self.setCursor(Qt.PointingHandCursor)
        else:
            self.setCursor(Qt.ArrowCursor)


class OCRWorker(QThread):
    """Worker thread for OCR processing to keep UI responsive"""
    finished = Signal(str)
    words_detected = Signal(list)  # Emits list of word dictionaries
    error = Signal(str)
    progress = Signal(str)
    progress_value = Signal(int)  # Emits progress percentage (0-100)
    preprocessed_image = Signal(str)  # ADD THIS: Signal to send preprocessed image path

    def __init__(self, image_path, det_model='PP-OCRv4_mobile_det', rec_model='en_PP-OCRv4_mobile_rec', crop_rect=None):
        super().__init__()
        self.image_path = image_path
        self.det_model = det_model
        self.rec_model = rec_model
        self.crop_rect = crop_rect  # (x, y, width, height) in original image coords
        self.ocr = None

    def run(self):
        try:
            # Initialize PaddleOCR v3 with mobile/slim models for fast performance
            self.progress_value.emit(10)
            self.progress.emit("Initializing PaddleOCR v3 (this may take a while on first run)...")
            self.ocr = PaddleOCR(
                # Use mobile/slim models for faster performance
                text_detection_model_name=self.det_model,      # Configurable detection model
                text_recognition_model_name=self.rec_model,    # Configurable recognition model

                # Disable heavy preprocessing for speed
                use_doc_orientation_classify=False,  # Disable document orientation classification
                use_doc_unwarping=False,             # Disable document unwarping
                use_textline_orientation=False,      # Disable text orientation detection
                lang='en',

                # Detection optimizations (v3 uses text_det_* prefix)
                text_det_limit_side_len=960,     # Lower for faster processing (480-960 range)
                text_det_thresh=0.3,             # Detection threshold
                text_det_box_thresh=0.5,         # Box threshold

                # Recognition optimizations (v3 uses text_recognition_* prefix)
                text_recognition_batch_size=6    # Batch size (adjust based on available memory)
            )

            # Load and crop image using PIL (matching existing pattern)
            from PIL import Image
            import tempfile

            self.progress.emit("Loading image...")
            pil_image = Image.open(self.image_path)

            # Convert to RGB if needed
            if pil_image.mode != 'RGB':
                pil_image = pil_image.convert('RGB')

            # Crop if crop_rect provided
            crop_offset_x = 0
            crop_offset_y = 0
            if self.crop_rect:
                x, y, w, h = self.crop_rect
                crop_offset_x = x
                crop_offset_y = y
                self.progress.emit(f"Cropping to region: ({x}, {y}, {w}, {h})...")
                pil_image = pil_image.crop((x, y, x + w, y + h))

            # Save to temp file (PaddleOCR expects file path, not array)
            temp_path = tempfile.mktemp(suffix='.png')
            pil_image.save(temp_path)

            # Perform OCR on temp file (v3 uses predict method)
            self.progress_value.emit(50)
            self.progress.emit("Running OCR on image...")
            result = self.ocr.predict(temp_path)

            # Debug: Print result structure
            print(f"OCR Result type: {type(result)}")

            # Extract text from results
            self.progress_value.emit(80)
            self.progress.emit("Extracting text from results...")
            text_lines = []
            word_data = []

            # PaddleOCR can return different formats
            if result and isinstance(result, list) and len(result) > 0:
                page_result = result[0]

                if page_result is None:
                    print("No text detected - page_result is None")

                # Handle dictionary format (newer PaddleOCR)
                elif isinstance(page_result, dict):
                    print(f"Dictionary format detected")
                    
                    # EXTRACT AND SAVE THE PREPROCESSED IMAGE
                    if 'doc_preprocessor_res' in page_result:
                        preprocessed_img = page_result['doc_preprocessor_res'].get('output_img')
                        
                        if preprocessed_img is not None:
                            import tempfile
                            from PIL import Image
                            
                            # Save preprocessed image to temp file
                            temp_path = tempfile.mktemp(suffix='.png')
                            Image.fromarray(preprocessed_img).save(temp_path)
                            print(f"Saved preprocessed image to: {temp_path}")
                            
                            # Emit signal with preprocessed image path
                            self.preprocessed_image.emit(temp_path)

                    # Extract data from dictionary (try both singular and plural keys)
                    bboxes = page_result.get('dt_polys', [])
                    texts = page_result.get('rec_texts', page_result.get('rec_text', []))
                    scores = page_result.get('rec_scores', page_result.get('rec_score', []))

                    print(f"Found {len(texts)} texts, {len(bboxes)} bboxes, {len(scores)} scores")

                    # Combine the data
                    for idx in range(len(texts)):
                        text_content = str(texts[idx])
                        text_lines.append(text_content)

                        word_entry = {
                            'text': text_content,
                            'index': idx
                        }

                        # Add confidence if available
                        if idx < len(scores):
                            confidence = scores[idx]
                            word_entry['confidence'] = f"{confidence:.2%}" if isinstance(confidence, (int, float)) else str(confidence)
                        else:
                            word_entry['confidence'] = 'N/A'

                        # Add bounding box if available
                        if idx < len(bboxes):
                            bbox = bboxes[idx]
                            # Convert numpy array or other formats to list
                            if hasattr(bbox, 'tolist'):
                                bbox = bbox.tolist()

                            # Offset bbox back to full image coordinates if cropped
                            if self.crop_rect:
                                adjusted_bbox = [[pt[0] + crop_offset_x, pt[1] + crop_offset_y] for pt in bbox]
                                word_entry['bbox'] = adjusted_bbox
                                print(f"Word {idx}: '{text_content}' with bbox (offset): {adjusted_bbox}")
                            else:
                                word_entry['bbox'] = bbox
                                print(f"Word {idx}: '{text_content}' with bbox: {bbox}")
                        else:
                            print(f"Word {idx}: '{text_content}' - NO BBOX")

                        word_data.append(word_entry)

                # Handle list format (older PaddleOCR): [[bbox, (text, confidence)], ...]
                elif isinstance(page_result, list):
                    print(f"List format detected - Processing {len(page_result)} detected text regions")

                    for idx, detection in enumerate(page_result):
                        if detection and len(detection) >= 2:
                            bbox = detection[0]  # Bounding box coordinates
                            text_info = detection[1]  # (text, confidence) tuple

                            # Extract text and confidence
                            if isinstance(text_info, (list, tuple)) and len(text_info) >= 1:
                                text_content = str(text_info[0])
                                confidence = text_info[1] if len(text_info) > 1 else None
                            else:
                                text_content = str(text_info)
                                confidence = None

                            text_lines.append(text_content)

                            # Create word data with bounding box
                            word_entry = {
                                'text': text_content,
                                'confidence': f"{confidence:.2%}" if isinstance(confidence, float) else 'N/A',
                                'index': idx
                            }

                            # Add bounding box if available
                            if bbox:
                                if hasattr(bbox, 'tolist'):
                                    bbox = bbox.tolist()

                                # Offset bbox back to full image coordinates if cropped
                                if self.crop_rect:
                                    adjusted_bbox = [[pt[0] + crop_offset_x, pt[1] + crop_offset_y] for pt in bbox]
                                    word_entry['bbox'] = adjusted_bbox
                                    print(f"Word {idx}: '{text_content}' with bbox (offset): {adjusted_bbox}")
                                else:
                                    word_entry['bbox'] = bbox
                                    print(f"Word {idx}: '{text_content}' with bbox: {bbox}")
                            else:
                                print(f"Word {idx}: '{text_content}' - NO BBOX")

                            word_data.append(word_entry)
                else:
                    print(f"Unexpected page_result type: {type(page_result)}")

            extracted_text = '\n'.join(text_lines) if text_lines else "No text detected in image"
            print(f"Total words extracted: {len(word_data)}")
            self.words_detected.emit(word_data)
            self.progress_value.emit(100)
            self.finished.emit(extracted_text)

        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            print(f"OCR Error: {error_details}")
            self.error.emit(f"Error during OCR: {str(e)}\n\nDetails:\n{error_details}")


class OCRApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.image_path = None
        self.ocr_worker = None
        self.word_data = []  # Store detected words data

        # Selection tracking
        self.current_crop_rect = None  # Track active crop for coordinate adjustment
        self.is_processing_selection = False  # Prevent conflicts during selection OCR

        # Initialize QSettings for persistence
        self.settings = QSettings('PaddleOCR', 'ImageTextExtractor')

        # Settings keys
        self.SETTINGS_DET_MODEL = 'ocr/detection_model'
        self.SETTINGS_REC_MODEL = 'ocr/recognition_model'
        self.DEFAULT_DET_MODEL = 'PP-OCRv4_mobile_det'
        self.DEFAULT_REC_MODEL = 'en_PP-OCRv4_mobile_rec'

        self.init_ui()

    def init_ui(self):
        self.setWindowTitle("PaddleOCR Image Text Extractor")
        self.setGeometry(100, 100, 1000, 700)

        # Available models for dropdown menus
        self.detection_models = [
            'PP-OCRv4_mobile_det',
            'PP-OCRv4_server_det',
            'PP-OCRv5_mobile_det',
            'PP-OCRv5_server_det',
        ]

        self.recognition_models = [
            'en_PP-OCRv4_mobile_rec',      # English (fast)
            'en_PP-OCRv5_mobile_rec',      # English (latest)
            'PP-OCRv4_mobile_rec',         # Chinese (fast)
            'PP-OCRv4_server_rec',         # Chinese (high accuracy)
            'PP-OCRv5_mobile_rec',         # Multi-language (latest, supports CN/EN/JP)
            'PP-OCRv5_server_rec',         # Multi-language (best accuracy)
        ]

        # Load saved model selections with validation
        saved_det_model = self.settings.value(
            self.SETTINGS_DET_MODEL,
            self.DEFAULT_DET_MODEL
        )
        saved_rec_model = self.settings.value(
            self.SETTINGS_REC_MODEL,
            self.DEFAULT_REC_MODEL
        )

        # Validate saved models exist in current model lists
        self.selected_det_model = saved_det_model if saved_det_model in self.detection_models else self.DEFAULT_DET_MODEL
        self.selected_rec_model = saved_rec_model if saved_rec_model in self.recognition_models else self.DEFAULT_REC_MODEL

        # Central widget and main layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        # Button layout
        button_layout = QHBoxLayout()

        # Upload button
        upload_btn = QPushButton("Upload Image")
        upload_btn.clicked.connect(self.upload_image)
        upload_btn.setStyleSheet("font-size: 14px; padding: 10px;")
        button_layout.addWidget(upload_btn)

        # Process image button (disabled until image is loaded)
        self.process_btn = QPushButton("Process Image")
        self.process_btn.clicked.connect(self.process_image)
        self.process_btn.setStyleSheet("font-size: 14px; padding: 10px;")
        self.process_btn.setEnabled(False)
        button_layout.addWidget(self.process_btn)

        # Selection mode toggle button
        self.select_area_btn = QPushButton("Select Area")
        self.select_area_btn.setCheckable(True)
        self.select_area_btn.clicked.connect(self.toggle_selection_mode)
        self.select_area_btn.setStyleSheet("font-size: 14px; padding: 10px;")
        self.select_area_btn.setEnabled(False)  # Disabled until image is loaded
        button_layout.addWidget(self.select_area_btn)

        # Process selection button
        self.process_selection_btn = QPushButton("Process Selection")
        self.process_selection_btn.clicked.connect(self.process_selection)
        self.process_selection_btn.setStyleSheet("font-size: 14px; padding: 10px;")
        self.process_selection_btn.setEnabled(False)  # Enabled when selection exists
        button_layout.addWidget(self.process_selection_btn)

        # Clear selection button
        self.clear_selection_btn = QPushButton("Clear Selection")
        self.clear_selection_btn.clicked.connect(self.clear_selection)
        self.clear_selection_btn.setStyleSheet("font-size: 14px; padding: 10px;")
        self.clear_selection_btn.setEnabled(False)
        button_layout.addWidget(self.clear_selection_btn)

        # Detection model selection
        det_label = QLabel("Detection:")
        det_label.setStyleSheet("font-size: 12px; padding-left: 10px;")
        button_layout.addWidget(det_label)

        self.det_model_combo = QComboBox()
        self.det_model_combo.addItems(self.detection_models)
        self.det_model_combo.setCurrentText(self.selected_det_model)
        self.det_model_combo.currentTextChanged.connect(self.on_detection_model_changed)
        self.det_model_combo.setMaximumWidth(180)
        self.det_model_combo.setStyleSheet("font-size: 12px; padding: 5px;")
        button_layout.addWidget(self.det_model_combo)

        # Recognition model selection
        rec_label = QLabel("Recognition:")
        rec_label.setStyleSheet("font-size: 12px; padding-left: 10px;")
        button_layout.addWidget(rec_label)

        self.rec_model_combo = QComboBox()
        self.rec_model_combo.addItems(self.recognition_models)
        self.rec_model_combo.setCurrentText(self.selected_rec_model)
        self.rec_model_combo.currentTextChanged.connect(self.on_recognition_model_changed)
        self.rec_model_combo.setMaximumWidth(180)
        self.rec_model_combo.setStyleSheet("font-size: 12px; padding: 5px;")
        button_layout.addWidget(self.rec_model_combo)

        # Add spacer
        button_layout.addStretch()

        # Zoom controls
        zoom_in_btn = QPushButton("Zoom In (+)")
        zoom_in_btn.clicked.connect(lambda: self.image_widget.zoom_in())
        zoom_in_btn.setStyleSheet("font-size: 14px; padding: 10px;")
        button_layout.addWidget(zoom_in_btn)

        zoom_out_btn = QPushButton("Zoom Out (-)")
        zoom_out_btn.clicked.connect(lambda: self.image_widget.zoom_out())
        zoom_out_btn.setStyleSheet("font-size: 14px; padding: 10px;")
        button_layout.addWidget(zoom_out_btn)

        zoom_reset_btn = QPushButton("Reset Zoom")
        zoom_reset_btn.clicked.connect(lambda: self.image_widget.zoom_reset())
        zoom_reset_btn.setStyleSheet("font-size: 14px; padding: 10px;")
        button_layout.addWidget(zoom_reset_btn)

        # Zoom level label
        self.zoom_label = QLabel("100%")
        self.zoom_label.setStyleSheet("font-size: 14px; padding: 10px; font-weight: bold;")
        button_layout.addWidget(self.zoom_label)

        main_layout.addLayout(button_layout)

        # Content layout (image and text side by side)
        content_layout = QHBoxLayout()

        # Image with word boxes display area
        image_container = QVBoxLayout()
        image_label = QLabel("Image with Detected Words")
        image_label.setStyleSheet("font-weight: bold; font-size: 12px;")
        image_container.addWidget(image_label)

        # Scroll area for image
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setMinimumWidth(450)

        # Custom image widget with word boxes
        self.image_widget = ImageWithBoxes()
        self.image_widget.setAlignment(Qt.AlignCenter)
        self.image_widget.setStyleSheet("background-color: #f0f0f0; border: 2px solid #ccc;")
        self.image_widget.setMinimumSize(400, 400)
        self.image_widget.word_clicked.connect(self.on_word_box_clicked)
        self.image_widget.zoom_changed.connect(self.on_zoom_changed)
        self.image_widget.selection_changed.connect(self.on_selection_changed)

        scroll_area.setWidget(self.image_widget)
        image_container.addWidget(scroll_area)

        content_layout.addLayout(image_container)

        # Text output area
        text_container = QVBoxLayout()
        text_label = QLabel("Extracted Text")
        text_label.setStyleSheet("font-weight: bold; font-size: 12px;")
        text_container.addWidget(text_label)

        self.text_output = QTextEdit()
        self.text_output.setReadOnly(True)
        self.text_output.setPlaceholderText("Extracted text will appear here...")
        self.text_output.setStyleSheet("font-size: 12px; padding: 5px;")
        text_container.addWidget(self.text_output)

        content_layout.addLayout(text_container)

        main_layout.addLayout(content_layout)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setStyleSheet("QProgressBar { height: 20px; text-align: center; }")
        self.progress_bar.setVisible(False)  # Hidden by default
        main_layout.addWidget(self.progress_bar)

        # Status label
        self.status_label = QLabel("Ready")
        self.status_label.setStyleSheet("padding: 5px; background-color: #e8e8e8;")
        main_layout.addWidget(self.status_label)

    def upload_image(self):
        file_name, _ = QFileDialog.getOpenFileName(
            self,
            "Select Image",
            "",
            "Image Files (*.png *.jpg *.jpeg *.bmp);;All Files (*)"
        )

        if file_name:
            self.image_path = file_name
            self.status_label.setText(f"Loaded: {os.path.basename(file_name)} - Click 'Process Image' to run OCR")

            # Load image same way PaddleOCR does
            from PIL import Image
            import numpy as np

            pil_image = Image.open(file_name)
            # Convert to RGB if needed
            if pil_image.mode != 'RGB':
                pil_image = pil_image.convert('RGB')

            # Save to temporary file to ensure consistent loading
            import tempfile
            temp_path = tempfile.mktemp(suffix='.png')
            pil_image.save(temp_path)

            # Now load into QPixmap
            pixmap = QPixmap(temp_path)
            if not pixmap.isNull():
                self.image_widget.set_image(pixmap)
                print(f"Loaded pixmap: {pixmap.width()}x{pixmap.height()}")

            self.text_output.clear()
            self.text_output.setPlaceholderText("Click 'Process Image' to extract text...")

            # Enable the process and select buttons now that an image is loaded
            self.process_btn.setEnabled(True)
            self.select_area_btn.setEnabled(True)

    def process_image(self):
        """Process the currently loaded image with OCR"""
        if self.image_path:
            # Disable button while processing
            self.process_btn.setEnabled(False)
            self.extract_text(self.image_path)

    def extract_text(self, image_path):
        self.text_output.setText("Initializing OCR...")
        self.status_label.setText("Starting OCR process...")

        # Show and reset progress bar
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)

        # Create and start worker thread
        self.ocr_worker = OCRWorker(
            image_path,
            det_model=self.selected_det_model,
            rec_model=self.selected_rec_model
        )
        self.ocr_worker.finished.connect(self.on_ocr_complete)
        self.ocr_worker.words_detected.connect(self.on_words_detected)
        self.ocr_worker.error.connect(self.on_ocr_error)
        self.ocr_worker.progress.connect(self.on_ocr_progress)
        self.ocr_worker.progress_value.connect(self.on_progress_value_changed)
        self.ocr_worker.preprocessed_image.connect(self.on_preprocessed_image)  # ADD THIS
        self.ocr_worker.start()

    def on_preprocessed_image(self, image_path):
        """Update display with the preprocessed image that OCR actually used"""
        # IMPORTANT: Don't replace image when processing selection
        # (selection coordinates won't align with preprocessed image)
        if self.is_processing_selection:
            print("Skipping preprocessed image display (selection mode)")
            return

        print(f"Loading preprocessed image: {image_path}")
        pixmap = QPixmap(image_path)
        if not pixmap.isNull():
            self.image_widget.set_image(pixmap)
            print(f"Loaded preprocessed image: {pixmap.width()}x{pixmap.height()}")
        else:
            print("Failed to load preprocessed image")

    def on_ocr_progress(self, status):
        self.status_label.setText(status)
        self.text_output.setText(f"Processing...\n\n{status}")

    def on_progress_value_changed(self, value):
        """Update progress bar value"""
        self.progress_bar.setValue(value)

    def on_words_detected(self, words):
        """Set word data on the image widget"""
        self.word_data = words

        # Debug: Print word data
        print(f"Received {len(words)} words")
        for i, word in enumerate(words):
            print(f"Word {i}: {word}")

        self.image_widget.set_word_data(words)

        if not words:
            self.text_output.setText("No words detected in image")
        else:
            # Count words with bounding boxes
            words_with_bbox = sum(1 for w in words if 'bbox' in w and w['bbox'])
            self.text_output.setText(f"Detected {len(words)} word(s) ({words_with_bbox} with bounding boxes). Click on a word box to see details.")

    def on_word_box_clicked(self, word_info):
        """Display word details when a word box is clicked"""
        if word_info:
            details = f"Word: {word_info.get('text', 'N/A')}\n"
            details += f"Confidence: {word_info.get('confidence', 'N/A')}\n"
            details += f"Index: {word_info.get('index', 'N/A')}\n"

            if 'bbox' in word_info and word_info['bbox']:
                details += f"\nBounding Box:\n"
                bbox = word_info['bbox']
                for i, point in enumerate(bbox):
                    details += f"  Point {i+1}: ({point[0]:.1f}, {point[1]:.1f})\n"

            self.text_output.setText(details)

    def on_zoom_changed(self, zoom_level):
        """Update zoom label when zoom level changes"""
        self.zoom_label.setText(f"{int(zoom_level * 100)}%")

    def on_ocr_complete(self, text):
        self.status_label.setText("OCR completed successfully")
        self.progress_bar.setVisible(False)
        # Re-enable buttons
        self.process_btn.setEnabled(True)
        self.select_area_btn.setEnabled(True)
        # Reset processing flag
        self.is_processing_selection = False

    def on_ocr_error(self, error_msg):
        self.text_output.setText(error_msg)
        self.status_label.setText("OCR failed")
        self.progress_bar.setVisible(False)
        # Re-enable buttons
        self.process_btn.setEnabled(True)
        self.select_area_btn.setEnabled(True)
        # Reset processing flag
        self.is_processing_selection = False

    def on_detection_model_changed(self, model_name):
        """Handle detection model selection change"""
        self.selected_det_model = model_name
        self.settings.setValue(self.SETTINGS_DET_MODEL, model_name)
        self.status_label.setText(f"Detection model: {model_name}")

    def on_recognition_model_changed(self, model_name):
        """Handle recognition model selection change"""
        self.selected_rec_model = model_name
        self.settings.setValue(self.SETTINGS_REC_MODEL, model_name)
        self.status_label.setText(f"Recognition model: {model_name}")

    # Selection mode methods
    def toggle_selection_mode(self, enabled):
        """Handle selection mode toggle"""
        self.image_widget.set_selection_mode(enabled)

        # Update button states
        if enabled:
            # Entering selection mode
            self.process_btn.setEnabled(False)  # Disable full image processing
            self.status_label.setText("Selection mode active - draw a rectangle on the image")
        else:
            # Exiting selection mode
            self.process_btn.setEnabled(True)  # Re-enable full processing
            self.status_label.setText("Selection mode disabled")

    def process_selection(self):
        """Process the selected area with OCR"""
        if not self.image_widget.selection_rect_original:
            return

        # Validate selection size
        if not self.image_widget.validate_selection():
            self.status_label.setText(f"Selection too small - minimum {self.image_widget.MIN_SELECTION_SIZE}px")
            return

        crop_rect = self.image_widget.selection_rect_original
        if crop_rect and self.image_path:
            # Clear previous word boxes before processing
            self.image_widget.set_word_data([])
            self.extract_text_from_crop(self.image_path, crop_rect)

    def extract_text_from_crop(self, image_path, crop_rect):
        """Start OCR worker with crop parameters"""
        self.text_output.setText("Initializing OCR for selected area...")
        self.status_label.setText(f"Processing selection: {crop_rect}...")

        # Store crop rect for reference
        self.current_crop_rect = crop_rect
        self.is_processing_selection = True

        # Show and reset progress bar
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)

        # Disable buttons during processing
        self.process_selection_btn.setEnabled(False)
        self.select_area_btn.setEnabled(False)

        # Create and start worker thread with crop parameters
        self.ocr_worker = OCRWorker(
            image_path,
            det_model=self.selected_det_model,
            rec_model=self.selected_rec_model,
            crop_rect=crop_rect  # Pass crop parameters
        )

        # Connect signals (same as full image processing)
        self.ocr_worker.finished.connect(self.on_ocr_complete)
        self.ocr_worker.words_detected.connect(self.on_words_detected)
        self.ocr_worker.error.connect(self.on_ocr_error)
        self.ocr_worker.progress.connect(self.on_ocr_progress)
        self.ocr_worker.progress_value.connect(self.on_progress_value_changed)
        self.ocr_worker.preprocessed_image.connect(self.on_preprocessed_image)

        self.ocr_worker.start()

    def clear_selection(self):
        """Clear the selection and return to normal mode"""
        self.image_widget.clear_selection()
        self.image_widget.set_selection_mode(False)
        self.select_area_btn.setChecked(False)
        self.process_btn.setEnabled(True)
        self.current_crop_rect = None
        self.is_processing_selection = False
        self.status_label.setText("Selection cleared")

    def on_selection_changed(self, has_selection):
        """Enable/disable selection-related buttons when selection state changes"""
        # Enable process/clear buttons only if selection is valid
        is_valid = has_selection and self.image_widget.validate_selection()
        self.process_selection_btn.setEnabled(is_valid)
        self.clear_selection_btn.setEnabled(has_selection)

        if has_selection and not is_valid:
            self.status_label.setText(f"Selection too small - minimum {self.image_widget.MIN_SELECTION_SIZE}px")
        elif has_selection:
            x, y, w, h = self.image_widget.selection_rect_original
            self.status_label.setText(f"Selection: {w}x{h}px at ({x}, {y}) - Click 'Process Selection' to run OCR")


def main():
    app = QApplication(sys.argv)
    window = OCRApp()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
