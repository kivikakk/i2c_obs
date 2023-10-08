import os
from abc import ABC
from argparse import ArgumentParser, Namespace
from enum import Enum
from functools import reduce

from serial import Serial

from .rtl.uart import symbols

__all__ = ["add_main_arguments"]


def add_main_arguments(parser: ArgumentParser):
    MAC_ICEBREAKER = "/dev/tty.usbserial-ibEt3maU1"

    parser.set_defaults(func=main)
    parser.add_argument(
        "uart",
        nargs="?",
        default=MAC_ICEBREAKER if os.path.exists(MAC_ICEBREAKER) else "/dev/ttyUSB1",
        help="UART interface",
    )


class State(Enum):
    IDLE = 0
    TRAINING = 1
    STRETCHING = 2


class Event(ABC):
    pass


class StartTrainingEvent(Event):
    def __str__(self):
        return "start link training"


class FinishTrainingEvent(Event):
    _measurements: list[int]

    def __init__(self, measurements: list[int]):
        super().__init__()
        self._measurements = measurements

    def __str__(self):
        tLOW_0 = self._measurements[0]
        tHIGH_0 = self._measurements[1]
        tLOW_1 = self._measurements[2]
        tCYCLE = tLOW_0 + tHIGH_0

        return (
            f"finish link training\n"
            f"raw measurements: {self._measurements!r}\n"
            f"tLOW_0:   1/{TARGET_SYSCLK//tLOW_0:,}s\n"
            f"tHIGH_0:  1/{TARGET_SYSCLK//tHIGH_0:,}s\n"
            f"tLOW_1:   1/{TARGET_SYSCLK//tLOW_1:,}s\n"
            f"tLOW_0+tHIGH_0 = {TARGET_SYSCLK//tCYCLE:,}Hz ({tCYCLE} cycles)\n"
            f"Duty: {tHIGH_0 * 100 / tCYCLE:.1f}%"
        )


class StartStretchingEvent(Event):
    def __str__(self):
        return "start stretching"


class FinishStretchingEvent(Event):
    def __str__(self):
        return "finish stretching"


class UnhandledEvent(Event):
    _state: State
    _b: bytes

    def __init__(self, state: State, b: bytes):
        self._state = state
        self._b = b

    def __str__(self):
        return f"unhandled data in {self._state}: {self._b!r}"


# XXX
TARGET_SYSCLK = 12_000_000


class _Parser:
    _state: State
    _nibbles: list[int]
    _measurements: list[int]

    def __init__(self):
        self._state = State.IDLE

    def feed(self, inp: list[bytes]) -> list[Event]:
        r = []
        for b in inp:
            assert len(b) == 1
            r += self._feed_one(ord(b))
        return r

    def _feed_one(self, b: int) -> list[Event]:
        match self._state:
            case State.IDLE:
                match b:
                    case symbols.STRETCH_START:
                        self._state = State.TRAINING
                        self._nibbles = []
                        self._measurements = []
                        return [StartTrainingEvent()]
                    case _:
                        return [UnhandledEvent(self._state, b)]
            case State.TRAINING:
                match b:
                    case n if 0x00 <= n <= 0x0F:
                        self._nibbles.append(n)
                        return []
                    case symbols.STRETCH_MEASURED:
                        if not self._nibbles:
                            self._state = State.STRETCHING
                            return [
                                FinishTrainingEvent(self._measurements),
                                StartStretchingEvent(),
                            ]
                        count = reduce(
                            lambda a, n: (a << 4) | n, reversed(self._nibbles)
                        )
                        self._measurements.append(count)
                        self._nibbles = []
                        return []
                    case symbols.STRETCH_FINISH:
                        print(
                            f"finish mid-training; nibbles {self._nibbles!r} measurements {self._measurements!r}"
                        )
                        self._state = State.IDLE
                        return [FinishStretchingEvent()]
                    case _:
                        return [UnhandledEvent(self._state, b)]
            case State.STRETCHING:
                match b:
                    case symbols.STRETCH_FINISH:
                        self._state = State.IDLE
                        return [FinishStretchingEvent()]
                    case _:
                        return [UnhandledEvent(self._state, b)]


def main(args: Namespace):
    # TODO configurable serial port.
    try:
        with Serial(args.uart) as ser:
            parser = _Parser()
            while True:
                for event in parser.feed([ser.read()]):
                    print("*", event)
    except KeyboardInterrupt:
        pass
