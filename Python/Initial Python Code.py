

import tkinter as tk
from tkinter import messagebox
from tkinter import ttk
import os
import cv2
import time
from datetime import datetime
import RPi.GPIO as GPIO
from threading import Thread
import threading



# Hardware control flag (False for Windows) so set true on raspberry pi
RUNNING_ON_RASPBERRY_PI = True
AUTO_START = False
ALIGN_UP = False
# Where the images are stored, changes depending on where you are storing it (this is an example)

# Hardware Configuration

#PLAN - USE 5,6, 13, 19 for One and 16,26, 20,21 for Second
VERT_STP1_BLACK = 5
VERT_STP1_GREEN= 6
VERT_STP1_RED = 13
VERT_STP1_BLUE = 19

VERT_STP2_BLACK = 16
VERT_STP2_GREEN= 26
VERT_STP2_RED = 20
VERT_STP2_BLUE = 21


# Stepper Motor Pins (L298N)
STP_IN1 = 22  #Red A
STP_IN2 = 23  #Yellow A
STP_IN3 = 24  #Gray B
STP_IN4 = 25  #Green B

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
if not RUNNING_ON_RASPBERRY_PI:
    BASE_DIR = r"C:\Users\csmid\OneDrive - The Pennsylvania State University\Images"
else:
    BASE_DIR = "/home/seco-tools-capstone/Desktop"

# Create base directory (if non existant)
os.makedirs(BASE_DIR, exist_ok=True)

# Current position of camera (top is 0)
CAM_YPOS  = 0
CAM_BIT_TOP_POS = 0
CAM_MIN = 0
CAM_MAX = 940

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
    GPIO.setup([VERT_STP1_BLACK, VERT_STP1_GREEN, VERT_STP1_RED, VERT_STP1_BLUE, 
                VERT_STP2_BLACK, VERT_STP2_GREEN, VERT_STP2_RED, VERT_STP2_BLUE, 
                STP_IN1, STP_IN2, STP_IN3, STP_IN4], GPIO.OUT)
        
    # Initialize all pins to LOW bc HIGH disables stepper and acuator (active LOW)
    GPIO.output([VERT_STP1_BLACK, VERT_STP1_GREEN, VERT_STP1_RED, VERT_STP1_BLUE, 
                VERT_STP2_BLACK, VERT_STP2_GREEN, VERT_STP2_RED, VERT_STP2_BLUE, 
                  STP_IN1, STP_IN2, STP_IN3, STP_IN4], GPIO.LOW)

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
        steps = int((degrees/360) * self.steps_per_rev )
        direction = 1 if clockwise else -1
        sequence = self.step_sequence if clockwise else self.step_sequence[::-1]
        for _ in range(steps):
            for step in sequence:
                for pin in range(4):
                    GPIO.output(self.step_pins[pin], step[pin])
                time.sleep(self.step_delay)

class ActuatorController:
    def __init__(self, stepper1_pins, stepper2_pins, step_sequence, steps_per_rev, gear_ratio):#, cam_min, cam_max):
        # Each actuator now has two vertical stepper motors
        self.stepper1_pins = stepper1_pins
        self.stepper2_pins = stepper2_pins
        self.step_sequence = step_sequence
        self.steps_per_rev = steps_per_rev
        self.gear_ratio = gear_ratio
        self.step_delay = 0.001
        self.stop_flag = False
        self.current_step = 0

    def move(self, degrees, upward=True):
        # Calculate how many steps to move
        steps = int((degrees / 360) * self.steps_per_rev * self.gear_ratio)
        sequence = self.step_sequence if upward else self.step_sequence[::-1]
       
        step_count = 0
        degree_count = 0
        for _ in range(steps):
            if not self.stop_flag:
                for step in sequence:
                    # Apply the same step pattern to both motors
                    for pin in range(4):
                       
                        # Motor 1
                        GPIO.output(self.stepper1_pins[0], step[0])
                        GPIO.output(self.stepper1_pins[1], step[1])
                        GPIO.output(self.stepper1_pins[2], step[2])
                        GPIO.output(self.stepper1_pins[3], step[3])

                        # Motor 2
                        GPIO.output(self.stepper2_pins[0], step[0])
                        GPIO.output(self.stepper2_pins[1], step[1])
                        GPIO.output(self.stepper2_pins[2], step[2])
                        GPIO.output(self.stepper2_pins[3], step[3])
                       
                    time.sleep(self.step_delay)
                    step_count += 1
                   
            else:
                self.stop()
                break
        degree_count = int(round((step_count / (self.steps_per_rev * self.gear_ratio)) * 90))
        return degree_count


    def extend(self, degrees=90):
        #Raise tool holder (both steppers move upward).    
        self.stop_flag = False
        return self.move(degrees, upward=True)

    def retract(self, degrees=90):
        #Lower tool holder (both steppers move downward).
        self.stop_flag = False
        return self.move(degrees, upward=False)

    def stop(self):
        #Disable all coils.
        for pin in self.stepper1_pins + self.stepper2_pins:
            GPIO.output(pin, GPIO.LOW)
        return 0
    
