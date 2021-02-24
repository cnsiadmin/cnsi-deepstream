import requests, json
import time
import cv2
import base64

def send_no_helmet_event(url, screenshot):

    #RTSPINPUT_URI = "rtsp://admin:Tldosdptmdk2@223.171.56.203:554/profile2/media.smp"
    # cap = cv2.VideoCapture(RTSPINPUT_URI)
    # ret, frame = cap.read()
    # converted = cv2.imencode('.jpg', frame)[1].tostring()
    jpgImg = cv2.imencode('.jpg', screenshot)[1].tostring()
    converted = base64.b64encode(jpgImg).decode('utf-8')
    #print(converted)
    #converted = converted.decode('utf8')
    #print(converted)
    #cv2.imwrite("rtsp_snapshot_test.jpg", frame)
    #'Content-Type' : 'application/json',
    header = {
    'Content-Type' : 'application/json',
    "clientType" : "SYSTEM",
    "authToken" : "1234!@#$abcd",
    "command" : "InputEventVideoAnalysis"
    }

    body = {
    "siteId" : "0001" ,
    "cameraId" : "0000001",
    "eventType" : "1",
    "screenshotImage" : converted,
    "time" : time.strftime('%Y%m%d%H24%M%S', time.localtime())
    }

    body = json.dumps(body)
    #print(header)
    #print(body)
    x = requests.post(url, headers=header, data=body, timeout=10)

    print(x.text.encode('utf8'))
