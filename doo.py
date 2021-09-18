#!/usr/bin/env python3
from __future__ import print_function

import cv2
from multiprocessing import Process
import multiprocessing
import time
from time import sleep
import math
import os
import os.path
import numpy as np
from datetime import datetime, timedelta
import serial
from subprocess import Popen, PIPE
import fcntl
from config.config import SERVER_PUBLIC_IP, DOOR_PORT


def reset_door_locker():
    # /etc/udev/rules.d/99-usb-serial.rules
    # SUBSYSTEM=="tty", ATTRS{idVendor}=="1234", ATTRS{idProduct}=="5678", SYMLINK+="ttyACM0"
    # sudo udevadm trigger
    driver = "ST-LINK"
    print("resetting driver:", driver)
    USBDEVFS_RESET = 21780
    result = 0
    try:
        lsusb_out = Popen("lsusb | grep -i ST-LINK", shell=True, bufsize=64, stdin=PIPE, stdout=PIPE,
                          close_fds=True).stdout.read().strip().split()
        bus = str(lsusb_out[1])
        bus = bus[2:-1]
        device = str(lsusb_out[3][:-1])
        device = device[2:-1]
        f = open("/dev/bus/usb/%s/%s" % (bus, device), 'w', os.O_WRONLY)
        fcntl.ioctl(f, USBDEVFS_RESET, 0)
    except Exception as msg:
        result = -1
    return result


def transform_frame(temp_image, empty_frame):
    pre_frame = empty_frame
    angle = 110
    (he, we, c) = empty_frame.shape
    empty_frame_yc = int(he / 2)
    empty_frame_xc = int(we / 2)
    (h, w, c) = temp_image.shape
    half_h = int(h / 2)
    half_w = int(w / 2)
    pre_frame[
        empty_frame_yc - half_h:
        empty_frame_yc + half_h,
        empty_frame_xc - half_w:
        empty_frame_xc + half_w, :
    ] = temp_image
    transformation_matrix = cv2.getRotationMatrix2D((empty_frame_xc, empty_frame_yc), angle, 1)
    transformed_image = cv2.warpAffine(pre_frame, transformation_matrix, (we, he))
    return transformed_image


