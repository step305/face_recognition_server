from utils import utils
from config.config import SERVER_PUBLIC_IP, DOOR_PORT
import logging
import requests
import json
import pickle
import codecs
import cv2
from datetime import datetime, timedelta
import time

FPS_COUNTER_MAX = 100
PERSON_FALSE_DETECT_TIME_INTERVAL = 3
PERSON_ROBUST_DETECT_COUNT = 3


def recognition_thread(frame_buffer, person_data_queue, person_detected_event, stop_event):
    logger = utils.logger_config('recognition_thread')

    server_recognition_address = 'http://{}:{}'.format(SERVER_PUBLIC_IP, DOOR_PORT)

    recognizer_url = server_recognition_address + '/api/face_recognize'
    downloader_url = server_recognition_address + '/api/downloadID'

    content_type = 'image/jpeg'
    headers = {'content-type': content_type}

    loaded = False
    while not loaded:
        try:
            response = requests.post(downloader_url, data='req')
            known_persons = pickle.loads(codecs.decode(json.loads(response.text)['message'].encode(), "base64"))
            user_names = [*known_persons]
            logger.info('Downloaded from server: {}'.format(user_names))
            loaded = True
        except Exception as e:
            logger.error('Can not download persons data from server. Trying again.')
            logging.exception("Trying")
            pass

    for user in user_names:
        logger.info("{} loaded ID".format(user))
        face_image = known_persons[user]["face_ID"]
        face_image = cv2.resize(face_image, (360, 480))
        ID = int(known_persons[user]["ID"])
        known_persons[user] = {
            "first_seen": datetime(1, 1, 1),
            "name": user,
            "first_seen_this_interaction": datetime(1, 1, 1),
            "last_seen": datetime(1, 1, 1),
            "seen_frames": 0,
            "face_image": face_image,
            "save_cnt": 0,
            "ID": ID
        }

    fps_cnt = 0
    t0 = time.time()
    logger.info('Data loaded')

    while True:
        try:
            if stop_event.is_set():
                logger.info('Done!')
                break
            if frame_buffer.empty():
                time.sleep(0.01)
                continue

            img = frame_buffer.get()
            rgb_img = img

            try:
                _, img_encoded = cv2.imencode('.jpg', rgb_img)
                response = requests.post(recognizer_url, data=img_encoded.tostring(), headers=headers)
                (persons, unknowns_cnt) = pickle.loads(
                    codecs.decode(json.loads(response.text)['message'].encode(), "base64"))
            except Exception as e:
                persons = []
                unknowns_cnt = 0
                logger.warning('Failed to send frame to server.')

            if (unknowns_cnt > 0) | bool(persons):
                person_detected_event.set()
                logger.info('Person near the door')
            else:
                person_detected_event.clear()

            if persons:
                logger.info('Found: {}'.format(persons))
                for person_pack in persons:
                    person = person_pack[0]
                    person_found = known_persons.get(person)
                    if person_found:
                        known_persons[person]["last_seen"] = datetime.now()

                        logger.info('Info: {} was on {} - {} times'.format(
                            person,
                            known_persons[person]["last_seen"],
                            known_persons[person]["seen_frames"]))

                        if known_persons[person]["first_seen"] != datetime(1, 1, 1):
                            known_persons[person]["seen_frames"] += 1
                            if datetime.now() - known_persons[person]["first_seen_this_interaction"] > \
                                    timedelta(minutes=5):
                                known_persons[person]["first_seen_this_interaction"] = datetime.now()
                                known_persons[person]["seen_frames"] = 0
                        else:
                            known_persons[person]["first_seen"] = datetime.now()
                            known_persons[person]["first_seen_this_interaction"] = datetime.now()

            persons_data = []
            for user in known_persons:
                if datetime.now() - known_persons[user]["last_seen"] > \
                        timedelta(seconds=PERSON_FALSE_DETECT_TIME_INTERVAL):
                    known_persons[user]["seen_frames"] = 0
                if known_persons[user]["seen_frames"] > PERSON_ROBUST_DETECT_COUNT:
                    persons_data.append((known_persons[user]["name"],
                                         known_persons[user]["ID"],
                                         known_persons[user]["last_seen"]))

            if len(persons_data) > 0:
                if person_data_queue.empty():
                    logger.info('Persons recognized near the door')
                    person_data_queue.put(persons_data)

            if fps_cnt == FPS_COUNTER_MAX:
                logger.info('Recognition cycle done in {}ms (average)'.format((time.time() - t0) * 1000 / fps_cnt))
                t0 = time.time()
                fps_cnt = 0
            else:
                fps_cnt += 1

        except Exception as e:
            logger.error('Exception in while loop')
            logging.exception("Error")
