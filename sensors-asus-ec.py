#!/usr/bin/python3
# -*- coding: utf-8 -*-

__license__ = "GNU Affero General Public License http://www.gnu.org/licenses/agpl.html"
__copyright__ = "Copyright (C) 2021 Shawn Bruce - Released under terms of the AGPLv3 License"

import os
import sys
import time
import argparse
import socket
import threading
from _thread import *
from daemonize import Daemonize
import json

EC_PATH = '/sys/kernel/debug/ec/ec0/io'

SUPPORTED_MODELS =  {   'ROG CROSSHAIR VIII DARK HERO':
                        [
                        {
                            'name': 'MOTHERBOARD_TEMP',
                            'offset': 0x3c,
                            'type': int(),
                            'suffix': '°C',
                            'page': 0,
                            'size': 1,
                        },
                        {
                            'name': 'CHIPSET_TEMP',
                            'offset': 0x3a,
                            'type': int(),
                            'suffix': '°C',
                            'page': 0,
                            'size': 1
                        },
                        {
                            'name': 'CPU_TEMP',
                            'offset': 0x3b,
                            'type': int(),
                            'suffix': '°C',
                            'page': 0,
                            'size': 1
                        },
                        {
                            'name': 'T_SENSOR',
                            'offset': 0x3d,
                            'type': int(),
                            'suffix': '°C',
                            'page': 0,
                            'size': 1
                        },
                        {
                            'name': 'WATER_FLOW',
                            'offset': 0xbd,
                            'type': int(),
                            'suffix': 'RPM',
                            'page': 0,
                            'size': 1
                        },
                        {
                            'name': 'WATER_IN',
                            'offset': 0,
                            'type': int(),
                            'suffix': '°C',
                            'page': 1,
                            'size': 1
                        },
                        {
                            'name': 'WATER_OUT',
                            'offset': 1,
                            'type': int(),
                            'suffix': '°C',
                            'page': 1,
                            'size': 1
                        },
                        {
                            'name': 'VCore',
                            'offset': 0xa2,
                            'type': int(),
                            'suffix': 'mV',
                            'page': 0,
                            'size': 2
                        }
                        ]
                    }


class Reader:
    def __init__(self, daemonize = False):
        self.data = dict()
        if daemonize:
            self._thread = threading.Thread(target=self.run)
            self._thread.daemon = True
            self._thread.start()
        else:
            self.update()

    def update(self):
        current_page = None
        with open(EC_PATH, 'rb') as fh:
            data = fh.read()

        for s in SUPPORTED_MODELS['ROG CROSSHAIR VIII DARK HERO']:
            page = s['page']
            size = s['size']
            if page != current_page:
                with open(EC_PATH, 'wb') as fh:
                    fh.seek(0xff)
                    fh.write(bytes([page]))
                    current_page = page

                with open(EC_PATH, 'rb') as fh:
                    data = fh.read()
            if size == 1:
                v = data[s['offset']]
            elif size == 2:
                v = (data[s['offset']] * 256) + data[s['offset'] + 1]

            self.data[s['name']] = '{} {}'.format(v, s['suffix'])

        # Reset page back to zero when we're done
        with open(EC_PATH, 'wb') as fh:
            fh.seek(0xff)
            fh.write(bytes([0]))

    def run(self):
        while True:
            self.update()
            time.sleep(1)

    def get(self):
        return self.data


class Server:
    def __init__(self, port, reader):
        self.reader = reader
        self.port = port

    def handle_connection(self, c):
        d = json.dumps(self.reader.get())
        c.send(d.encode())
        c.close()

    def run(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.bind(('127.0.0.1', self.port))

        s.listen(5)
        while True:
            c, addr = s.accept()
            start_new_thread(self.handle_connection, (c,))


def main():
    arg_parser = argparse.ArgumentParser()
    arg_parser.add_argument('-d', '--daemon', dest='daemon', action='store_true', default=False, required=False)
    arg_parser.add_argument('-f', '--foreground', dest='foreground', action='store_true', default=False, required=False)
    arg_parser.add_argument('-p', '--pidfile',dest='pidfile', default='/var/run/sensors-asus-ec.pid', required=False)
    arg_parser.add_argument('-P', '--port', dest='port', default=2787, required=False)
    args = arg_parser.parse_args()

    if args.daemon:
        reader = Reader(daemonize=True)
        server = Server(args.port, reader)

        daemon = Daemonize(app='sensors-asus-ec', pid=args.pidfile, foreground=args.foreground, action=server.run)

        daemon.start()
    else:
        data = None

        try:
            s = socket.socket()
            s.connect(('127.0.0.1', args.port))

            data = s.recv(1024).decode()
            data = json.loads(data)
        except:
            pass

        if not data:
            try:
                reader = Reader()
                data = reader.get()
            except:
                print("Unable to read data.")
                sys.exit(1)

        for k, v in data.items():
            print('{:20}: {}'.format(k, v))

if __name__ == '__main__':
    main()