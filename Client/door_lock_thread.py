from utils import utils
from subprocess import Popen, PIPE
import fcntl
import serial
import RPi.GPIO as GPIO
import time
from datetime import datetime
import os
import logging

GPIO_RELAY_PINS = (20, 21)  # # relay id = 1, 2
MAX_RELAYS = 2
LED_OFF_DELAY = 3
DOOR_OPENED_DELAY = 5


def relay_init():
    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)
    for pin in GPIO_RELAY_PINS:
        GPIO.setup(pin, GPIO.OUT)


def wiegand_send_card_id(port, card_id):
    str_cmd = "$0: card={} :command=5\n".format(card_id)
    port.write(str_cmd.encode('ascii'))
    time.sleep(0.1)


def wiegand_relay(port, relay_id, state):
    if (relay_id > 0) & (relay_id < MAX_RELAYS + 1):
        if state == 'on':
            str_cmd = "${}: card=0 :command=2\n".format(relay_id)
            port.write(str_cmd.encode('ascii'))
        elif state == 'off':
            str_cmd = "${}: card=0 :command=3\n".format(relay_id)
            port.write(str_cmd.encode('ascii'))
        time.sleep(0.03)


def door_relay(relay_id, state):
    if (relay_id > 0) & (relay_id < MAX_RELAYS+1):
        if state == 'on':
            GPIO.output(GPIO_RELAY_PINS[relay_id-1], GPIO.HIGH)
        elif state == 'off':
            GPIO.output(GPIO_RELAY_PINS[relay_id - 1], GPIO.LOW)


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


def door_lock_thread(person_data_queue, person_detected_event, disp_wakeup_event, stop_event):
    logger = utils.logger_config('door_lock_thread')

    relay_init()

    snd_allowed_cmd = ('gst-launch-1.0 filesrc location=Media/allowed.ogg ! oggdemux ! '
                       'vorbisdec ! audioconvert ! audioresample ! pulsesink &')

    time_to_LED_off = time.time()
    time_to_next_door_open = time.time()
    logger.info('started')
    led_state = 'off'

    while True:
        try:
            if stop_event.is_set():
                logger.info('Done!')
                break
            wiegand_port = serial.Serial(port='/dev/ttyACM0', baudrate=9600, timeout=1.0, write_timeout=1)

            now_time = time.time()

            if person_detected_event.is_set():
                if led_state == 'off':
                    disp_wakeup_event.set()
                    time_to_LED_off = now_time + LED_OFF_DELAY
                    wiegand_relay(wiegand_port, 1, 'on')
                    wiegand_relay(wiegand_port, 1, 'on')
                    door_relay(1, 'on')
                    logger.info('LED on')
                    led_state = 'on'

            if time_to_LED_off < (now_time + LED_OFF_DELAY/3):
                if led_state == 'on':
                    disp_wakeup_event.clear()
                    wiegand_relay(wiegand_port, 1, 'off')
                    wiegand_relay(wiegand_port, 1, 'off')
                    door_relay(1, 'off')
                    logger.info('LED off')
                    led_state = 'off'

            if person_data_queue.empty():
                time.sleep(0.01)
                continue

            pers_id_data = person_data_queue.get()

            if len(pers_id_data) > 0:
                nowDate = datetime.now()
                log_filepath = 'log_{}_{}_{}.txt'.format(nowDate.day, nowDate.month, nowDate.year)
                user_name, user_id, user_timestamp = pers_id_data[0]
                logger.info('Person near the door')

                if time_to_next_door_open < (now_time + DOOR_OPENED_DELAY/2):
                    wiegand_send_card_id(wiegand_port, user_id)

                    wiegand_relay(wiegand_port, 2, 'on')
                    wiegand_relay(wiegand_port, 2, 'on')
                    door_relay(2, 'on')

                    logger.info('Unlock door for {}'.format(user_name))
                    os.system(snd_allowed_cmd)
                    time.sleep(1)

                    wiegand_relay(wiegand_port, 2, 'off')
                    wiegand_relay(wiegand_port, 2, 'off')
                    door_relay(2, 'off')

                    logger.info('Locked the door')
                    time_to_next_door_open = time.time() + DOOR_OPENED_DELAY

                    log_file = open(log_filepath, 'a')
                    log_file.write("{}.{}.{} Users detected at the door:\n".format(nowDate.day,
                                                                                   nowDate.month,
                                                                                   nowDate.year
                                                                                   ))
                    for id_data in pers_id_data:
                        user_name, user_id, user_timestamp = id_data
                        log_file.write("\t{}:{}:{} - {} (#{})\n".format(user_timestamp.hour,
                                                                        user_timestamp.minute,
                                                                        user_timestamp.second,
                                                                        user_name,
                                                                        user_id))
                    log_file.close()
            wiegand_port.close()
        except Exception as e:
            logger.error('Exception in while loop')
            logging.exception("Error")
            res_reset = reset_door_locker()
            if res_reset == 0:
                logger.info('USB reset done!')
            else:
                logger.error('USB reset failed!')
