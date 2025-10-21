import tkinter as tk
from tkinter import messagebox
import os
import cv2
import time
from datetime import datetime
import threading
import numpy as np
#import RPi.GPIO as GPIO

# Hardware control flag (False for Windows) so set true on raspberry pi
RUNNING_ON_RASPBERRY_PI = False

# Where the images are stored, changes depending on where you are storing it (this is an example)
BASE_DIR = r'/home/ey/Documents/psu/Y4/460W/automated_tool_imaging_interface/test_pics'
CANNY_THRESHOLD1 = 100  # Lower threshol
CANNY_THRESHOLD2 = 200  # Upper threshold for edge detection

# Hardware Configuration
# Actuator Pins (L298N)
ACT_IN1 = 17
ACT_IN2 = 18
#cam_paths = ['/dev/video0', '/dev/video2', '/dev/video4']
#caps = [cv2.VideoCapture(path, cv2.CAP_V4L2) for path in cam_paths]
CAMERA_INDICES = [0, 2, 4]

# Stepper Motor Pins (L298N)
STP_IN1 = 22
STP_IN2 = 23
STP_IN3 = 24
STP_IN4 = 25

# Stepper Configuration
STEP_SEQ = [
    [1, 0, 1, 0],
    [0, 1, 1, 0],
    [0, 1, 0, 1],
    [1, 0, 0, 1]
]

# NEMA-23 Stepper Motor Config
# 1.8° per step
STEPS_PER_REVOLUTION = 200

# Using the GT2 Pulley: 20 teeth with 12.7mm pitch diameter
GEAR_RATIO = 20/12.7

# Camera config
NUM_CAMERAS = 3
# USB
CAMERA_INDICES = [0, 2, 4]

# Create base directory (if non existant)
os.makedirs(BASE_DIR, exist_ok=True)


if not RUNNING_ON_RASPBERRY_PI:
    class DummyGPIO:
        BCM = OUT = HIGH = LOW = IN = None
        def setmode(self, *args, **kwargs): pass
        def setwarnings(self, *args, **kwargs): pass
        def setup(self, *args, **kwargs): pass
        def output(self, *args, **kwargs): pass
        def input(self, *args, **kwargs): return 0
        def cleanup(self, *args, **kwargs): pass
    GPIO = DummyGPIO()
# GPIO(general-purpose input/output) Setup  handles both incoming and outgoing digital signals. As an input port, it can be used to communicate to the CPU the ON/OFF signals received from switches, or the digital readings received from sensors.
def setup_gpio():
    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)
       
    # Actuator pins and stepper motor pins
    GPIO.setup([ACT_IN1, ACT_IN2, STP_IN1, STP_IN2, STP_IN3, STP_IN4], GPIO.OUT)
       
    # Initialize all pins to LOW bc HIGH disables stepper and acuator (active LOW)
    GPIO.output([ACT_IN1, ACT_IN2, STP_IN1, STP_IN2, STP_IN3, STP_IN4], GPIO.LOW)

class StepperController:
    def __init__(self, step_pins, step_sequence, steps_per_rev, gear_ratio):
        self.step_pins = step_pins
        self.step_sequence = step_sequence
        self.steps_per_rev = steps_per_rev
        self.gear_ratio = gear_ratio
        self.step_delay = 0.01
        self.current_step = 0

    def rotate_degrees(self, degrees, clockwise=True):
        # calculate steps needed to rotate by a specific angle in degrees
        steps = int((degrees / 360) * self.steps_per_rev * self.gear_ratio)
        direction = 1 if clockwise else -1
        sequence = self.step_sequence if clockwise else self.step_sequence[::-1]
        for _ in range(steps):
            for step in sequence:
                for pin in range(4):
                    GPIO.output(self.step_pins[pin], step[pin])
                time.sleep(self.step_delay)

class ActuatorController:
    def __init__(self, in1, in2):
        self.in1 = in1
        self.in2 = in2

    def extend(self, duration=1.0):
        # extend the actuator so it moves tool holder up
        GPIO.output(self.in1, GPIO.HIGH)
        GPIO.output(self.in2, GPIO.LOW)
        time.sleep(duration)
        self.stop()

    def retract(self, duration=1.0):
        # retract the actuator so it move tool holder down
        GPIO.output(self.in1, GPIO.LOW)
        GPIO.output(self.in2, GPIO.HIGH)
        time.sleep(duration)
        self.stop()
   
    def stop(self):
        GPIO.output(self.in1, GPIO.LOW)
        GPIO.output(self.in2, GPIO.LOW)
   
