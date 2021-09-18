from __future__ import print_function
import requests
import json
import cv2
import time
import argparse
import pickle
import codecs


ap = argparse.ArgumentParser()
ap.add_argument("-p", "--port", required=True, default=5000, type=int,
                help="path to input dataset")
args = vars(ap.parse_args())


addr = 'http://178.154.195.107:{}'.format(args['port']) #'http://178.154.195.107:{}'.format(args['port'])
test_url = addr + '/api/face_recognize'
download_url = addr + '/api/downloadID'

# prepare headers for http request
content_type = 'image/jpeg'
headers = {'content-type': content_type}

loaded = False
while not loaded:
    try:
        response = requests.post(download_url, data='req')
        known_persons = pickle.loads(codecs.decode(json.loads(response.text)['message'].encode(), "base64"))
        print(known_persons)
        users = [*known_persons]
        loaded = True
    except Exception as e:
        pass
cv2.imshow('a', known_persons[users[0]]["face_ID"])
cv2.waitKey(1000)


img = cv2.imread('test.jpg')
# encode image as jpeg
for i in range(100):
    t0 = time.time()
    _, img_encoded = cv2.imencode('.jpg', img)
    # send http request with image and receive response
    response = requests.post(test_url, data=img_encoded.tostring(), headers=headers)
    print('{} msec'.format((time.time() - t0)*1e3))
    # decode response
    (persons, uknowns_cnt) = pickle.loads(codecs.decode(json.loads(response.text)['message'].encode(), "base64"))
    print(persons)

# expected output: {u'message': u'image received. size=124x124'}
