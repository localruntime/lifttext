"""Mixins for ImageWithBoxes widget - zoom/pan, selection, and rendering"""
from PySide6.QtCore import Qt, QRect, QPoint, Signal
from PySide6.QtGui import QPainter, QPen, QColor, QFont


class ZoomPanMixin:
    """Mixin for zoom and pan functionality"""

    def __init_zoom_pan__(self):
        """Initialize zoom/pan properties"""
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

    def zoom_in(self):
        """Zoom in by 20%"""
        if hasattr(self, 'original_pixmap') and self.original_pixmap:
            new_zoom = min(self.max_zoom, self.zoom_level * 1.2)
            if new_zoom != self.zoom_level:
                self.zoom_level = new_zoom
                self.update_display()

    def zoom_out(self):
        """Zoom out by 20%"""
        if hasattr(self, 'original_pixmap') and self.original_pixmap:
            new_zoom = max(self.min_zoom, self.zoom_level / 1.2)
            if new_zoom != self.zoom_level:
                self.zoom_level = new_zoom
                self.update_display()

    def zoom_reset(self):
        """Reset zoom to 100% and clear pan offset"""
        if hasattr(self, 'original_pixmap') and self.original_pixmap:
            self.zoom_level = 1.0
            self.pan_offset_x = 0
            self.pan_offset_y = 0
            self.update_display()

    def update_display(self):
        """Update the scaled pixmap and display"""
        if hasattr(self, 'original_pixmap') and self.original_pixmap:
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

            if hasattr(self, 'zoom_changed'):
                self.zoom_changed.emit(self.zoom_level)
            self.update()

    def handle_pan_press(self, event):
        """Handle pan button press (middle/right mouse)"""
        if event.button() in (Qt.MiddleButton, Qt.RightButton):
            self.is_panning = True
            self.pan_start_pos = event.pos()
            self.pan_start_offset_x = self.pan_offset_x
            self.pan_start_offset_y = self.pan_offset_y
            self.setCursor(Qt.ClosedHandCursor)
            return True
        return False

    def handle_pan_release(self, event):
        """Handle pan button release"""
        if event.button() in (Qt.MiddleButton, Qt.RightButton):
            if self.is_panning:
                self.is_panning = False
                self.setCursor(Qt.ArrowCursor)
                return True
        return False

    def handle_pan_move(self, event):
        """Handle pan mouse movement"""
        if self.is_panning:
            current_pos = event.pos()
            delta_x = current_pos.x() - self.pan_start_pos.x()
            delta_y = current_pos.y() - self.pan_start_pos.y()

            self.pan_offset_x = self.pan_start_offset_x + delta_x
            self.pan_offset_y = self.pan_start_offset_y + delta_y

            self.update()
            return True
        return False


class SelectionMixin:
    """Mixin for selection rectangle functionality"""

    def __init_selection__(self):
        """Initialize selection properties"""
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

    # Coordinate conversion methods
    def display_to_original_coords(self, display_x, display_y):
        """Convert display coordinates to original image coordinates"""
        if not hasattr(self, 'original_pixmap') or not self.original_pixmap:
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
        if not self.selection_rect_original or not hasattr(self, 'original_pixmap') or not self.original_pixmap:
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
        if not self.drag_start_pos or not hasattr(self, 'original_pixmap') or not self.original_pixmap:
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
        if hasattr(self, 'is_panning') and self.is_panning:
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
        elif hasattr(self, 'hovered_word_index') and self.hovered_word_index is not None:
            self.setCursor(Qt.PointingHandCursor)
        else:
            self.setCursor(Qt.ArrowCursor)


class RenderingMixin:
    """Mixin for rendering image, bounding boxes, and selection overlay"""

    def render_image_and_boxes(self, painter):
        """Render the scaled image and word boxes"""
        if not hasattr(self, 'scaled_pixmap') or not self.scaled_pixmap:
            return

        # Draw the scaled image centered with pan offset
        draw_x = self.offset_x + self.pan_offset_x
        draw_y = self.offset_y + self.pan_offset_y
        painter.drawPixmap(draw_x, draw_y, self.scaled_pixmap)

        # Draw word boxes
        if hasattr(self, 'word_data'):
            for idx, word_info in enumerate(self.word_data):
                if 'bbox' in word_info and word_info['bbox']:
                    bbox = word_info['bbox']

                    # Convert bbox coordinates to scaled display coordinates with pan offset
                    scaled_points = []
                    for point in bbox:
                        x = int(point[0] * self.scale_factor + self.offset_x + self.pan_offset_x)
                        y = int(point[1] * self.scale_factor + self.offset_y + self.pan_offset_y)
                        scaled_points.append(QPoint(x, y))

                    # Determine box color based on state
                    if hasattr(self, 'selected_word_index') and idx == self.selected_word_index:
                        pen_color = QColor(25, 118, 210)  # Blue for selected
                        fill_color = QColor(187, 222, 251, 100)  # Light blue fill
                        pen_width = 3
                    elif hasattr(self, 'hovered_word_index') and idx == self.hovered_word_index:
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

    def render_selection_overlay(self, painter):
        """Render selection rectangle and overlay"""
        if not hasattr(self, 'selection_rect_original') or not self.selection_rect_original:
            return

        display_rect = self.get_selection_display_rect()
        if not display_rect:
            return

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
        self.update_selection_handles()

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