class MicroscopeManager:
    def __init__(self, camera_indices):
        self.camera_indices = camera_indices
        self.positions = ["top", "side", "interior"]

    def capture_images(self, tool_number, flute_number, layer_number, position):
        """Capture images sequentially from each camera"""
        timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
        date_folder = datetime.now().strftime('%Y-%m-%d')
        folder_path = os.path.join(BASE_DIR, date_folder)
        os.makedirs(folder_path, exist_ok=True)
        file_paths = []

        for idx, pos in zip(self.camera_indices, self.positions):
            idx=4 # to only use the microscope on hand
            print(f"Opening camera {idx} for {pos} view...")
            try:
                # open camera with V4L2 backend
                cam = cv2.VideoCapture(idx, cv2.CAP_V4L2)
                cam.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)  # Reduced resolution
                cam.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
                cam.set(cv2.CAP_PROP_AUTOFOCUS, 0)
                cam.set(cv2.CAP_PROP_FPS, 30)
                fps = cam.get(cv2.CAP_PROP_FPS)
                print(f"Camera supports a frame rate of: {fps} FPS")
                #time.sleep(0.5)  # Warmup period

                # capture stab frames
                for i in range(20):
                    ret, frame = cam.read()
                    if i == 19:
                        ret, frame = cam.read()
                    #time.sleep(0.5)

                if ret:
                    # edge detection
                    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                    edges = cv2.Canny(gray, CANNY_THRESHOLD1, CANNY_THRESHOLD2)
                    edge_overlay = cv2.addWeighted(
                        frame, 0.7,
                        cv2.cvtColor(edges, cv2.COLOR_GRAY2BGR), 0.3, 0
                    )

                    # filename
                    filename = f"T{tool_number}_FL{flute_number}_OD{layer_number}_{pos}_{position}deg.jpg"
                    file_path = os.path.join(folder_path, filename)
                    cv2.imwrite(file_path, edge_overlay)
                    filename2 = f"T{tool_number}_FL{flute_number}_OD{layer_number}_{pos}_{position}deg_orig.jpg"
                    file_path2 = os.path.join(folder_path, filename2)
                    cv2.imwrite(file_path2, frame)
                    file_paths.append(file_path)
                    file_paths.append(file_path2)
                    print(f"Captured {pos} view: {filename}")
                else:
                    print(f"Failed to capture image from camera {idx}")

            except Exception as e:
                print(f"Error with camera {idx}: {str(e)}")
            finally:
                cam.release()
              # USB 
                time.sleep(0.5) 

        return file_paths

    def close(self):
        print("All cameras released sequentially")

def automated_capture_sequence(tool_number, flute_number, layer_number, cameras, actuator, stepper):
    try:
        angle_increment = 18
        all_file_paths = []
       
        actuator.retract(1.5)
        time.sleep(1.0)

        for position in range(20):
            current_angle = position * angle_increment
            print(f"\nPosition {position+1}/20 ({current_angle}°)")
           
            # move up and capture
            actuator.extend(1.0)
            time.sleep(1.0)  # Increased stabilization time
           
            # capture images sequentially
            image_paths = cameras.capture_images(tool_number, flute_number, layer_number, current_angle)
            all_file_paths.extend(image_paths)
           
            # move down
            actuator.retract(1.0)
            time.sleep(0.5)
           
            # rotate if not last position
            if position < 19:
                stepper.rotate_degrees(angle_increment)
                time.sleep(1.0)  # Increased rotation stabilization

        print(f"Captured {len(all_file_paths)} images total")
        return all_file_paths
       
    except Exception as e:
        print(f"Capture sequence error: {e}")
        raise e

