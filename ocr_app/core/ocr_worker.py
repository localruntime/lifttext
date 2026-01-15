"""OCR worker thread for background processing"""
from PySide6.QtCore import QThread, Signal
from paddleocr import PaddleOCR


class OCRWorker(QThread):
    """Worker thread for OCR processing to keep UI responsive"""
    finished = Signal(str)
    words_detected = Signal(list)  # Emits list of word dictionaries
    error = Signal(str)
    progress = Signal(str)
    progress_value = Signal(int)  # Emits progress percentage (0-100)
    preprocessed_image = Signal(str)  # Signal to send preprocessed image path

    def __init__(self, image_path, det_model='PP-OCRv4_mobile_det', rec_model='en_PP-OCRv4_mobile_rec', language='en', crop_rect=None):
        super().__init__()
        self.image_path = image_path
        self.det_model = det_model
        self.rec_model = rec_model
        self.language = language
        self.crop_rect = crop_rect  # (x, y, width, height) in original image coords
        self.ocr = None

    def run(self):
        try:
            # Initialize OCR engine (PaddleOCR v3) with mobile/slim models for fast performance
            self.progress_value.emit(10)
            self.progress.emit("Initializing OCR engine (this may take a while on first run)...")
            self.ocr = PaddleOCR(
                # Use mobile/slim models for faster performance
                text_detection_model_name=self.det_model,      # Configurable detection model
                text_recognition_model_name=self.rec_model,    # Configurable recognition model

                # Enable preprocessing for better accuracy
                use_doc_orientation_classify=False,  # Disable document orientation classification
                use_doc_unwarping=False,             # Disable document unwarping
                use_textline_orientation=True,       # Enable text orientation detection for better recognition
                lang=self.language,

                # Detection parameters optimized for accuracy
                text_det_limit_side_len=1280,    # Higher resolution for better quality (increased from 960)
                text_det_thresh=0.5,             # Higher threshold for more confident detection (increased from 0.3)
                text_det_box_thresh=0.6,         # Higher box threshold for accuracy (increased from 0.5)
                det_db_unclip_ratio=1.5,         # Conservative box expansion for accurate crops (reduced from 3.0)

                # Recognition parameters for accuracy
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

            # Extract text from results
            self.progress_value.emit(80)
            self.progress.emit("Extracting text from results...")
            text_lines = []
            word_data = []

            # PaddleOCR can return different formats
            if result and isinstance(result, list) and len(result) > 0:
                page_result = result[0]

                if page_result is None:
                    pass  # No text detected

                # Handle dictionary format (newer PaddleOCR)
                elif isinstance(page_result, dict):
                    # EXTRACT AND SAVE THE PREPROCESSED IMAGE
                    if 'doc_preprocessor_res' in page_result:
                        preprocessed_img = page_result['doc_preprocessor_res'].get('output_img')

                        if preprocessed_img is not None:
                            import tempfile
                            from PIL import Image

                            # Save preprocessed image to temp file
                            temp_path = tempfile.mktemp(suffix='.png')
                            Image.fromarray(preprocessed_img).save(temp_path)

                            # Emit signal with preprocessed image path
                            self.preprocessed_image.emit(temp_path)

                    # Extract data from dictionary (try both singular and plural keys)
                    bboxes = page_result.get('dt_polys', [])
                    texts = page_result.get('rec_texts', page_result.get('rec_text', []))
                    scores = page_result.get('rec_scores', page_result.get('rec_score', []))

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
                            else:
                                word_entry['bbox'] = bbox

                        word_data.append(word_entry)

                # Handle list format (older PaddleOCR): [[bbox, (text, confidence)], ...]
                elif isinstance(page_result, list):
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
                                else:
                                    word_entry['bbox'] = bbox

                            word_data.append(word_entry)

            extracted_text = '\n'.join(text_lines) if text_lines else "No text detected in image"
            self.words_detected.emit(word_data)
            self.progress_value.emit(100)
            self.finished.emit(extracted_text)

        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            self.error.emit(f"Error during OCR: {str(e)}\n\nDetails:\n{error_details}")
