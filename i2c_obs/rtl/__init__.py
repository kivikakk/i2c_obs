from typing import Final, cast

from amaranth import Array, Elaboratable, Module, Mux, Signal
from amaranth.build import Attrs
from amaranth.hdl.ast import Assert, Display
from amaranth.lib.wiring import Component, In, Out
from amaranth_boards.resources import I2CResource

from ..platform import Platform, icebreaker, orangecrab
from .common import ButtonWithHold, Hz
from .uart import UART, symbols

__all__ = ["Top"]


class Top(Component):
    VALID_SPEEDS: Final[list[int]] = [
        100_000,
        400_000,
        1_000_000,
    ]
    DEFAULT_SPEED: Final[int] = 400_000

    switch: In(1)
    led: Out(1)
    scl_oe: Out(1)
    scl_o: Out(1)
    scl_i: In(1)

    _speed: Hz

    def __init__(
        self,
        *,
        platform: Platform,
        speed: Hz = Hz(400_000),
    ):
        super().__init__()
        self._speed = speed

    def ports(self, platform: Platform) -> list[Signal]:
        return [getattr(self, name) for name in self.signature.members.keys()]

    def elaborate(self, platform: Platform) -> Elaboratable:
        m = Module()

        m.submodules.button = ButtonWithHold()
        m.d.comb += m.submodules.button.i.eq(self.switch)
        button_up = m.submodules.button.up

        m.submodules.uart = uart = UART()

        # I've removed the pull-up resistors here since they should
        # be provided by the controller.
        match platform:
            case icebreaker():
                m.d.comb += [
                    self.switch.eq(platform.request("button").i),
                    platform.request("led").o.eq(self.led),
                ]
                platform.add_resources(
                    [
                        I2CResource(
                            0,
                            scl="1",
                            sda="2",
                            conn=("pmod", 0),
                            attrs=Attrs(IO_STANDARD="SB_LVCMOS"),
                        )
                    ]
                )
                i2c = platform.request("i2c")
                m.d.comb += [
                    i2c.scl.oe.eq(self.scl_oe),
                    i2c.scl.o.eq(self.scl_o),
                    self.scl_i.eq(i2c.scl.i),
                ]

            case orangecrab():
                m.d.comb += [
                    self.switch.eq(platform.request("button").i),
                    platform.request("led").o.eq(self.led),
                ]
                platform.add_resources(
                    [
                        I2CResource(
                            0,
                            scl="scl",
                            sda="sda",
                            conn=("io", 0),
                            attrs=Attrs(IO_TYPE="LVCMOS33"),
                        )
                    ]
                )
                i2c = platform.request("i2c")
                m.d.comb += [
                    i2c.scl.oe.eq(self.scl_oe),
                    i2c.scl.o.eq(self.scl_o),
                    self.scl_i.eq(i2c.scl.i),
                ]

                with m.If(m.submodules.button.held):
                    m.d.sync += cast(Signal, platform.request("program").o).eq(1)

            case _:
                button_up = self.switch

        # Not stretching by default.
        m.d.comb += [
            self.scl_o.eq(0),
            self.scl_oe.eq(0),
        ]

        scl_last = Signal()
        m.d.sync += scl_last.eq(self.scl_i)

        freq = cast(int, platform.default_clk_frequency)
        counter_max = int(freq // 10_000)
        # We wait for sum of 2 measurements.
        timer_count = Signal(range(counter_max * 2 + 1))

        # Measurement starts at 1 in the cycle we see SCL drop, and is
        # incremented every cycle thereafter as long as SCL is stable;
        # repeat for 3 consecutive measurements (i.e. low-high-low).
        #
        #       |      |      |      |      |      |      |      |      |      |
        # ___   |      |      |     _|______|______|___   |      |      |     _|
        #    \  |      |      |    / |      |      |   \  |      |      |    / |
        #     \_|______|______|___/  |      |      |    \_|______|______|___/  |
        #       |      |      |      |      |      |      |      |      |      |
        #        a1     a2     a3     b1     b2     b3     c1     c2     c3
        N_MEASUREMENTS = 3
        measurements = Array(
            [Signal(range(counter_max + 1)) for _ in range(N_MEASUREMENTS)]
        )
        measure_ix = Signal(range(N_MEASUREMENTS))
        measures_sent = Signal(range(N_MEASUREMENTS))
        measured_count_report = Signal.like(measurements[0])

        m.d.sync += uart.wr_en.eq(0)

        with m.FSM() as fsm:
            m.d.comb += self.led.eq(~fsm.ongoing("IDLE"))

            with m.State("IDLE"):
                with m.If(button_up):
                    m.d.sync += [
                        uart.wr_data.eq(symbols.STRETCH_START),
                        uart.wr_en.eq(1),
                    ]
                    m.next = "TRAINING: WAIT"

            with m.State("TRAINING: WAIT"):
                # Falling edge.
                with m.If(scl_last & ~self.scl_i):
                    m.d.sync += [
                        measures_sent.eq(0),
                        measure_ix.eq(0),
                        *(m.eq(1) for m in measurements),
                    ]
                    m.next = "TRAINING: COUNT"
                with m.If(button_up):
                    m.next = "FISH"

            with m.State("TRAINING: COUNT"):
                with m.If(self.scl_i == scl_last):
                    m.d.sync += measurements[measure_ix].eq(
                        measurements[measure_ix] + 1
                    )
                with m.Else():
                    m.d.sync += measured_count_report.eq(measurements[measure_ix])
                    if platform.simulation:
                        m.d.comb += Assert(
                            Mux(measure_ix[0] == 0, self.scl_i, ~self.scl_i)
                        )
                        # XXX This does things I truly do not anticipate in cxxsim.
                        m.d.sync += Display(
                            "measurement #{0:d} count: {1:d}",
                            measure_ix,
                            measurements[measure_ix],
                        )
                    with m.If(measure_ix == N_MEASUREMENTS - 1):
                        m.next = "STRETCH: WAIT"
                    with m.Else():
                        m.d.sync += measure_ix.eq(measure_ix + 1)
                with m.If(button_up):
                    m.next = "FISH"

            with m.State("STRETCH: WAIT"):
                # Stretching counting starts when we detect SCL go low: we
                # register the number of additional cycles to be held after this
                # one, which will equal zero on the cycle we need to relax.
                #
                #       |      |      |      |      |      |      |
                # ___   |      |      |      |      |      |     _|
                #    \  |      |      |      |      |      |    / |
                #     \_|______|______|______|______|______|___/  |
                #       |      |      |      |      |      |      |
                #        =4     =3     =2     =1     =0     0
                #
                # The initial value is therefore the desired tLOW cycle count
                # minus two.
                #
                # I'm choosing the sum of measurements[0]+[1] as the desired cycle count:
                # this lets SCL rise at exactly the time it'd normally next fall.
                with m.If(scl_last & ~self.scl_i):
                    m.d.sync += timer_count.eq(sum(measurements[:2]) - 2)
                    m.next = "LOW: HOLD"
                with m.If(button_up):
                    m.next = "FISH"

            with m.State("LOW: HOLD"):
                m.d.comb += self.scl_oe.eq(1)
                m.d.sync += timer_count.eq(timer_count - 1)
                with m.If(timer_count == 0):
                    m.next = "LOW: FINISHED HOLD"
                with m.If(button_up):
                    m.next = "FISH"

            with m.State("LOW: FINISHED HOLD"):
                with m.If(self.scl_i):
                    m.next = "STRETCH: WAIT"
                with m.If(button_up):
                    m.next = "FISH"

            with m.State("FISH"):
                m.d.sync += [
                    uart.wr_data.eq(symbols.STRETCH_FINISH),
                    uart.wr_en.eq(1),
                ]
                m.next = "IDLE"

        writing_measured_count = Signal()
        m.d.sync += writing_measured_count.eq(0)
        with m.If(measured_count_report != 0):
            m.d.sync += [
                uart.wr_data.eq(measured_count_report[:4]),
                uart.wr_en.eq(1),
                measured_count_report.eq(measured_count_report >> 4),
                writing_measured_count.eq(1),
            ]
        with m.Elif(writing_measured_count):
            m.d.sync += [
                uart.wr_data.eq(symbols.STRETCH_MEASURED),
                uart.wr_en.eq(1),
                measures_sent.eq(measures_sent + 1),
            ]
            with m.If(measures_sent == N_MEASUREMENTS - 1):
                m.d.sync += writing_measured_count.eq(1)

        return m