class MicroscopeManager:
    def __init__(self, camera_indices):
        self.cameras = []
        self.camera_indices = camera_indices
        self.initialize_cameras()

    def initialize_cameras(self):
        for idx in self.camera_indices:
            try:
                WIDTH, HEIGHT = 640, 480

                # open captures
                camera = cv2.VideoCapture(idx, cv2.CAP_V4L2)
                
                camera.set(cv2.CAP_PROP_FRAME_WIDTH, WIDTH)
                camera.set(cv2.CAP_PROP_FRAME_HEIGHT, HEIGHT)
                camera.set(cv2.CAP_PROP_AUTOFOCUS, 0)
                camera.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))


                if camera.isOpened():
                    self.cameras.append(camera)
                    print(f"Camera {idx} initialized successfully")
                else:
                    print(f"Failed to open camera {idx}")
            except Exception as e:
                print(f"Error initializing camera {idx}: {e}")

        # check if cameras were initialized
        if len(self.cameras) != len(self.camera_indices):
            print("WARNING: Not all cameras were initialized!")

    def capture_images(self, tool_number, flute_number, layer_number, height, position, camera_num=None):
        """Capture images from all cameras"""
        timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
        date_folder = datetime.now().strftime('%Y-%m-%d')
        tool_folder = f"T{tool_number}_FL{flute_number}_OD{layer_number}"
        folder_path = os.path.join(BASE_DIR, tool_folder)
        os.makedirs(folder_path, exist_ok=True)

        file_paths = []

        # position names for the cameras
        positions = ["top", "side1", "side2"]
        
        if camera_num is not None:
            if camera_num < len(self.cameras):
                cameras_to_use = [(camera_num, self.cameras[camera_num])]
            else:
                return []
        else:
            cameras_to_use = list(enumerate(self.cameras))
        for i, camera in cameras_to_use:
            # Take multiple frames to ensure good quality
            for _ in range(10):
                ret, frame = camera.read()

            if ret:
               
                # "T# FL# OD L# M/AP"
                
                file_name = f"{datetime.now().strftime('%Y-%m-%d')}_L{height}_{positions[i]}_{int(position)}deg.jpg"
                file_path = os.path.join(folder_path, file_name)

                # save the image
                cv2.imwrite(file_path, frame)
                file_paths.append(file_path)
                print(f"Image captured: {file_path}")
            else:
                print(f"Failed to capture image from camera {i}")

        return file_paths

    def close(self):
        """Release all cameras"""
        for camera in self.cameras:
            camera.release()
        print("All cameras released")


def automated_capture_sequence(tool_number, flute_number, layer_number, cameras, actuator, stepper):
    #run  the automated capture sequence
    try:
        angle_increment = 95/(int(flute_number))

        all_file_paths = []
        
        time.sleep(0.5)
        cam_height = 0
        cam_height += actuator.extend(920)
       
        # initial positioning by starting with tool fully down
        image_paths = cameras.capture_images(tool_number, flute_number, layer_number, 0, 0, 0)
        all_file_paths.extend(image_paths)
        # wait for stability 
        time.sleep(0.5)
        # go through 
        
        for x in range(int(layer_number)):
            current_angle = 0
            cam_height -= actuator.retract(200/int(layer_number))
          
            for position in range(int(flute_number)):
                current_angle += 180/int(flute_number)
               
                # capture images from all cameras
            
                image_paths = cameras.capture_images(tool_number, flute_number, layer_number, current_height, current_angle, 1)
                all_file_paths.extend(image_paths)
                image_paths = cameras.capture_images(tool_number, flute_number, layer_number, current_height, current_angle, 2)
                all_file_paths.extend(image_paths)

                # rotate to next position             
                stepper.rotate_degrees(angle_increment)
                #wait
                time.sleep(0.3)
            #reverse    
            for position in range(int(flute_number)):
                stepper.rotate_degrees(angle_increment, False)
        cam_height -= actuator.retract(cam_height)   
        return all_file_paths
        
        
    except Exception as e:
        print(f"Error during capture sequence: {e}")
        raise e