def cam_thread(frame_buffer, LEDevent, stop):
    import logging
    logger = logging.getLogger('camera_thread')
    logger.setLevel(logging.INFO)
    file_handler = logging.FileHandler('/home/step305/Door/Faces/LogFaces/log_door_camera_thread.txt')
    formatter = logging.Formatter('%(asctime)s : %(levelname)s : %(name)s : %(message)s')
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    door_ID = 0
    #    capture_pipeline = (
    #        'v4l2src device=/dev/video0 do-timestamp=true ! '
    #        'video/x-raw, width=1280, height=720, framerate=30/1, format=NV12 ! '
    #        'videoconvert ! video/x-raw, format=BGR ! appsink'
    #    )

    capture_pipeline = (
        'v4l2src device=/dev/video0 ! '
        'image/jpeg, width=1280, height=720, framerate=30/1, format=MJPG ! '
        'jpegparse ! jpegdec ! videoconvert ! video/x-raw, format=BGR ! appsink'
    )
    cam = cv2.VideoCapture(capture_pipeline, cv2.CAP_GSTREAMER)
    writer_pipeline = (
        'appsrc ! videoconvert ! video/x-raw, format=NV12 ! '
        'nvvidconv ! video/x-raw(memory:NVMM), width=1280, height=720, format=NV12 ! '
        'nvv4l2h265enc bitrate=8000000 maxperf-enable=1 '
        'preset-level=1 insert-sps-pps=1 profile=1 iframeinterval=1 ! '
        'h265parse ! rtph265pay ! udpsink host=127.0.0.1 '
        'port=5000 async=0 sync=0'
    )
    udp_writer = cv2.VideoWriter(writer_pipeline, 0, 30, (1280, 720))
    mask1 = cv2.imread('mask1_2.jpg', 0)
    Logo = cv2.imread('logo2.jpg')
    screen_saver = cv2.VideoCapture('a9.mp4')
    print(datetime.now(), ':', 'Loaded main')
    logger.info('Loaded media')

    final_w = 1680
    final_h = 1050
    final_frame_cam_frame_x0 = 0
    final_frame_delta_minus = 86
    black_frame = np.zeros((final_h, final_h, 3), np.uint8)
    final_frame = np.zeros((final_h, final_w, 3), np.uint8)
    aspect_x = 16
    aspect_y = 10
    diag = int(math.sqrt(aspect_x ** 2 + aspect_y ** 2))
    step = int(final_h / diag) - 1
    cam_resize_x = step * aspect_x
    cam_resize_y = step * aspect_y

    time.sleep(10)
    #    os.system('pacmd set-default-sink
    #    "alsa_output.usb-Creative_Technology_Ltd_Sound_Blaster_Play__3_00104826-00.analog-stereo"')
    #    os.system('pacmd set-sink-volume 0 0x5000')
    os.system('xrandr -o normal')
    os.system('v4l2-ctl -d 0 -c zoom_absolute=160')
    os.system('v4l2-ctl -d 0 -c pan_absolute=0')
    os.system('v4l2-ctl -d 0 -c tilt_absolute=0')
    os.system('v4l2-ctl -d 0 -c brightness=140')
    os.system('./RTSPserver &')
    print(datetime.now(), ':', 'Loaded main N3')
    logger.info('camera config done')

    window_name = 'Video'
    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
    cv2.setWindowProperty(window_name, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
    t0 = time.monotonic()
    frames_cnt = 0
    skip_frames_MAX = 2
    skip_frames = skip_frames_MAX
    time2screenoff = time.time()
    saver_frame_counter = 0
    while True:
        try:
            ret, frame = cam.read()
            if not ret:
                continue
            if frame_buffer.empty():
                if skip_frames == 0:
                    fr = cv2.resize(frame, (int(frame.shape[1] * 0.5), int(frame.shape[0] * 0.5)))
                    frame_buffer.put((door_ID, fr))
                    skip_frames = skip_frames_MAX
                else:
                    skip_frames -= 1
            udp_writer.write(frame)
            if LEDevent.is_set():
                # LEDevent.clear()
                time2screenoff = now_time + 4
                logger.info('person in frame!')
            now_time = time.time()
            if time2screenoff < (now_time + 1):
                rr, frame_saver = screen_saver.read()
                saver_frame_counter += 1
                if saver_frame_counter == screen_saver.get(cv2.CAP_PROP_FRAME_COUNT):
                    saver_frame_counter = 0  # Or whatever as long as it is the same as next line
                    screen_saver.set(cv2.CAP_PROP_POS_FRAMES, 0)
                time.sleep(1 / 50)
                frame = frame_saver
            rot_frame = cv2.resize(frame, (cam_resize_x, cam_resize_y))
            rot_frame = cv2.flip(rot_frame, 1)
            rot_frame = transform_frame(rot_frame, black_frame)
            final_frame[
                0:final_h,
                final_frame_cam_frame_x0:final_frame_cam_frame_x0 + final_h - final_frame_delta_minus
            ] = rot_frame[:, final_frame_delta_minus:]

            final_frame = cv2.bitwise_and(final_frame, final_frame, mask=mask1)
            final_frame = cv2.bitwise_or(final_frame, Logo)
            final_frame = cv2.flip(final_frame, -1)
            cv2.imshow(window_name, final_frame)
            frames_cnt += 1
            if frames_cnt >= 100:
                t1 = time.monotonic()
                print(datetime.now(), ':', 'FPS={:.1f}'.format(frames_cnt / (t1 - t0)))
                logger.info('FPS = {}'.format(frames_cnt / (t1 - t0)))
                frames_cnt = 0
                t0 = t1
            if (cv2.waitKey(1) & 0xFF) == ord('q'):
                stop.set()
                break
            if stop.is_set():
                break
        except Exception as e:
            logger.error('exception in while loop')
    cam.release()
    screen_saver.release()
    logger.info('done!')
    os.system('pkill RTSPserver')
    cv2.destroyAllWindows()


def cam_back_thread(frame_buffer, stop):
    door_ID = 1
    capture_pipeline = (
        'v4l2src device=/dev/video2 do-timestamp=true ! '
        'video/x-raw, width=1280, height=720, framerate=30/1, format=NV12 ! '
        'videoconvert ! video/x-raw, format=BGR ! appsink'
    )
    rtsp_pipeline = (
        'rtspsrc location=rtsp://admin:12345@10.0.0.200:554 latency=0 ! '
        'rtph264depay ! h264parse ! omxh264dec ! nvvidconv ! '
        'video/x-raw, format=BGRx, width=1280, height=720 ! '
        'videoconvert ! video/x-raw, format=BGR ! appsink'
    )
    # gstreamer_pipeline = (
    #   'v4l2src device=/dev/video2 ! '
    #   'image/jpeg, width=1280, height=720, framerate=30/1, format=MJPG ! '
    #   'jpegparse ! jpegdec ! videoconvert ! video/x-raw, format=BGR ! appsink'
    # )

    writer_pipeline = (
        'appsrc ! videoconvert ! video/x-raw, format=NV12 ! '
        'nvvidconv ! video/x-raw(memory:NVMM), width=1280, height=720, format=NV12 ! '
        'nvv4l2h265enc bitrate=8000000 maxperf-enable=1 '
        'preset-level=1 insert-sps-pps=1 profile=1 iframeinterval=1 ! '
        'h265parse ! rtph265pay ! udpsink host=127.0.0.1 '
        'port=5001 async=0 sync=0'
    )
    udp_writer = cv2.VideoWriter(writer_pipeline, 0, 30, (1280, 720))

    time.sleep(20)
    # cam = cv2.VideoCapture(capture_pipeline, cv2.CAP_GSTREAMER)
    cam = cv2.VideoCapture(rtsp_pipeline, cv2.CAP_GSTREAMER)
    #    os.system('xrandr -o normal')
    #    os.system('v4l2-ctl -d 2 -c zoom_absolute=160')
    #    os.system('v4l2-ctl -d 2 -c pan_absolute=0')
    #    os.system('v4l2-ctl -d 2 -c tilt_absolute=0')
    #    os.system('v4l2-ctl -d 2 -c brightness=140')
    os.system('./RTSPserver_back &')

    t0 = time.monotonic()
    frames_cnt = 0
    skip_frames_MAX = 2
    skip_frames = skip_frames_MAX
    while True:
        ret, frame = cam.read()
        if not ret:
            continue
        if frame_buffer.empty():
            if skip_frames == 0:
                fr = cv2.resize(frame, (int(frame.shape[1] * 0.5), int(frame.shape[0] * 0.5)))
                frame_buffer.put((door_ID, fr))
                skip_frames = skip_frames_MAX
            else:
                skip_frames -= 1
        udp_writer.write(frame)
        frames_cnt += 1
        if frames_cnt >= 15:
            t1 = time.monotonic()
            print(datetime.now(), ':', 'back: FPS={:.1f}'.format(frames_cnt / (t1 - t0)))
            frames_cnt = 0
            t0 = t1
        if stop.is_set():
            break
    cam.release()
    os.system('pkill RTSPserver_back')


def door_lock_thread(personID, LEDevent1, LEDevent2, disp_off_event, stop):
    import logging
    logger = logging.getLogger('door_lock_thread')
    logger.setLevel(logging.INFO)
    file_handler = logging.FileHandler('/home/step305/Door/Faces/LogFaces/log_door_door_lock_thread.txt')
    formatter = logging.Formatter('%(asctime)s : %(levelname)s : %(name)s : %(message)s')
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    # switch_port = serial.Serial(port='/dev/ttyACM0', baudrate=9600)

    snd_allowed = ('gst-launch-1.0 filesrc location=allowed.ogg ! oggdemux ! '
                   'vorbisdec ! audioconvert ! audioresample ! pulsesink &')
    time2LED1off = time.time()
    time2LED2off = time.time()
    time2next_door_open = time.time()
    logger.info('started')
    while True:
        try:
            wiegand_port = serial.Serial(port='/dev/ttyACM0', baudrate=9600, timeout=1.0, write_timeout=1)
            if stop.is_set():
                logger.info('Done!')
                break
            now_time = time.time()
            if LEDevent1.is_set():
                # LEDevent1.clear()
                disp_off_event.set()
                time2LED1off = now_time + 3
                # switch_port.write(bytes([129])
                str_cmd = "$1: card=0 :command=2\n"
                wiegand_port.write(str_cmd.encode('ascii'))
                time.sleep(0.03)
                str_cmd = "$1: card=0 :command=2\n"
                wiegand_port.write(str_cmd.encode('ascii'))
                time.sleep(0.03)
                logger.info('Person in frame door 1')
            if LEDevent2.is_set():
                # LEDevent2.clear()
                time2LED2off = now_time + 3
                # switch_port.write(bytes([131]))
                str_cmd = "$3: card=0 :command=2\n"
                wiegand_port.write(str_cmd.encode('ascii'))
                time.sleep(0.03)
                str_cmd = "$3: card=0 :command=2\n"
                wiegand_port.write(str_cmd.encode('ascii'))
                time.sleep(0.03)
                logger.info('Person in frame door 1')
            if time2LED1off < (now_time + 1):
                disp_off_event.clear()
                # switch_port.write(bytes([1]))
                str_cmd = "$1: card=0 :command=3\n"
                wiegand_port.write(str_cmd.encode('ascii'))
                time.sleep(0.03)
                str_cmd = "$1: card=0 :command=3\n"
                wiegand_port.write(str_cmd.encode('ascii'))
                time.sleep(0.03)
            if time2LED2off < (now_time + 1):
                # switch_port.write(bytes([3]))
                str_cmd = "$3: card=0 :command=3\n"
                wiegand_port.write(str_cmd.encode('ascii'))
                time.sleep(0.03)
                str_cmd = "$3: card=0 :command=3\n"
                wiegand_port.write(str_cmd.encode('ascii'))
                time.sleep(0.03)
            if personID.empty():
                sleep(0.01)
                continue
            door_id, pers_id_data = personID.get()
            if len(pers_id_data) > 0:
                nowDate = datetime.now()
                log_filepath = 'Faces/LogFaces/log_{}_{}_{}.txt'.format(nowDate.day, nowDate.month, nowDate.year)
                user_name, user_id, user_timestamp = pers_id_data[0]
                logger.info('Person near the door')
                if time2next_door_open < (now_time + 1):

                    str_cmd = "$0: card={} :command=5\n".format(user_id)
                    wiegand_port.write(str_cmd.encode('ascii'))
                    time.sleep(0.1)

                    str_cmd = "$2: card=0 :command=2\n"
                    wiegand_port.write(str_cmd.encode('ascii'))
                    time.sleep(0.03)

                    str_cmd = "$0: card=0 :command=2\n"
                    wiegand_port.write(str_cmd.encode('ascii'))
                    time.sleep(0.03)

                    print(datetime.now(), ':', 'Unlock for {}'.format(user_name))
                    logger.info('Unlock door for {}'.format(user_name))
                    os.system(snd_allowed)
                    sleep(1)

                    # switch_port.write(bytes([0]))
                    str_cmd = "$0: card=0 :command=3\n"
                    wiegand_port.write(str_cmd.encode('ascii'))
                    time.sleep(0.03)

                    str_cmd = "$2: card=0 :command=3\n"
                    wiegand_port.write(str_cmd.encode('ascii'))
                    time.sleep(0.03)

                    print(datetime.now(), ':', 'locked')
                    logger.info('Locked door')
                    time2next_door_open = time.time() + 5

                    log_file = open(log_filepath, 'a')
                    log_file.write("{}.{}.{} Users detected at door #{}:\n".format(nowDate.day,
                                                                                   nowDate.month,
                                                                                   nowDate.year,
                                                                                   door_id))
                    for id_data in pers_id_data:
                        user_name, user_id, user_timestamp = id_data
                        log_file.write("{}:{}:{} - {} (#{})\n".format(user_timestamp.hour,
                                                                      user_timestamp.minute,
                                                                      user_timestamp.second,
                                                                      user_name,
                                                                      user_id))
                    log_file.close()
            #    switch_port.close()
            wiegand_port.close()
        except Exception as e:
            logger.error('Exception in while loop')
            res_reset = reset_door_locker()
            if res_reset == 0:
                logger.info('USB reset done!')
            else:
                logger.error('USB reset failed!')


def recognition_thread(frame_buffer, person_ID, LEDevent1, LEDevent2, stop):
    import requests
    import json
    import pickle
    import codecs

    import logging
    logger = logging.getLogger('recognition_thread')
    logger.setLevel(logging.INFO)
    file_handler = logging.FileHandler('/home/step305/Door/Faces/LogFaces/log_door_recognition_thread.txt')
    formatter = logging.Formatter('%(asctime)s : %(levelname)s : %(name)s : %(message)s')
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    addr = 'http://{}:{}'.format(SERVER_PUBLIC_IP, DOOR_PORT)
    test_url = addr + '/api/face_recognize'
    download_url = addr + '/api/downloadID'
    # prepare headers for http request
    content_type = 'image/jpeg'
    headers = {'content-type': content_type}
    response = requests.post(download_url, data='req')
    known_persons = pickle.loads(codecs.decode(json.loads(response.text)['message'].encode(), "base64"))
    print(known_persons)
    user_names = [*known_persons]

    logger.info('Loaded model and classifier')

    for user in user_names:
        print(datetime.now(), ':', user + " loaded ID")
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
    FPS = 0
    FPSMAX = 100
    t0 = time.time()
    logger.info('Faces loaded')

    while True:
        try:
            if stop.is_set():
                logger.info('Done!')
                break
            if frame_buffer.empty():
                sleep(0.01)
                continue
            door_id, img = frame_buffer.get()
            rgb_img = img[:, :, ::-1]

            _, img_encoded = cv2.imencode('.jpg', rgb_img)
            response = requests.post(test_url, data=img_encoded.tostring(), headers=headers)
            (persons, unknowns_cnt) = pickle.loads(
                codecs.decode(json.loads(response.text)['message'].encode(), "base64"))
            if (unknowns_cnt > 0) | persons:
                if door_id == 0:
                    LEDevent1.set()
                    logger.info('Person near the door')
                elif door_id == 1:
                    LEDevent2.set()
                    logger.info('Person near the door')
            else:
                if door_id == 0:
                    LEDevent1.clear()
                elif door_id == 1:
                    LEDevent2.clear()

            if persons:
                for person in persons:
                    person_found = known_persons.get(person)
                    if person_found:
                        known_persons[person]["last_seen"] = datetime.now()
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
                if datetime.now() - known_persons[user]["last_seen"] > timedelta(seconds=2):
                    known_persons[user]["seen_frames"] = 0
                if known_persons[user]["seen_frames"] > 3:
                    persons_data.append((known_persons[user]["name"],
                                         known_persons[user]["ID"],
                                         known_persons[user]["last_seen"]))
            if len(persons_data) > 0:
                if person_ID.empty():
                    logger.info('Persons recognized near the door')
                    person_ID.put((door_id, persons_data))
            if FPS == FPSMAX:
                print(datetime.now(), ':',
                      'Recognition cycle done in {}ms (average)'.format((time.time() - t0) * 1000 / FPS))
                logger.info('Recognition cycle done in {}ms (average)'.format((time.time() - t0) * 1000 / FPS))
                t0 = time.time()
                FPS = 0
            else:
                FPS += 1
        except Exception as e:
            logger.error('Exception in while loop')


if __name__ == '__main__':
    # os.system('echo 190 > /sys/devices/pwm-fan/target_pwm')
    multiprocessing.set_start_method('forkserver')
    global_stop = multiprocessing.Event()
    global_stop.clear()
    LED1event = multiprocessing.Event()
    LED1event.clear()
    LED2event = multiprocessing.Event()
    LED2event.clear()
    dispoffevent = multiprocessing.Event()
    dispoffevent.clear()
    captured_frame_buffer = multiprocessing.Manager().Queue(1)
    person_ID_queue = multiprocessing.Manager().Queue(1)
    camera_process = Process(target=cam_thread,
                             args=(captured_frame_buffer, dispoffevent, global_stop), daemon=True)
    camera_process.start()
    # camera_back_process = Process(target=cam_back_thread,
    #                              args=(captured_frame_buffer, global_stop), daemon=True)
    # camera_back_process.start()
    recognition_process = Process(target=recognition_thread,
                                  args=(captured_frame_buffer, person_ID_queue,
                                        LED1event, LED2event, global_stop), daemon=True)
    recognition_process.start()
    door_lock_process = Process(target=door_lock_thread,
                                args=(person_ID_queue, LED1event, LED2event, dispoffevent, global_stop), daemon=True)
    door_lock_process.start()

    while True:
        try:
            if global_stop.is_set():
                break
            sleep(1)
        except KeyboardInterrupt:
            global_stop.set()
    camera_process.terminate()
    # camera_back_process.terminate()
    recognition_process.terminate()
    sleep(5)
    door_lock_process.terminate()
