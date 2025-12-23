from paddleocr import PaddleOCR
import time

print("Initializing PaddleOCR with mobile-optimized settings...")
ocr = PaddleOCR(
    use_angle_cls=False,
    lang='en',
    use_gpu=False,
    det_limit_side_len=960,
    det_db_thresh=0.3,
    det_db_box_thresh=0.5,
    use_dilation=True,
    rec_batch_num=6,
    max_text_length=25,
    det_algorithm='DB',
    rec_algorithm='SVTR_LCNet',
    use_mp=False,
    total_process_num=1
)
print("PaddleOCR initialized")

print("\nRunning OCR on test.png...")
start_time = time.time()
result = ocr.ocr('test.png', cls=False)
elapsed = time.time() - start_time

print(f"\nOCR completed in {elapsed:.2f} seconds")
print(f"Result: {result}")
