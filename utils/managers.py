import numpy as np
from .iou import compute_iou, find_matched_indice

def xywh2xyxy(xywh):
    x,y,w,h = xywh
    x1,y1,x2,y2 = x,y,x+w,y+h
    return x1,y1,x2,y2

class EventManager():
    def __init__(self):
        self.tracking_person = [] # list of [obj_id,x1,y1,x2,y2,h]
    def get_metadata(self, metadata):
        detected_person = []
        detected_helmet = []
        for obj in metadata:
            if obj[1] == 'person':
                obj_id = obj[2]
                x1,y1,x2,y2 = xywh2xyxy(obj[3:7])
                detected_person.append([obj_id,x1,y1,x2,y2]) #list of [obj_id,x1,y1,x2,y2]
            elif obj[1] == 'helmet':
                x1,y1,x2,y2 = xywh2xyxy(obj[3:7])
                detected_helmet.append([x1,y1,x2,y2]) #list of [x1,y1,x2,y2]
            else:
                raise ValueError("Wrong class id in EventManager")
        detected_person = np.array(detected_person)
        detected_helmet = np.array(detected_helmet)
        # Calculate person x helmet matching indice with iou
        iou = compute_iou(detected_person[:,1:], detected_helmet)
        indice = find_matched_indice(iou)

        # Add a new column for his wearing helmet or not
        r,c = detected_person.shape
        detected_person_info = np.zeros((r,c+1))
        detected_person_info[:,:-1] = detected_person

        # If there is a matching helmet, the person sets 1 on last column.
        for idx in indice:
            detected_person_info[idx[0],-1]=1
        return detected_person_info # array list of [obj_id,x1,y1,x2,y2,helmet]

    def update(self, detected_persons, frame):
        screenshots = []
        for j, p in enumerate(self.tracking_person):
            match = 0 #Is there a detection to match with this person with obj_id?
            for i, det in enumerate(detected_persons):
                if int(det[0]) == p.obj_id: # Yes, It matched
                    match = 1
                    x = p.update(det) # update with detection
                    if x not None:
                        screenshots.append(x)
                    detected_persons = np.delete(detected_persons, i, axis=0) #the used detection is deleted.
                    continue
            if match != 1: # No, any detection does not match this person.
                self.tracking_person.pop(j) #release this person, because It's not tracked anymore.
        for det in detected_persons: # the detections remain, is new trackable person. we register it.
            self.tracking_person.append(Person(det))
        return screenshots

class Person():
    def __init__(self, det, frame):
        obj_id,x1,y1,x2,y2,h = det
        self.obj_id = int(obj_id)
        self.frame_count = 0 #count frames to be watched
        self.image = frame[int(y1):int(y2), int(x1):int(x2)]
    def update(self, det):
        h = int(det[-1])
        self.frame_count+=1
        if h == 1:
            self.frame_count = 0
            return None
        if frame_count == 60:
            return self.image
