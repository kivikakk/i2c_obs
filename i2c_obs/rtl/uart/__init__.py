from typing import Optional

from amaranth import C, Cat, Elaboratable, Module, Signal
from amaranth.lib.fifo import SyncFIFO
from amaranth.lib.wiring import Component, Out

from ...platform import Platform, icebreaker
from ..common import Counter

__all__ = ["UART"]


class UART(Component):
    wr_data: Out(8)
    wr_en: Out(1)

    _baud: int
    _c: Counter
    _fifo: SyncFIFO
    _tx: Signal

    def __init__(self, *, baud: int = 9600):
        self._baud = baud
        super().__init__()
        self._c = Counter(hz=self._baud)
        self._fifo = SyncFIFO(width=8, depth=16)
        self._tx = Signal()

    def elaborate(self, platform: Optional[Platform]) -> Elaboratable:
        m = Module()

        match platform:
            case icebreaker():
                uart = platform.request("uart")
                m.d.comb += uart.tx.eq(self._tx)

            case _:
                pass

        m.submodules.c = self._c

        m.submodules.fifo = self._fifo
        m.d.comb += [
            self._fifo.w_data.eq(self.wr_data),
            self._fifo.w_en.eq(self.wr_en),
            self._tx.eq(1),
        ]
        m.d.sync += self._fifo.r_en.eq(0)

        # Shove the START and STOP bits in here too!
        data = Signal(10)
        written = Signal(range(10))

        with m.FSM():
            with m.State("IDLE"):
                with m.If(self._fifo.r_rdy):
                    m.d.sync += [
                        data.eq(Cat(C(0, 1), self._fifo.r_data, C(1, 1))),  # Meow :3
                        written.eq(0),
                        self._fifo.r_en.eq(1),
                    ]
                    m.next = "TX"

            with m.State("TX"):
                m.d.comb += [
                    self._c.en.eq(1),
                    self._tx.eq(data[0]),
                ]
                with m.If(self._c.full):
                    m.d.sync += [
                        data.eq(data >> 1),
                        written.eq(written + 1),
                    ]
                    with m.If(written == 9):
                        m.next = "IDLE"

        return m
