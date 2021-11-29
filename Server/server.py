from flask import Flask, request, Response
import jsonpickle
import numpy as np
import cv2
import utils.face_rec as fr
import argparse
from config.config import SERVER_STATIC_IP
import pickle
import logging
import codecs


ap = argparse.ArgumentParser()
ap.add_argument("-p", "--port", required=True, default=5000, type=int,
                help="path to input dataset")
args = vars(ap.parse_args())


logger = logging.getLogger('recognition_thread_at_port_' + str(args['port']))
logger.setLevel(logging.INFO)
file_handler = logging.FileHandler('Logs/log_recognition_thread_at_port_' + str(args['port']) + '.txt')
formatter = logging.Formatter('%(asctime)s : %(levelname)s : %(name)s : %(message)s')
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

recognizer = fr.FaceRecognizer(logger)

# Initialize the Flask application
app = Flask(__name__)


# route http posts to this method
@app.route('/api/face_recognize', methods=['POST'])
def recognize_request():
    recogn = recognizer
    r = request
    # convert string of image data to uint8
    # nparr = np.fromstring(r.data, np.uint8)
    nparr = np.frombuffer(r.data, np.uint8)
    # decode image
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

    # do some fancy processing here....
    persons = []
    msg = codecs.encode(pickle.dumps(persons), "base64").decode()
    (res, persons, unknowns_cnt) = recogn.recognize_face(img)
    if res:
        msg = codecs.encode(pickle.dumps((persons, unknowns_cnt)), "base64").decode()
    response = {'message': msg}

    # encode response using jsonpickle
    response_pickled = jsonpickle.encode(response)

    return Response(response=response_pickled, status=200, mimetype="application/json")


@app.route('/api/downloadID', methods=['POST'])
def download_request():
    r = request
    recogn = recognizer
    msg = codecs.encode(pickle.dumps(recogn.known_persons), "base64").decode()
    response = {'message': msg}
    response_pickled = jsonpickle.encode(response)
    return Response(response=response_pickled, status=200, mimetype="application/json")


# start flask app
app.run(host=SERVER_STATIC_IP, port=args['port'])
