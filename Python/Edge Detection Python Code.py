import cv2
import numpy as np

# Open the USB camera (usually index 0, 1, etc.)
cap = cv2.VideoCapture(0)

if not cap.isOpened():
    print("Error: Could not open camera.")
    exit()

while True:
    # Capture frame-by-frame
    ret, frame = cap.read()
    if not ret:
        print("Error: Failed to read frame.")
        break

    # Convert to grayscale
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    # Detect edges using Canny
    edges = cv2.Canny(gray, 100, 200)

    # Create a color version of the edges (e.g., red)
    edge_colored = np.zeros_like(frame)
    edge_colored[edges != 0] = [0, 0, 255]  # Red edges

    # Overlay edges on the original frame
    overlay = cv2.addWeighted(frame, 0.8, edge_colored, 1.0, 0)

    # Display the result
    cv2.imshow("Edge Detection", overlay)

    # Press 'q' to exit
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

# Release the camera and close all windows
cap.release()
cv2.destroyAllWindows()


