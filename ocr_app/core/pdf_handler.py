"""PDF file handling and page navigation"""
import os
import tempfile
from PySide6.QtGui import QPixmap


class PDFHandler:
    """Handles PDF file loading, page navigation, and caching"""

    def __init__(self, ui_callbacks=None):
        """
        Initialize PDF handler

        Args:
            ui_callbacks: Dict with callbacks for UI updates:
                - 'update_page_label': Function to update page number label
                - 'update_page_buttons': Function to enable/disable nav buttons
                - 'show_navigation': Function to show PDF navigation controls
                - 'hide_navigation': Function to hide PDF navigation controls
        """
        self.ui_callbacks = ui_callbacks or {}

        # PDF state tracking
        self.is_pdf_mode = False
        self.current_pdf_path = None
        self.current_page_number = 0
        self.total_pdf_pages = 0
        self.pdf_page_cache = {}  # Dict[int, str] - page_num -> temp_image_path
        self.pdf_document = None  # fitz.Document object (keep open for performance)

    def reset_pdf_state(self):
        """Clear all PDF-related state and close document"""
        if self.pdf_document:
            self.pdf_document.close()
        self.is_pdf_mode = False
        self.current_pdf_path = None
        self.current_page_number = 0
        self.total_pdf_pages = 0

        # Clean up cached temp files
        for temp_path in self.pdf_page_cache.values():
            try:
                if os.path.exists(temp_path):
                    os.remove(temp_path)
            except:
                pass
        self.pdf_page_cache.clear()
        self.pdf_document = None

        # Hide navigation controls
        if 'hide_navigation' in self.ui_callbacks:
            self.ui_callbacks['hide_navigation']()

    def load_pdf_file(self, pdf_path):
        """
        Load PDF file and display first page

        Args:
            pdf_path: Path to PDF file

        Returns:
            tuple: (success: bool, message: str, first_page_path: str or None)
        """
        try:
            # Import PyMuPDF
            import fitz

            # Open PDF document
            doc = fitz.open(pdf_path)

            # Check for password protection
            if doc.needs_pass:
                doc.close()
                return (False, "Error: Password-protected PDFs are not supported", None)

            # Validate PDF has pages
            if doc.page_count == 0:
                doc.close()
                return (False, "Error: PDF has no pages", None)

            # Update PDF state
            self.pdf_document = doc
            self.current_pdf_path = pdf_path
            self.is_pdf_mode = True
            self.current_page_number = 0
            self.total_pdf_pages = doc.page_count

            # Load first page
            first_page_path = self.load_pdf_page_display(0)

            # Show navigation controls
            if 'show_navigation' in self.ui_callbacks:
                self.ui_callbacks['show_navigation']()

            # Return success
            success_msg = f"Loaded PDF: {os.path.basename(pdf_path)} ({self.total_pdf_pages} pages)"
            return (True, success_msg, first_page_path)

        except Exception as e:
            self.reset_pdf_state()
            return (False, f"Error loading PDF: {str(e)}", None)

    def load_pdf_page_display(self, page_number):
        """
        Render specific PDF page and return path to temp image

        Args:
            page_number: 0-indexed page number

        Returns:
            str: Path to rendered page image
        """
        # Check cache first
        if page_number in self.pdf_page_cache:
            temp_path = self.pdf_page_cache[page_number]
        else:
            # Render page
            import fitz
            from PIL import Image

            page = self.pdf_document.load_page(page_number)

            # Get pixmap at 2x resolution for quality
            zoom_matrix = fitz.Matrix(2, 2)
            pix = page.get_pixmap(matrix=zoom_matrix)

            # Convert to PIL Image
            pil_image = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

            # Save to temp file
            temp_path = tempfile.mktemp(suffix='.png')
            pil_image.save(temp_path)

            # Cache page (with size limit)
            self.cache_pdf_page(page_number, temp_path)

        # Update current page
        self.current_page_number = page_number

        # Update UI
        if 'update_page_label' in self.ui_callbacks:
            self.ui_callbacks['update_page_label']()
        if 'update_page_buttons' in self.ui_callbacks:
            self.ui_callbacks['update_page_buttons']()

        return temp_path

    def cache_pdf_page(self, page_number, temp_path):
        """Add page to cache with size limit"""
        MAX_CACHE_SIZE = 10

        if len(self.pdf_page_cache) >= MAX_CACHE_SIZE:
            # Remove oldest entry (FIFO)
            oldest_page = min(self.pdf_page_cache.keys())
            old_path = self.pdf_page_cache.pop(oldest_page)
            # Clean up temp file
            try:
                if os.path.exists(old_path):
                    os.remove(old_path)
            except:
                pass

        self.pdf_page_cache[page_number] = temp_path

    def navigate_to_prev_page(self):
        """
        Load previous PDF page

        Returns:
            str or None: Path to rendered page if navigation succeeded
        """
        if self.is_pdf_mode and self.current_page_number > 0:
            return self.load_pdf_page_display(self.current_page_number - 1)
        return None

    def navigate_to_next_page(self):
        """
        Load next PDF page

        Returns:
            str or None: Path to rendered page if navigation succeeded
        """
        if self.is_pdf_mode and self.current_page_number < self.total_pdf_pages - 1:
            return self.load_pdf_page_display(self.current_page_number + 1)
        return None

    def can_navigate_prev(self):
        """Check if can navigate to previous page"""
        return self.is_pdf_mode and self.current_page_number > 0

    def can_navigate_next(self):
        """Check if can navigate to next page"""
        return self.is_pdf_mode and self.current_page_number < self.total_pdf_pages - 1

    def get_page_info(self):
        """
        Get current page information

        Returns:
            tuple: (current_page_1_indexed, total_pages)
        """
        if self.is_pdf_mode:
            return (self.current_page_number + 1, self.total_pdf_pages)
        return (0, 0)
