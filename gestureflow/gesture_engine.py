import cv2
import mediapipe as mp
import pyautogui
import time
import json
import os
import math
import threading# Crucial for preventing massive cursor lag during loop calls
pyautogui.PAUSE = 0
pyautogui.FAILSAFE = False

class GestureEngine:
    def __init__(self):
        self.cap = None # Don't initialize camera until started
        self.screen_w, self.screen_h = pyautogui.size()
        
        self.mp_hands = mp.solutions.hands
        self.hands = self.mp_hands.Hands(
            max_num_hands=1, 
            min_detection_confidence=0.6, 
            min_tracking_confidence=0.6
        )
        self.mp_draw = mp.solutions.drawing_utils
        
        # Cooldowns
        self.last_action_times = {}
        self.action_cooldowns = {
            "IDLE": 0.0,
            "SINGLE & DOUBLE CLICK": 0.25,
            "RIGHT CLICK": 0.5,
            "FORWARD": 1.0,
            "REWIND": 1.0,
            "SPACE (PLAY/PAUSE)": 1.0,
            "HALT SYSTEM": 2.0,
            "VOLUME_UP": 0.1,
            "VOLUME_DOWN": 0.1,
            "SPEED_UP": 0.5,
            "SPEED_DOWN": 0.5
        }
        
        # Smoothing variables for mouse movement
        # Setting smoothing lower (e.g. 0.05) makes it faster/more responsive.
        self.prev_x, self.prev_y = 0, 0
        self.smoothing = 0.50
        
        self.running = False
        self.thread = None
        self.lock = threading.Lock()
        self.current_frame_bytes = None
        self.load_config()

    def load_config(self):
        config_path = os.path.join(os.path.dirname(__file__), "config.json")
        try:
            with open(config_path, "r") as f:
                self.config = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            self.config = {}

    def get_hand_info(self, hand_landmarks, handedness):
        label = handedness.classification[0].label
        
        # Anti-Waist Protection: if the hand is hanging pointing to the floor (wrist is higher on screen than middle knuckle),
        # return all 0s instantly so no false clicks are triggered while resting.
        if hand_landmarks.landmark[0].y < hand_landmarks.landmark[9].y:
            return label, [0, 0, 0, 0, 0]
            
        fingers = []
        
        # Foolproof thumb logic: compare distance from Thumb Tip (4) vs Thumb IP (3) to the Index Base (5)
        # If the thumb is extended, the tip is reaching far away from the index base.
        # If folded in a fist or resting, the tip tightly curls toward the index base.
        tip_x, tip_y = hand_landmarks.landmark[4].x, hand_landmarks.landmark[4].y
        ip_x, ip_y = hand_landmarks.landmark[3].x, hand_landmarks.landmark[3].y
        idx_base_x, idx_base_y = hand_landmarks.landmark[5].x, hand_landmarks.landmark[5].y
        
        dist_tip = math.hypot(tip_x - idx_base_x, tip_y - idx_base_y)
        dist_ip = math.hypot(ip_x - idx_base_x, ip_y - idx_base_y)
        
        fingers.append(1 if dist_tip > dist_ip * 1.15 else 0)

        # Index, Middle, Ring, Pinky
        fingers.append(1 if hand_landmarks.landmark[8].y < hand_landmarks.landmark[6].y else 0)
        fingers.append(1 if hand_landmarks.landmark[12].y < hand_landmarks.landmark[10].y else 0)
        fingers.append(1 if hand_landmarks.landmark[16].y < hand_landmarks.landmark[14].y else 0)
        fingers.append(1 if hand_landmarks.landmark[20].y < hand_landmarks.landmark[18].y else 0)
        
        return label, fingers

    def detect_gesture(self, label, current_fingers):
        
        for key, gesture_data in self.config.items():
            if gesture_data["name"] == "None":
                continue # Skip IDLE check for direct matching, we handle IDLE naturally
                
            expected_fingers = gesture_data["fingers"]
            expected_label = gesture_data["label"]
            
            # Check if fingers match
            fingers_match = True
            for i in range(5):
                if expected_fingers[i] == 1:
                    # If finger is required, it must be 1
                    if current_fingers[i] != 1:
                        fingers_match = False
                        break
                else:
                    # If finger is not required, it must be 0 (except thumb which is noisy)
                    if i == 0:
                        pass # Ignore thumb state if it is expected to be 0
                    elif current_fingers[i] != 0:
                        fingers_match = False
                        break
            label_match = (expected_label == "Either" or expected_label == label)
            
            if fingers_match and label_match:
                return gesture_data["name"], gesture_data["action"]
                
        # If no gesture matched, return IDLE
        return "None", self.config.get("None", {}).get("action", "IDLE")

    def execute_action(self, action_name, hand_landmarks):
        curr_time = time.time()
        last_time = self.last_action_times.get(action_name, 0)
        cooldown = self.action_cooldowns.get(action_name, 0.5)

        if action_name == "IDLE":
            pass
        elif action_name == "MOUSE MODE":
            self._do_mouse_mode(hand_landmarks)
            
        elif action_name == "HALT SYSTEM":
            if curr_time - last_time > cooldown:
                print("HALT SYSTEM DETECTED! Stopping Engine...")
                self.stop()
                self.last_action_times[action_name] = curr_time
                return True
                
        elif curr_time - last_time > cooldown:
            self._trigger_keyboard_action(action_name)
            self.last_action_times[action_name] = curr_time
            return True
        return False
        
    def _do_mouse_mode(self, hand_landmarks):
        if hand_landmarks:
            # We map a smaller inner rectangle of the camera feed to the entire screen.
            # This makes the mouse much faster and requires less hand movement.
            margin_x = 0.15  # Reverting to 15% so the tracking box isn't artificially small
            margin_y = 0.15

            norm_x = hand_landmarks.landmark[8].x
            norm_y = hand_landmarks.landmark[8].y

            # Map from [margin_x, 1 - margin_x] to [0, 1]
            mapped_x = (norm_x - margin_x) / (1.0 - 2 * margin_x)
            mapped_y = (norm_y - margin_y) / (1.0 - 2 * margin_y)

            # Clamp between 0 and 1
            mapped_x = max(0.0, min(1.0, mapped_x))
            mapped_y = max(0.0, min(1.0, mapped_y))

            raw_x = mapped_x * self.screen_w
            raw_y = mapped_y * self.screen_h
            
            target_x = (raw_x * (1 - self.smoothing)) + (self.prev_x * self.smoothing)
            target_y = (raw_y * (1 - self.smoothing)) + (self.prev_y * self.smoothing)

            try:
                import ctypes
                ctypes.windll.user32.SetCursorPos(int(target_x), int(target_y))
                self.prev_x, self.prev_y = target_x, target_y
            except Exception:
                pass


    def _trigger_keyboard_action(self, action):
        if action == "SINGLE & DOUBLE CLICK":
            pyautogui.click()
        elif action == "RIGHT CLICK":
            pyautogui.rightClick()
        elif action == "FORWARD":
            pyautogui.press("right")
        elif action == "REWIND":
            pyautogui.press("left")
        elif action == "SPACE (PLAY/PAUSE)":
            # pyautogui.press("playpause") sometimes fails to hook into Windows background SMTC because it lacks the extended key flag.
            # Using ctypes with KEYEVENTF_EXTENDEDKEY forces Windows to intercept it for background media like Chrome/Spotify.
            import ctypes
            VK_MEDIA_PLAY_PAUSE = 0xB3
            KEYEVENTF_EXTENDEDKEY = 0x0001
            KEYEVENTF_KEYUP = 0x0002
            ctypes.windll.user32.keybd_event(VK_MEDIA_PLAY_PAUSE, 0, KEYEVENTF_EXTENDEDKEY, 0)
            ctypes.windll.user32.keybd_event(VK_MEDIA_PLAY_PAUSE, 0, KEYEVENTF_EXTENDEDKEY | KEYEVENTF_KEYUP, 0)
        elif action == "VOLUME_UP":
            pyautogui.press("volumeup")
        elif action == "VOLUME_DOWN":
            pyautogui.press("volumedown")
        elif action == "SPEED_UP":
            pyautogui.hotkey('shift', '>')
        elif action == "SPEED_DOWN":
            pyautogui.hotkey('shift', '<')

    def process_frame(self):
        if not self.running or self.cap is None:
            return None
            
        success, img = self.cap.read()
        if not success:
            return None

        img = cv2.flip(img, 1)
        imgRGB = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        
        self.load_config() # Reload config on every frame to catch UI updates
        results = self.hands.process(imgRGB)

        if results.multi_hand_landmarks:
            for i, hand_landmarks in enumerate(results.multi_hand_landmarks):
                self.mp_draw.draw_landmarks(img, hand_landmarks, self.mp_hands.HAND_CONNECTIONS)
                hand_label, current_fingers = self.get_hand_info(hand_landmarks, results.multi_handedness[i])
                
                gesture_name, action_mapped = self.detect_gesture(hand_label, current_fingers)
                
                self.execute_action(action_mapped, hand_landmarks)
                
                cv2.putText(img, f"Gesture: {gesture_name}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
                cv2.putText(img, f"Action: {action_mapped}", (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 0), 2)
                
                # Show detected fingers for debugging to the user
                finger_str = "".join([str(x) for x in current_fingers])
                cv2.putText(img, f"Fingers: {finger_str} ({hand_label})", (10, 90), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

        return img

    def get_frame_bytes(self):
        # We need to yield *something* so the multipart stream doesn't block indefinitely
        # when the camera is off.
        if not self.running:
            # Yield a black frame if not running
            img = sum([bytearray([0,0,0]) * 640] * 480, bytearray())
            import numpy as np
            frame = np.array(img).reshape((480, 640, 3)).astype(np.uint8)
            ret, buffer = cv2.imencode('.jpg', frame)
            return buffer.tobytes()

        with self.lock:
            frame_bytes = self.current_frame_bytes
            
        if frame_bytes is None:
            time.sleep(0.03)
            return None
            
        time.sleep(0.01) # Small sleep so WSGI thread does not hog CPU
        return frame_bytes

    def _run_loop(self):
        import ctypes
        VK_ESCAPE = 0x1B
        while self.running:
            # Check global ESC key
            if ctypes.windll.user32.GetAsyncKeyState(VK_ESCAPE) & 0x8000:
                print("ESC DETECTED! Halting system natively.")
                self.stop()
                break
                
            frame = self.process_frame()
            if frame is not None:
                ret, buffer = cv2.imencode('.jpg', frame)
                frame_bytes = buffer.tobytes()
                with self.lock:
                    self.current_frame_bytes = frame_bytes
            else:
                time.sleep(0.01)
                
        # Cleanly release the hardware camera sensor natively inside the loop
        if self.cap:
            self.cap.release()
            self.cap = None

    def start(self):
        if not self.running:
            self.cap = cv2.VideoCapture(0)
            self.running = True
            self.thread = threading.Thread(target=self._run_loop, daemon=True)
            self.thread.start()

    def stop(self):
        was_running = self.running
        self.running = False
            
        if was_running:
            import ctypes
            import threading
            def show_msg():
                ctypes.windll.user32.MessageBoxW(0, "Gesture Flow tracking has been completely halted and your camera is offline.", "System Halted", 0x40)
            threading.Thread(target=show_msg, daemon=True).start()

    def release(self):
        self.stop()