class CustomThread(Thread):
    def __init__(self, group=None, target=None, name=None, args=(), kwargs={}, verbose=None):
        # Initializing the Thread class
        super().__init__(group, target, name, args, kwargs)
        self._return = None

    # Overriding the Thread.run function
    def run(self):
        if self._target is not None:
            self._return = self._target(*self._args, **self._kwargs)

    def join(self):
        super().join()
        return self._return

class ToolInterface:
    def __init__(self, cam_min):#, cam_max):
        self.window = tk.Tk()
        self.window.title("Tool Imaging Station")
        self.align_bool = False
        self.move_threadu = None
        self.move_threadd = None
        self.up_stat = True
        self.cam_min = cam_min
        self.has_aligned_up = False 
      
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
        
       # self.actuator = ActuatorController(ACT_IN1, ACT_IN2)  OLD ACTUATOR
        self.actuator = ActuatorController(
                stepper1_pins=[VERT_STP1_BLACK, VERT_STP1_GREEN, VERT_STP1_RED, VERT_STP1_BLUE],
                stepper2_pins=[VERT_STP2_BLACK, VERT_STP2_GREEN, VERT_STP2_RED, VERT_STP2_BLUE],
            step_sequence=STEP_SEQ,
            steps_per_rev=STEPS_PER_REVOLUTION,
            gear_ratio=GEAR_RATIO
        )
        self.cameras = MicroscopeManager(CAMERA_INDICES)

         # GUI elements
        self.create_widgets()
        if AUTO_START:
            self.window.after(1000, self.auto_start)   #for autostart

    def create_widgets(self):
        # input
        tk.Label(self.window, text="Tool Number:").grid(row=0, column=0, sticky="w", padx=5, pady=5)
        tk.Label(self.window, text="Flute Number:").grid(row=1, column=0, sticky="w", padx=5, pady=5)
        tk.Label(self.window, text="Layer Number:").grid(row=2, column=0, sticky="w", padx=5, pady=5)
        tk.Label(self.window, text="Height to Check:").grid(row=3, column=0, sticky="w", padx=5, pady=5)
        tk.Label(self.window, text="Color:").grid(row=4, column=0, sticky="w", padx=5, pady=5)
        
        self.tool_number = tk.Entry(self.window)
        self.flute_number = tk.Entry(self.window)
        self.layer_number = tk.Entry(self.window)
        self.height = tk.Entry(self.window)
        self.color = tk.StringVar(value="Select Color")  # default display text
        self.color_dropdown = ttk.Combobox(self.window, textvariable=self.color, values=["Silver", "Black", "Gold"],state="readonly" )
        
        self.tool_number.grid(row=0, column=1, padx=5, pady=5, columnspan=4)
        self.flute_number.grid(row=1, column=1, padx=5, pady=5, columnspan=4)
        self.layer_number.grid(row=2, column=1, padx=5, pady=5, columnspan=4)
        self.height.grid(row=3, column=1, padx=5, pady=5, columnspan=4)

        self.color_dropdown.grid(row=4, column=1, padx=5, pady=5, columnspan=4)

        # status display
        self.status_text = tk.StringVar()
        self.status_text.set("Ready to start. Press 'align up/down' to move cameras. Press again to stop")
        self.status_label = tk.Label(self.window, textvariable=self.status_text,
                                    bd=1, relief=tk.SUNKEN, anchor=tk.W)
        # ew is parameter in Tinker GUI ew aligns the widget to both left and right edges, making it stretch horizontally across its grid cell
        self.status_label.grid(row=6, column=0, columnspan=4, sticky="ew", padx=0, pady=0)

        # control buttons
        self.start_button = tk.Button(self.window, text="Start Imaging", command=self.start_process)
        self.start_button.grid(row=5, column=0, padx=1, pady=10)

        self.top_bit_button = tk.Button(self.window, text="Set Bit Top", command=self.bit_top)
        self.top_bit_button.grid(row=5, column=1, padx=1, pady=10)

        self.alignu_button = tk.Button(self.window, text="Align Up", command=self.align_up)
        self.alignu_button.grid(row=5, column=2, padx=1, pady=10)

        self.alignd_button = tk.Button(self.window, text="Align Down", command=self.align_down)
        self.alignd_button.grid(row=5, column=3, padx=1, pady=10)

        self.set_top = tk.Button(self.window, text=" Set Top", command=self.set_top)
        self.set_top.grid(row=5, column=4, padx=1, pady=10)

        self.exit_button = tk.Button(self.window, text="Exit", command=self.cleanup_and_exit)
        self.exit_button.grid(row=5, column=5, padx=1, pady=10)

    def align_up(self):
        global CAM_YPOS
        if not self.align_bool:# and CAM_YPOS >= self.cam_min and not self.top:
            # Start retracting in background thread
            self.bottom = False
            self.move_threadu = CustomThread(
                target=self.actuator.retract,
                args=(2000,),
                #daemon=True
            )
            self.move_threadu.start()

            self.align_bool = True
            self.up_stat = True
            self.alignu_button.config(text="STOP Align Up")
            

        elif self.up_stat:# and not self.top: #only disable motor when moving UP
            # Second press → stop
            self.actuator.stop_flag = True    # tell actuator to stop
            result = self.move_threadu.join()
            CAM_YPOS -= result
            if CAM_YPOS <= self.cam_min: 
                CAM_YPOS = self.cam_min           
            self.align_bool = False
            self.alignu_button.config(text="Align Up")
            self.has_aligned_up = True 

    def align_down(self):
        global CAM_YPOS
        if not self.align_bool:# and CAM_YPOS <= self.cam_max and not self.bottom:
            self.top = False
        # Start retracting in background thread
            self.move_threadd = CustomThread(
                target=self.actuator.extend,
                
                args=(2000,),
                #daemon=True
            )
            self.move_threadd.start()

            self.align_bool = True
            self.up_stat = False
            self.alignd_button.config(text="STOP Align Down")

        elif not self.up_stat:# and not self.bottom: # only disable motor when moving DOWN
            # Second press → stop
            self.actuator.stop_flag = True    # tell actuator to stop
            result = self.move_threadd.join()
            
            CAM_YPOS += result
            
                     
            self.align_bool = False
            self.alignd_button.config(text="Align Down")

    def set_top(self): # sets the 0 position (manual)
        global CAM_YPOS
        CAM_YPOS = 0
        self.update_status("Current position set as top.")

    def bit_top(self): # will save in folder in the future
        global CAM_BIT_TOP_POS, CAM_YPOS
        CAM_BIT_TOP_POS = CAM_YPOS
        self.update_status(f"Top Position Saved: {CAM_BIT_TOP_POS}")

    def update_status(self, message):
        # update status display
        self.status_text.set(message)
        self.window.update()

    def start_process(self):
        # start the imaging process in a separate thread
        try:
            if not self.has_aligned_up:
                messagebox.showwarning("Warning", "Please click 'Align Up' before starting imaging.")
                return
            
            # validate inputs
            tool_number = self.tool_number.get().strip()
            flute_number = self.flute_number.get().strip()
            layer_number = self.layer_number.get().strip()
            height = self.height.get().strip()
            color = self.color.get().strip()

            if not tool_number or not flute_number or not layer_number:
                messagebox.showerror("Error", "All fields are required!")
                return
                

            # disable start button to prevent multiple runs
            self.start_button.config(state=tk.DISABLED)

            # start imaging in a separate thread
            self.update_status("Imaging process started...")
            thread = threading.Thread(target=self.run_imaging_sequence, args=(tool_number, flute_number, layer_number))
            thread.daemon = True
            thread.start()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to start: {str(e)}")
            self.start_button.config(state=tk.NORMAL)
    
    def auto_start(self):  
        tool_number = "1"
        flute_number = "1"
        layer_number = "1"

        self.update_status("Starting imaging automatically...")
        thread = threading.Thread(
            target=self.run_imaging_sequence, 
            args=(tool_number, flute_number, layer_number)
        )
        thread.daemon = True
        thread.start()
    
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
    app = ToolInterface(cam_min = CAM_MIN)#, cam_max = CAM_MAX)
    app.run()
    #except Exception as e:
        #print(f"Critical error: {e}")
        #GPIO.cleanup()
#sudo apt-get install python3-rpi.gpio python3-opencv
#/#bin/bash rmmod uvcvideo modprobe uvcvideo nodrop=1 timeout=5000 quirks=0x80
