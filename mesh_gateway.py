#!/usr/bin/env python3

from serial import Serial
from serial.tools import list_ports
from typing import Optional, OrderedDict, List, TextIO
from enum import IntEnum
from time import time
import csv
from pathlib import Path


class SensorTypes(IntEnum):
    Temperature = 0x75
    Humidity = 0x76


class SensorEvent(OrderedDict):
    node_addr: int
    sensor: SensorTypes
    value: float

    def from_buffer(self, buf: bytes) -> None:
        self.node_addr = int.from_bytes(buf[0:2], byteorder="big")
        self.sensor = SensorTypes(int.from_bytes(buf[2:4], byteorder="big"))
        self.value = int.from_bytes(buf[4:], byteorder="big") / 100


class MessageType(IntEnum):
    MSG_POLL = 0  # NULL payload
    MSG_BACKLOG = 1  # uint8_t payload
    MSG_PUB = 1  # struct msg_pub_payload
    MSG_ACK = 0xFE  # NULL payload
    MSG_NACK = 0xFF  # NULL payload


class Message(OrderedDict):
    start: int
    msg_type: MessageType
    payload_size: int
    payload: bytes
    crc: int


class Interface:
    _ser: Optional[Serial]
    csv_path: Path

    def __init__(
        self, port: Optional[str] = None, log_path: Optional[str] = None
    ) -> None:

        # initialize the csv output file
        if (log_path is None) or (log_path == ""):
            log_path = "enviro_log.csv"

        self.csv_path = Path(log_path)

        try:
            with open(self.csv_path, "xt", newline="") as f:
                w = csv.writer(f, dialect="unix")
                w.writerow(["Timestamp", "Node Addr", "Sensor", "Value"])
        except FileExistsError:
            # Assume if it exists, we wrote it, and the header is valid.
            # Good enough for now.
            pass

        # Initialize Serial Port
        if port is not None:
            ports = list_ports.comports()
            for a_port in ports:
                if a_port.product == "Mesh Sensor Gateway":
                    try:  # it may be already in use.
                        self._ser = Serial(a_port.device, 115200)
                    except:  # narrow this down a bit
                        pass

        else:
            self._ser = Serial(port, 115200)

    @property
    def connected(self):
        if self._ser is not None:
            return self._ser.isOpen()
        else:
            return False

    def get_message(self) -> Message:
        # Just assume it's a pub event and it's good for now
        if self._ser is not None:
            buf = self._ser.read(10)
            retval = Message()

            retval.start = buf[0]
            retval.msg_type = MessageType(buf[1])
            retval.payload_size = buf[2]
            retval.payload = buf[3:9]
            retval.crc = buf[9]  # Assume crc is good. TODO: validate

            return retval
        else:
            return Message()

    def log_event(self, event: SensorEvent) -> None:
        with open(self.csv_path, "at", newline="") as f:
            w = csv.writer(f, dialect="unix")
            w.writerow(
                (time(), event.node_addr, event.sensor.name, event.value)
            )


if __name__ == "__main__":
    mesh = Interface("/dev/ttyACM1")
    event = SensorEvent()
    try:
        while True:
            message = mesh.get_message()
            # print([hex(i) for i in message.payload])
            event.from_buffer(message.payload)
            print(
                f"Got Event from {event.node_addr}: {event.sensor.name} is {event.value}\n"
            )
            mesh.log_event(event)
    except KeyboardInterrupt:
        pass
