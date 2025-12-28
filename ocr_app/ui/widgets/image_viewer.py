"""Image viewer widget with interactive word boxes using mixin composition"""
from PySide6.QtWidgets import QLabel
from PySide6.QtCore import Qt, Signal, QPoint
from PySide6.QtGui import QPainter

from .image_mixins import ZoomPanMixin, SelectionMixin, RenderingMixin


class ImageWithBoxes(QLabel, ZoomPanMixin, SelectionMixin, RenderingMixin):
    """Custom widget that displays an image with clickable word boxes"""
    word_clicked = Signal(object)  # Emits word data when a box is clicked (dict or None)
    zoom_changed = Signal(float)  # Emits current zoom level
    selection_changed = Signal(bool)  # Emits when selection becomes active/inactive

    def __init__(self):
        QLabel.__init__(self)

        # Core properties
        self.original_pixmap = None
        self.scaled_pixmap = None
        self.word_data = []
        self.selected_word_index = None
        self.scale_factor = 1.0
        self.offset_x = 0
        self.offset_y = 0
        self.hovered_word_index = None

        # Initialize mixins
        self.__init_zoom_pan__()
        self.__init_selection__()

        # Configure widget
        self.setMouseTracking(True)

    def set_image(self, pixmap):
        """Set the image to display"""
        self.original_pixmap = pixmap
        self.word_data = []
        self.selected_word_index = None
        self.hovered_word_index = None
        self.zoom_level = 1.0  # Reset zoom when loading new image
        self.pan_offset_x = 0  # Reset pan when loading new image
        self.pan_offset_y = 0
        self.update_display()

    def set_word_data(self, words):
        """Set word bounding box data"""
        self.word_data = words
        self.update()

    def resizeEvent(self, event):
        """Handle resize events"""
        super().resizeEvent(event)
        self.update_display()

    def paintEvent(self, event):
        """Custom paint to draw image, word boxes, and selection"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # Render image and word boxes (from RenderingMixin)
        self.render_image_and_boxes(painter)

        # Draw selection rectangle and overlay (from RenderingMixin)
        self.render_selection_overlay(painter)

    def mousePressEvent(self, event):
        """Handle mouse clicks for panning, selection, and word box clicking"""
        # PRIORITY 1: Pan always works (middle/right button)
        if self.handle_pan_press(event):
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
            word_found = False

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
                        word_found = True
                        break

            # If clicked on empty space, clear selection
            if not word_found and self.selected_word_index is not None:
                self.selected_word_index = None
                self.word_clicked.emit(None)  # Signal deselection
                self.update()

    def mouseReleaseEvent(self, event):
        """Handle mouse release to end panning and finalize selection"""
        # Handle pan release
        if self.handle_pan_release(event):
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
        if self.handle_pan_move(event):
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
