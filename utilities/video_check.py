import cv2

# Check for available cameras
index = 0
arr = []
while True:
    cap = cv2.VideoCapture(index)
    if not cap.read()[0]:
        break
    else:
        arr.append(index)
    cap.release()
    index += 1

print("Number of video capable devices connected to the system: ", len(arr))
if len(arr) > 0:
    print("Device IDs: ")
    for i in arr:
        print(i)