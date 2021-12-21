#!/usr/bin/env python3
from __future__ import print_function

from multiprocessing import Process
import multiprocessing
import time
import recognition_thread
import door_lock_thread
from config.config import USE_PICAMERA
if USE_PICAMERA:
    import picamera_thread
else:
    import camera_thread


if __name__ == '__main__':
    multiprocessing.set_start_method('forkserver')

    global_stop_event = multiprocessing.Event()
    global_stop_event.clear()

    person_detected_event = multiprocessing.Event()
    person_detected_event.clear()

    wakeup_event = multiprocessing.Event()
    wakeup_event.clear()

    captured_frame_buffer = multiprocessing.Manager().Queue(1)
    person_id_queue = multiprocessing.Manager().Queue(1)

    if USE_PICAMERA:
        camera_process = Process(target=picamera_thread.camera_thread,
                                 args=(captured_frame_buffer, wakeup_event, global_stop_event),
                                 daemon=True)
    else:
        camera_process = Process(target=camera_thread.camera_thread,
                                 args=(captured_frame_buffer, wakeup_event, global_stop_event),
                                 daemon=True)
    camera_process.start()

    recognition_process = Process(target=recognition_thread.recognition_thread,
                                  args=(captured_frame_buffer, person_id_queue,
                                        person_detected_event, global_stop_event),
                                  daemon=True)
    recognition_process.start()

    door_lock_process = Process(target=door_lock_thread.door_lock_thread,
                                args=(person_id_queue, person_detected_event, wakeup_event, global_stop_event),
                                daemon=True)
    door_lock_process.start()

    while True:
        try:
            if global_stop_event.is_set():
                break
            time.sleep(1)
        except KeyboardInterrupt:
            global_stop_event.set()
    camera_process.terminate()
    recognition_process.terminate()
    time.sleep(5)
    door_lock_process.terminate()
