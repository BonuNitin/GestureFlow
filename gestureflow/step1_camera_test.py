import cv2

cap = cv2.VideoCapture(0)

while True:
    ret, frame = cap.read()
    if not ret:
        print("Camera not working")
        break

    # 1 = flip horizontally (mirror effect)
    # 0 = flip vertically
    # -1 = flip both
    frame = cv2.flip(frame, 1)

    cv2.imshow("My First CV Program - Press Q", frame)
    
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()
