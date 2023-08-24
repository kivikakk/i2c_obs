from abc import ABC
from argparse import ArgumentParser, Namespace
from enum import Enum
from functools import reduce

from serial import Serial

from .rtl.uart import symbols

__all__ = ["add_main_arguments"]


def add_main_arguments(parser: ArgumentParser):
    parser.set_defaults(func=main)
    parser.add_argument(
        "uart",
        nargs="?",
        default="/dev/ttyUSB1",
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
    _bus: int

    def __init__(self, bus: int):
        self._bus = bus

    def __str__(self):
        return f"finish link training: bus speed {self._bus:,} Hz"


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


class _Parser:
    _state: State
    _count: list[int]
    _bus: int

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
                        self._count = []
                        return [StartTrainingEvent()]
                    case _:
                        return [UnhandledEvent(self._state, b)]
            case State.TRAINING:
                match b:
                    case n if 0x00 <= n <= 0x0F:
                        self._count.append(n)
                        return []
                    case symbols.STRETCH_MEASURED:
                        self._state = State.STRETCHING
                        count = reduce(lambda a, n: (a << 4) | n, reversed(self._count))
                        # XXX this depends on the target.
                        period = 12_000_000 // count
                        self._bus = period // 2
                        return [FinishTrainingEvent(self._bus)]
                    case symbols.STRETCH_FINISH:
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
    with Serial(args.uart) as ser:
        parser = _Parser()
        while True:
            for event in parser.feed([ser.read()]):
                print("*", event)
