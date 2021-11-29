from config.config import PORTS
import subprocess

if __name__ == '__main__':
    progs = []
    for port in PORTS:
        progs.append(subprocess.Popen(['python3', 'server.py', '--port', '{}'.format(port)]))
    print('Press Ctrl+C to exit...')
    while True:
        try:
            pass
        except KeyboardInterrupt as e:
            for prog in progs:
                prog.terminate()
            break
