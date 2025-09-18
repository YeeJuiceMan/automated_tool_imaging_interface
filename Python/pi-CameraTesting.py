import cv2
import numpy as np

# adjust these if your cameras fail to open
CAMERA_INDICES = [0, 2, 4]
WIDTH, HEIGHT = 640, 480

def main():
    # open captures
    caps = [cv2.VideoCapture(idx, cv2.CAP_V4L2) for idx in CAMERA_INDICES]
    for cap in caps:
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, WIDTH)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, HEIGHT)
        cap.set(cv2.CAP_PROP_AUTOFOCUS, 0)

    cv2.namedWindow('All Cameras', cv2.WINDOW_NORMAL)
    cv2.resizeWindow('All Cameras', WIDTH * 3, HEIGHT)

    try:
        while True:
            frames = []
            for cap in caps:
                ret, frame = cap.read()
                if not ret:
                    # if read fails, show a blank image
                    frame = np.zeros((HEIGHT, WIDTH, 3), dtype=np.uint8)
                else:
                    # resize in case actual resolution differs
                    frame = cv2.resize(frame, (WIDTH, HEIGHT))
                frames.append(frame)

            # stack horizontally
            combined = np.hstack(frames)
            cv2.imshow('All Cameras', combined)

            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

    finally:
        # cleanup
        for cap in caps:
            cap.release()
        cv2.destroyAllWindows()

if __name__ == '__main__':
    main()
