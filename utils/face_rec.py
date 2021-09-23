import cv2
import pickle
from datetime import datetime, timedelta
import os
import logging
import numpy as np
import face_recognition
import time


logger = logging.getLogger('recognition_thread')
logger.setLevel(logging.INFO)
file_handler = logging.FileHandler('Logs/log_recognition_thread.txt')
formatter = logging.Formatter('%(asctime)s : %(levelname)s : %(name)s : %(message)s')
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)


MODEL_PROTOPATH = 'model/deploy.prototxt'
MODEL_MODELPATH = 'model/res10_300x300_ssd_iter_140000.caffemodel'
KNN_MODELPATH = 'model/trained_knn_model.clf'
FACE_DETECTOR_CONFIDENSE = 0.5
FACE_RECOGNITION_THRESHOLD = 0.5


def prepare_img(img):
    # image = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    image = cv2.resize(img, (300, 300))
    return image


def load_known_faces():
    known_persons = {}
    logger.info('Loaded model and classifier')
    for class_dir in os.listdir('KnownFaces/'):
        if class_dir == 'Unknown':
            continue
        logger.info("{} - loaded ID".format(class_dir))
        face_image = cv2.imread(os.path.join("KnownFaces/", class_dir, "face_ID.jpg"))
        face_image = cv2.resize(face_image, (360, 480))
        with open(os.path.join("KnownFaces/", class_dir, "cardID.txt"), "r") as f:
            ID = int(f.read())
        known_persons[class_dir] = {
            "face_ID": face_image,
            "name": class_dir,
            "ID": ID
        }
    return known_persons


def calc_encodings(img, boxes):
    t0 = time.time()
    enc = face_recognition.face_encodings(img, known_face_locations=boxes, model='small')
    t1 = time.time()
    print('Face encodings: {}ms'.format((t1-t0)*1e3))
    return enc


class FaceRecognizer:
    def __init__(self):
        self.protopath = MODEL_PROTOPATH
        self.modelpath = MODEL_MODELPATH
        self.detector = cv2.dnn.readNetFromCaffe(self.protopath, self.modelpath)
        self.detections = None
        self.boxes = None
        self.result = False
        self.imageBlob = None
        self.persons_data = []
        self.image = None
        logger.info('Models loaded')

        with open(KNN_MODELPATH, 'rb') as f:
            self.knn_clf = pickle.load(f)
        logger.info('KNN predictor loaded')

        self.known_persons = load_known_faces()
        logger.info('Faces loaded')

    def detect_faces(self, image):
        t0 = time.time()
        self.result = False
        self.imageBlob = cv2.dnn.blobFromImage(image, 1.0, (300, 300), (104.0, 177.0, 123.0), swapRB=False, crop=False)
        self.detector.setInput(self.imageBlob)
        self.detections = self.detector.forward()
        if self.detections.shape[2] > 0:
            self.result = True
        t1 = time.time()
        print('Face detect: {}ms'.format((t1-t0)*1e3))
        return self.result

    def recognize_face(self, img):
        self.result = False
        self.persons_data = []
        self.image = prepare_img(img)
        (h, w) = self.image.shape[:2]
        self.boxes = []
        if self.detect_faces(self.image):
            for i in range(0, self.detections.shape[2]):
                self.confidence = self.detections[0, 0, i, 2]
                if self.confidence > FACE_DETECTOR_CONFIDENSE:
                    box = self.detections[0, 0, i, 3:7] * np.array([w, h, w, h])
                    (startX, startY, endX, endY) = box.astype("int")
                    x0 = int(startX + 0 * w / 10)
                    y0 = int(startY + 0.2 * h / 4)
                    x1 = int(endX - 0 * w / 10)
                    y1 = int(endY)
                    self.boxes.append((y0, x1, y1, x0))
        unknowns_cnt = len(self.boxes)
        if self.boxes:
            self.result = True
            self.enc = calc_encodings(self.image, self.boxes)
            # print(self.detections.shape[2])
            self.closest_distances = self.knn_clf.kneighbors(self.enc, n_neighbors=1)
            self.are_matches = [self.closest_distances[0][i][0] <= FACE_RECOGNITION_THRESHOLD
                                for i in range(len(self.boxes))]
            for predicted_user, face_location, found in zip(self.knn_clf.predict(self.enc), self.boxes,
                                                            self.are_matches):
                if found:
                    unknowns_cnt -= 1
                    person_found = self.known_persons.get(predicted_user)
                    if person_found is not None:
                        self.persons_data.append((person_found["name"],
                                                  person_found["ID"],
                                                  face_location))
        print(self.persons_data)
        return self.result, self.persons_data, unknowns_cnt
