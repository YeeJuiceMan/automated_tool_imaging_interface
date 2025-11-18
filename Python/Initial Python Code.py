import os
os.environ["OPENCV_VIDEOIO_PRIORITY_GSTREAMER"] = "0"

import cv2

print("Testing video devices...")
for i in range(6):
    cap = cv2.VideoCapture(i, cv2.CAP_V4L2)
    print(i, "Opened:", cap.isOpened())
    cap.release()
