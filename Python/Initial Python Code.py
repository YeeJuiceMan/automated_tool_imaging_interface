import os
os.environ["OPENCV_VIDEOIO_PRIORITY_GSTREAMER"] = "0"

import cv2

print("Checking /dev/video* devices...")
import glob
print(glob.glob("/dev/video*"))

print("\nTesting camera indices...")
for i in range(6):
    cap = cv2.VideoCapture(i, cv2.CAP_V4L2)
    opened = cap.isOpened()
    print(f"Index {i}: {'OPEN' if opened else 'not available'}")
    cap.release()