class ToolInterface(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Tool Imaging Station")
       
        if RUNNING_ON_RASPBERRY_PI:
            GPIO.setmode(GPIO.BCM)
            GPIO.setwarnings(False)
            GPIO.setup([ACT_IN1, ACT_IN2, STP_IN1, STP_IN2, STP_IN3, STP_IN4], GPIO.OUT)

        self.stepper = StepperController(
            step_pins=[STP_IN1, STP_IN2, STP_IN3, STP_IN4],
            step_sequence=STEP_SEQ,
            steps_per_rev=STEPS_PER_REVOLUTION,
            gear_ratio=GEAR_RATIO
        )
        self.actuator = ActuatorController(ACT_IN1, ACT_IN2)
        self.cameras = MicroscopeManager(CAMERA_INDICES)
        self.create_widgets()

    def create_widgets(self):
        tk.Label(self, text="Tool Number:").grid(row=0, column=0, sticky="w", padx=5, pady=5)
        self.tool_entry = tk.Entry(self)
        self.tool_entry.grid(row=0, column=1, padx=5, pady=5)
       
        tk.Label(self, text="Flute Number:").grid(row=1, column=0, sticky="w", padx=5, pady=5)
        self.flute_entry = tk.Entry(self)
        self.flute_entry.grid(row=1, column=1, padx=5, pady=5)
       
        tk.Label(self, text="Layer Number:").grid(row=2, column=0, sticky="w", padx=5, pady=5)
        self.layer_entry = tk.Entry(self)
        self.layer_entry.grid(row=2, column=1, padx=5, pady=5)
       
        self.start_btn = tk.Button(self, text="Start Imaging", command=self.start_process)
        self.start_btn.grid(row=3, column=0, padx=5, pady=10)
       
        self.status_text = tk.StringVar()
        self.status_text.set("Ready to start...")
        self.status_label = tk.Label(self, textvariable=self.status_text, bd=1, relief=tk.SUNKEN)
        self.status_label.grid(row=4, columnspan=2, sticky="ew", padx=5, pady=5)

    def start_process(self):
        try:
            tool_number = self.tool_entry.get().strip()
            flute_number = self.flute_entry.get().strip()
            layer_number = self.layer_entry.get().strip()
           
            if not all([tool_number, flute_number, layer_number]):
                messagebox.showerror("Error", "All fields are required!")
                return
               
            self.start_btn.config(state=tk.DISABLED)
            self.status_text.set("Starting imaging sequence...")
           
            thread = threading.Thread(target=self.run_sequence, args=(tool_number, flute_number, layer_number))
            thread.daemon = True
            thread.start()
           
        except Exception as e:
            messagebox.showerror("Error", str(e))
            self.start_btn.config(state=tk.NORMAL)

    def run_sequence(self, tool_number, flute_number, layer_number):
        try:
            start_time = time.time()
            image_paths = automated_capture_sequence(
                tool_number, flute_number, layer_number,
                self.cameras, self.actuator, self.stepper
            )
           
            elapsed = time.time() - start_time
            self.status_text.set(f"Captured {len(image_paths)} images in {elapsed:.1f}s")
            messagebox.showinfo("Complete", f"Successfully captured {len(image_paths)} images")
           
        except Exception as e:
            self.status_text.set(f"Error: {str(e)}")
            messagebox.showerror("Error", str(e))
        finally:
            self.start_btn.config(state=tk.NORMAL)

    def on_close(self):
        self.cameras = None
        GPIO.cleanup()
        self.destroy()


def automated_capture_sequence(tool_number, flute_number, layer_number, cameras, actuator, stepper):
    #run  the automated capture sequence to get 20 images per tool
    try:
        # calculate angle increment for 20 positions by 360 degrees / 20 positions = 18 degrees per step
        angle_increment = 18

        # duration calculation to ensure under 8 minutes sso each position takes about 20 seconds which include movement, stabilization, capture
        # 20 positions * 20 seconds = 400 seconds which would be 6.67 minutes

        all_file_paths = []

        # initial positioning by starting with tool fully down
        actuator.retract(1.5)
        # wait for stability
        time.sleep(0.5)

        # go through 20 positions
        for position in range(20):
            current_angle = position * angle_increment
            print(f"\nCapturing at position {position+1}/20 ({current_angle}°)")

            # move to the measurement position and move the tool to camera view position
            actuator.extend(4.0)
            # wait for stability
            time.sleep(1.0)

            # capture images from all cameras
            image_paths = cameras.capture_images(tool_number, flute_number, layer_number, current_angle)
            all_file_paths.extend(image_paths)

            # move back down
            actuator.retract(4.0)
            time.sleep(1.0)

            # rotate to next position if not the last one
            if position < 19:
                stepper.rotate_degrees(angle_increment)
                #wait
                time.sleep(1.0)

        #print(f"\nCapture sequence completed. Total images: {len(all_file_paths)}")
        return all_file_paths

    except Exception as e:
        print(f"Error during capture sequence: {e}")
        raise e

class ToolInterface:
    def __init__(self):
        self.window = tk.Tk()
        self.window.title("Tool Imaging Station")

        # set up GPIO
        if RUNNING_ON_RASPBERRY_PI:
            setup_gpio()

        # initialize hardware controllers
        self.stepper = StepperController(
            step_pins=[STP_IN1, STP_IN2, STP_IN3, STP_IN4],
            step_sequence=STEP_SEQ,
            steps_per_rev=STEPS_PER_REVOLUTION,
            gear_ratio=GEAR_RATIO
        )
       
        self.actuator = ActuatorController(ACT_IN1, ACT_IN2)
        self.cameras = MicroscopeManager(CAMERA_INDICES)

         # GUI elements
        self.create_widgets()

    def create_widgets(self):
        # input
        tk.Label(self.window, text="Tool Number:").grid(row=0, column=0, sticky="w", padx=5, pady=5)
        tk.Label(self.window, text="Flute Number:").grid(row=1, column=0, sticky="w", padx=5, pady=5)
        tk.Label(self.window, text="Layer Number:").grid(row=2, column=0, sticky="w", padx=5, pady=5)

        self.tool_number = tk.Entry(self.window)
        self.flute_number = tk.Entry(self.window)
        self.layer_number = tk.Entry(self.window)

        self.tool_number.grid(row=0, column=1, padx=5, pady=5)
        self.flute_number.grid(row=1, column=1, padx=5, pady=5)
        self.layer_number.grid(row=2, column=1, padx=5, pady=5)

        # status display
        self.status_text = tk.StringVar()
        self.status_text.set("Ready to start...")
        self.status_label = tk.Label(self.window, textvariable=self.status_text,
                                    bd=1, relief=tk.SUNKEN, anchor=tk.W)
        # ew is parameter in Tinker GUI ew aligns the widget to both left and right edges, making it stretch horizontally across its grid cell
        self.status_label.grid(row=4, column=0, columnspan=2, sticky="ew", padx=5, pady=5)

        # control buttons
        self.start_button = tk.Button(self.window, text="Start Imaging", command=self.start_process)
        self.start_button.grid(row=3, column=0, padx=5, pady=10)

        self.exit_button = tk.Button(self.window, text="Exit", command=self.cleanup_and_exit)
        self.exit_button.grid(row=3, column=1, padx=5, pady=10)

    def update_status(self, message):
        # update status display
        self.status_text.set(message)
        self.window.update()

    def start_process(self):
        # start the imaging process in a separate thread
        try:
            # validate inputs
            tool_number = self.tool_number.get().strip()
            flute_number = self.flute_number.get().strip()
            layer_number = self.layer_number.get().strip()

            if not tool_number or not flute_number or not layer_number:
                messagebox.showerror("Error", "All fields are required!")
                return

            # disable start button to prevent multiple runs
            self.start_button.config(state=tk.DISABLED)

            # start imaging in a separate thread
            self.update_status("Imaging process started...")
            thread = threading.Thread(target=self.run_imaging_sequence,
                                     args=(tool_number, flute_number, layer_number))
            thread.daemon = True
            thread.start()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to start: {str(e)}")
            self.start_button.config(state=tk.NORMAL)

    def run_imaging_sequence(self, tool_number, flute_number, layer_number):
        """Run the imaging sequence in a background thread"""
        try:
            start_time = time.time()
            self.update_status("Starting automated capture sequence...")

            # run the capture sequence
            image_paths = automated_capture_sequence(
                tool_number, flute_number, layer_number,
                self.cameras, self.actuator, self.stepper
            )

            elapsed_time = time.time() - start_time
            self.update_status(f"Imaging complete! {len(image_paths)} images captured in {elapsed_time:.1f} seconds")

            # re-enable start button
            self.window.after(0, lambda: self.start_button.config(state=tk.NORMAL))

            # completion message
            self.window.after(0, lambda: messagebox.showinfo(
                "Process Complete",
                f"Successfully captured {len(image_paths)} images!\n"
                f"Total time: {elapsed_time:.1f} seconds"
            ))

        except Exception as e:
            self.update_status(f"Error: {str(e)}")
            self.window.after(0, lambda: messagebox.showerror("Error", f"Imaging failed: {str(e)}"))
            self.window.after(0, lambda: self.start_button.config(state=tk.NORMAL))

    def cleanup_and_exit(self):
        # clean up resources and exit
        try:
            self.update_status("Cleaning up...")
            self.cameras.close()
            GPIO.cleanup()
            self.window.destroy()
        except Exception as e:
            print(f"Error during cleanup: {e}")
            self.window.destroy()

    def run(self):
        # start the GUI application
        try:
            self.window.protocol("WM_DELETE_WINDOW", self.cleanup_and_exit)
            self.window.mainloop()
        except KeyboardInterrupt:
            self.cleanup_and_exit()

if __name__ == "__main__":
    #try:
    app = ToolInterface()
    app.run()
    #except Exception as e:
        #print(f"Critical error: {e}")
        #GPIO.cleanup()
#sudo apt-get install python3-rpi.gpio python3-opencv
