#!/usr/bin/env python2

import gevent.monkey; gevent.monkey.patch_all()

import logging
import logging.config
import os
import socket
import string
import StringIO
import struct
import sys

import gevent.socket
import gevent.server
import gevent.event
import yaml


class TftpFile(object):

    def __init__(self, name, buffer_io):
        self.name = name
        self.is_done = False
        self.event = gevent.event.Event()
        self.buffer_io = buffer_io

    def done(self):
        self.is_done = True
        self.event.set()

    def wait(self):
        self.event.wait()


class TftpReceiveFile(TftpFile):

    def read(self):
        self.wait()
        return self.buffer_io.getvalue()


class TftpConnection(gevent.server.DatagramServer):
    BLOCK_SIZE = 512
    RRQ_OP = 1 # Read request
    WRQ_OP = 2 # Write request
    DATA_OP = 3
    ACK_OP = 4
    ERR_OP = 5

    def __init__(self, socket, remote_addr, file_obj):
        super(TftpConnection, self).__init__(socket)
        self.socket = socket
        self.remote_addr = remote_addr
        self.file_obj = file_obj
        self.previous_packet = None

    def send(self, raw_data, may_retransmit=False):
        self.socket.sendto(raw_data, self.remote_addr)
        self.previous_packet = raw_data if may_retransmit else None

    def retransmit(self):
        if self.previous_packet is not None:
            self.send(self.previous_packet)


class TftpSendConnection(TftpConnection):

    def __init__(self, socket, remote_addr, file_obj):
        super(TftpSendConnection, self).__init__(socket, remote_addr, file_obj)
        self.block_num = 0

    def handle(self, data, address):

        # Common header
        buf = buffer(data)
        opcode = struct.unpack("!h", buf[:2])[0]

        # Acknowledgement?
        if opcode == TftpConnection.ACK_OP:
            block = struct.unpack("!h", buf[2:4])[0]

            if block != self.block_num:
                raise Exception("wrong ack, expected %i, got %i" % (self.block_num, block))

            if self.file_obj.is_done:
                return

            self._send_data()

        # Error?
        elif opcode == TftpConnection.ERR_OP:
            err_num, err_text = struct.unpack("!h", buf[2:4])[0], buf[4:-1]
            print err_num, repr(err_text)
            self.retransmit()

    def start(self):
        super(TftpSendConnection, self).start()
        self.send_data()

    def send_data(self):
        data = self.read_file.read(TftpConnection.BLOCK_SIZE)
        self.last_packet = struct.pack("!hh", TftpConnection.DATA_OP, self.block_num)
        self.send(self.last_packet)

        if len(data) < TftpConnection.BLOCK_SIZE:
            self.file_obj.done()


class TftpReceiveConnection(TftpConnection):

    def __init__(self, socket, remote_addr, file_obj):
        super(TftpReceiveConnection, self).__init__(socket, remote_addr, file_obj)
        self.block_num = 0
        self.previous_packet = None

    def start(self):
        super(TftpReceiveConnection, self).start()
        self.send_ack()

    def handle(self, data, address):

        # Common header
        buf = buffer(data)
        opcode = struct.unpack("!h", buf[:2])[0]

        # Data transfer?
        if opcode == TftpConnection.DATA_OP:
            block, data = struct.unpack("!h", buf[2:4])[0], buf[4:]

            if not self.file_obj:
                raise Exception("still waiting for first packet")

            if block != self.block_num:
                raise Exception("wrong block, expected %i, got %i" % (self.block_num, block))

            self.file_obj.buffer_io.write(data)

            if TftpConnection.BLOCK_SIZE != len(data):
                self.file_obj.done()

            self.send_ack()

        # Error?
        elif opcode == TftpConnection.ERR_OP:
            err_num, err_text = struct.unpack("!h", buf[2:4])[0], buf[4:-1]
            print err_num, repr(err_text)
            self.retransmit()

    def send_data(self):
        data = self.read_file.read(TftpConnection.BLOCK_SIZE)
        self.file_obj.is_done = len(data) < TftpConnection.BLOCK_SIZE
        self.last_packet = struct.pack("!hh", TftpConnection.DATA_OP, self.block_num)
        self.send(self.last_packet)

        if self.file_obj.is_done:
            self.file_obj.done()

    def send_ack(self):
        self.previous_packet = struct.pack("!hh", TftpConnection.ACK_OP, self.block_num)
        self.send(self.previous_packet)
        self.block_num += 1


class TftpServer(gevent.server.DatagramServer):

    def __init__(self, interface):
        super(TftpServer, self).__init__(interface)
        self.sendable = {}
        self.receivable = {}

    def receive(self, filename):
        if filename in self.receivable:
            raise Exception('already receiving file: "%s"')
        file_obj = TftpReceiveFile(filename, StringIO.StringIO())
        self.receivable[filename] = file_obj
        return file_obj

    def send(self, filename, content):
        if filename in self.sendable:
            raise Exception('already sending file: "%s"')
        file_obj = TftpFile(filename, StringIO.StringIO(content))
        self.sendable[filename] = file_obj
        return file_obj

    def handle(self, data, address):

        # Common header
        buf = buffer(data)
        opcode = struct.unpack("!h", buf[:2])[0]

        # Read/write request?
        if opcode == TftpConnection.RRQ_OP:
            filename, mode, _ = string.split(data[2:], "\0")

            if filename not in self.sendable:
                raise Exception("invalid filename: %s" % filename)

            file_obj = self.sendable[filename]
            new_socket = gevent.socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            TftpSendConnection(new_socket, address, file_obj).start()
            del self.sendable[filename]

        elif opcode == TftpConnection.WRQ_OP:
            filename, mode, _ = string.split(data[2:], "\0")

            if filename not in self.receivable:
                raise Exception("invalid filename: %s" % filename)

            file_obj = self.receivable[filename]
            new_socket = gevent.socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            TftpReceiveConnection(new_socket, address, file_obj).start()
            del self.receivable[filename]


def main():

    # Configure logging
    for path in ('logging.yml', 'logging.default.yml'):
        if not os.path.isfile(path):
            continue
        with open(path, 'rt') as file:
            config = yaml.load(file)
        logging.config.dictConfig(config)

    # Start server
    server = TftpServer('0.0.0.0:6969')
    server.start()

    # Await file upload
    print server.receive("test.txt").read()


if __name__ == '__main__':
    main()

