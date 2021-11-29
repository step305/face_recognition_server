import cv2
from datetime import datetime
from utils import utils
import numpy as np
import time
import os
import logging

DISP_ROI_SZ = (600, 720)
DISPLAY_SIZE = (600, 1024)
CAMERA_FRAME_SIZE = (1280, 720)
TIMER_COORDS = (DISPLAY_SIZE[0]-100, 100)
TIMER_COLOR = (255, 255, 255)
CAMERA_FPS = 30
SKIP_FRAMES_MAX = 2
SCREEN_OFF_DELAY = 4
SCREEN_SAVER_FPS = 30
FRAMES_FOR_FPS = 100


def camera_thread(frame_buffer, wakeup_event, stop_event):
    logger = utils.logger_config('camera_thread')

    capture_pipeline = (
        'v4l2src device=/dev/video0 ! '
        'image/jpeg, width={}, height={}, framerate={}/1, format=MJPG ! '
        'jpegparse ! jpegdec ! videoconvert ! video/x-raw, format=BGR ! appsink'.format(CAMERA_FRAME_SIZE[0],
                                                                                        CAMERA_FRAME_SIZE[1],
                                                                                        CAMERA_FPS)
    )
    cam = cv2.VideoCapture(capture_pipeline, cv2.CAP_GSTREAMER)

    # writer_pipeline = (
    #    'appsrc ! videoconvert ! video/x-raw, format=NV12 ! '
    #    'nvvidconv ! video/x-raw(memory:NVMM), width={}, height={}, format=NV12 ! '
    #    'nvv4l2h265enc bitrate=8000000 maxperf-enable=1 '
    #    'preset-level=1 insert-sps-pps=1 profile=1 iframeinterval=1 ! '
    #    'h264parse ! rtph264pay ! udpsink host=127.0.0.1 '
    #    'port=5000 async=0 sync=0'
    # ).format(CAMERA_FRAME_SIZE[0], CAMERA_FRAME_SIZE[1])
    writer_pipeline = (
        'appsrc ! videoconvert ! video/x-raw, width={}, height={} ! '
        'omxh264enc ! video / x-h264, profile=high ! udpsink host=127.0.0.1 port=5000 sync=false'
    ).format(CAMERA_FRAME_SIZE[0], CAMERA_FRAME_SIZE[1])

    udp_writer = cv2.VideoWriter(writer_pipeline, cv2.CAP_GSTREAMER, 0, CAMERA_FPS, CAMERA_FRAME_SIZE, True)

    # mask1 = cv2.imread('Media/mask1_2.jpg', 0)
    # Logo = cv2.imread('Media/logo2.jpg')
    screen_saver = cv2.VideoCapture('screen_saver.mp4')
    logger.info('Loaded media')

    crop_roi_x = (CAMERA_FRAME_SIZE[0]/2 - DISP_ROI_SZ[0]/2, CAMERA_FRAME_SIZE[0]/2 + DISP_ROI_SZ[0]/2)
    crop_roi_y = (CAMERA_FRAME_SIZE[1] / 2 - DISP_ROI_SZ[1] / 2, CAMERA_FRAME_SIZE[1] / 2 + DISP_ROI_SZ[1] / 2)
    disp_roi_x = (DISPLAY_SIZE[0]/2 - DISP_ROI_SZ[0]/2, DISPLAY_SIZE[0]/2 + DISP_ROI_SZ[0]/2)
    disp_roi_y = (DISPLAY_SIZE[1] / 2 - DISP_ROI_SZ[1] / 2, DISPLAY_SIZE[1] / 2 + DISP_ROI_SZ[1] / 2)

    black_frame = np.zeros((DISPLAY_SIZE[1], DISPLAY_SIZE[0], 3), np.uint8)
    final_frame = np.zeros((DISPLAY_SIZE[1], DISPLAY_SIZE[0], 3), np.uint8)

    time.sleep(10)

    # os.system('xrandr -o normal')
    os.system('v4l2-ctl -d 0 -c zoom_absolute=160')
    os.system('v4l2-ctl -d 0 -c pan_absolute=0')
    os.system('v4l2-ctl -d 0 -c tilt_absolute=0')
    os.system('v4l2-ctl -d 0 -c brightness=140')
    os.system('./RTSPserver &')

    logger.info('camera config done')

    window_name = 'FaceRecWindow'
    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
    cv2.setWindowProperty(window_name, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)

    t0 = time.monotonic()
    t1 = t0

    frames_cnt = 0
    skip_frames = SKIP_FRAMES_MAX
    time_to_screenoff = time.time()

    saver_frame_counter = 0

    while True:
        try:
            ret, frame = cam.read()
            if not ret:
                continue
            if frame_buffer.empty():
                if skip_frames == 0:
                    fr = frame
                    frame_buffer.put(fr)
                    skip_frames = SKIP_FRAMES_MAX
                else:
                    skip_frames -= 1
            udp_writer.write(frame)
            now_time = time.time()
            if wakeup_event.is_set():
                time_to_screenoff = now_time + SCREEN_OFF_DELAY
                logger.info('person in frame!')
            if time_to_screenoff < (now_time + SCREEN_OFF_DELAY/4):
                rr, frame_saver = screen_saver.read()
                saver_frame_counter += 1
                if saver_frame_counter == screen_saver.get(cv2.CAP_PROP_FRAME_COUNT):
                    saver_frame_counter = 0  # Or whatever as long as it is the same as next line
                    screen_saver.set(cv2.CAP_PROP_POS_FRAMES, 0)
                time.sleep(1 / SCREEN_SAVER_FPS)
                frame = frame_saver
            final_frame = np.zeros((DISPLAY_SIZE[1], DISPLAY_SIZE[0], 3), np.uint8)
            final_frame[
                disp_roi_y[0]:disp_roi_y[1],
                disp_roi_x[0]:disp_roi_x[1]
            ] = frame[crop_roi_y[0]:crop_roi_y[1],
                crop_roi_x[0]:crop_roi_x[1]]

            cur_time = datetime.now().time()
            cv2.putText(final_frame,
                        '{}:{}:{:.0f}'.format(cur_time.hour, cur_time.minute, cur_time.second),
                        TIMER_COORDS,
                        cv2.FONT_HERSHEY_SIMPLEX,
                        1,
                        TIMER_COLOR)
            cv2.imshow(window_name, final_frame)

            frames_cnt += 1
            if frames_cnt >= FRAMES_FOR_FPS:
                t1 = time.monotonic()
                logger.info('FPS = {}'.format(frames_cnt / (t1 - t0)))
                frames_cnt = 0
                t0 = t1
            if (cv2.waitKey(1) & 0xFF) == ord('q'):
                stop_event.set()
                break
            if stop_event.is_set():
                break
        except Exception as e:
            logger.error('exception in while loop')
            logging.exception("Error")
    cam.release()
    screen_saver.release()
    logger.info('done!')
    os.system('pkill RTSPserver')
    cv2.destroyAllWindows()
