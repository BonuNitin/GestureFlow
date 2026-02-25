
import cv2
import mediapipe as mp
import pyautogui
import time

# Optimization
pyautogui.PAUSE = 0
pyautogui.FAILSAFE = False

cap = cv2.VideoCapture(0)
screen_w, screen_h = pyautogui.size()

mp_hands = mp.solutions.hands
hands = mp_hands.Hands(
    max_num_hands=1, 
    min_detection_confidence=0.8, 
    min_tracking_confidence=0.8
)
mp_draw = mp.solutions.drawing_utils

# Cooldowns
last_click_time = 0
last_double_click_time = 0
last_ff_time = 0
last_rw_time = 0

click_cooldown = 0.5
double_click_cooldown = 0.8
move_cooldown = 1.0

def get_hand_info(hand_landmarks, handedness):
    label = handedness.classification[0].label 
    fingers = []
    
    # Thumb logic
    if label == "Right":
        fingers.append(hand_landmarks.landmark[4].x > hand_landmarks.landmark[5].x)
    else:
        fingers.append(hand_landmarks.landmark[4].x < hand_landmarks.landmark[5].x)

    # Index, Middle, Ring, Pinky
    fingers.append(hand_landmarks.landmark[8].y < hand_landmarks.landmark[6].y)
    fingers.append(hand_landmarks.landmark[12].y < hand_landmarks.landmark[10].y)
    fingers.append(hand_landmarks.landmark[16].y < hand_landmarks.landmark[14].y)
    fingers.append(hand_landmarks.landmark[20].y < hand_landmarks.landmark[18].y)
    
    return label, fingers

while True:
    success, img = cap.read()
    if not success:
        break

    img = cv2.flip(img, 1)
    imgRGB = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    results = hands.process(imgRGB)

    if results.multi_hand_landmarks:
        for i, hand_landmarks in enumerate(results.multi_hand_landmarks):
            mp_draw.draw_landmarks(img, hand_landmarks, mp_hands.HAND_CONNECTIONS)
            hand_label, f = get_hand_info(hand_landmarks, results.multi_handedness[i])
            curr_time = time.time()

            # 1. FIST -> IDLE MODE
            if not any(f):
                cv2.putText(img, "IDLE", (50, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)

            # 2. FOUR FINGERS UP (NO THUMB) -> SINGLE CLICK
            elif not f[0] and all(f[1:]):
                if curr_time - last_click_time > click_cooldown:
                    pyautogui.click()
                    print("🖱️ Single Click")
                    last_click_time = curr_time
                cv2.putText(img, "SINGLE CLICK", (50, 100), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)

            # 3. THUMB ONLY -> DOUBLE CLICK
            elif f[0] and not any(f[1:]):
                if curr_time - last_double_click_time > double_click_cooldown:
                    pyautogui.doubleClick()
                    print("🖱️🖱️ Double Click")
                    last_double_click_time = curr_time
                cv2.putText(img, "DOUBLE CLICK", (50, 100), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 0), 2)

            # 4. RIGHT VICTORY -> FAST FORWARD
            elif hand_label == "Right" and f[1] and f[2] and not f[3] and not f[4]:
                if curr_time - last_ff_time > move_cooldown:
                    pyautogui.press("right")
                    last_ff_time = curr_time
                cv2.putText(img, "FF >>", (50, 150), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 255), 2)

            # 5. LEFT VICTORY -> REWIND
            elif hand_label == "Left" and f[1] and f[2] and not f[3] and not f[4]:
                if curr_time - last_rw_time > move_cooldown:
                    pyautogui.press("left")
                    last_rw_time = curr_time
                cv2.putText(img, "<< REWIND", (50, 150), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 255), 2)

            # 6. INDEX ONLY -> MOUSE MOVEMENT
            elif f[1] and not any([f[2], f[3], f[4]]):
                target_x = int(hand_landmarks.landmark[8].x * screen_w)
                target_y = int(hand_landmarks.landmark[8].y * screen_h)
                pyautogui.moveTo(target_x, target_y, _pause=False)
                cv2.putText(img, "MOUSE MODE", (50, 200), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)

    cv2.imshow("AuraTrack Mouse Pro", img)
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()