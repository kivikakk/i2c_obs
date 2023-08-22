from typing import Final, Optional, cast

from amaranth import Elaboratable, Module, Signal
from amaranth.build import Attrs
from amaranth.hdl.ast import Assert, Display
from amaranth.lib.wiring import Component, In, Out
from amaranth_boards.resources import I2CResource

from ..platform import Platform, icebreaker, orangecrab, test, cxxsim
from .common import ButtonWithHold, Hz

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

    def elaborate(self, platform: Optional[Platform]) -> Elaboratable:
        m = Module()

        m.submodules.button = ButtonWithHold()
        m.d.comb += m.submodules.button.i.eq(self.switch)
        button_up = m.submodules.button.up

        # I've removed the pull-up resistors here since they should
        # be provided by the controller.
        match platform:
            case icebreaker():
                m.d.comb += [
                    self.switch.eq(platform.request("button").i),
                    self.led.eq(platform.request("led").o),
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
                    self.led.eq(platform.request("led").o),
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

            case test():
                button_up = self.switch

            case cxxsim():
                button_up = self.switch

        # Not stretching by default.
        m.d.comb += self.scl_o.eq(0)
        m.d.sync += self.scl_oe.eq(0)

        scl_last = Signal()
        m.d.sync += scl_last.eq(self.scl_i)

        freq = cast(int, platform.default_clk_frequency)
        counter_max = int(freq // 100_000) + 1
        measured_count = Signal(range(counter_max))
        timer_count = Signal(len(measured_count) * 2)

        with m.FSM() as fsm:
            m.d.comb += self.led.eq(~fsm.ongoing("IDLE"))
            with m.State("IDLE"):
                with m.If(button_up):
                    m.next = "MEASURE: PRE"

            with m.State("MEASURE: PRE"):
                with m.If(~self.scl_i & (self.scl_i != scl_last)):
                    m.d.sync += measured_count.eq(0)
                    m.next = "MEASURE: COUNT"

            with m.State("MEASURE: COUNT"):
                m.d.sync += measured_count.eq(measured_count + 1)
                with m.If(self.scl_i != scl_last):
                    if platform.simulation:
                        m.d.comb += Assert(self.scl_i)
                        m.d.sync += Display("Measured count: {0:d}", measured_count)
                    m.next = "HIGH: WAIT"

            with m.State("HIGH: WAIT"):
                # Falling edge on SCL, hold it low ourselves
                # for (measured_count*2)-1.
                with m.If(self.scl_i != scl_last):
                    if platform.simulation:
                        m.d.comb += Assert(~self.scl_i)
                    m.d.sync += [
                        timer_count.eq((measured_count*2)-1),
                        self.scl_oe.eq(1),
                    ]
                    m.next = "LOW: HOLD"

            with m.State("LOW: HOLD"):
                m.d.sync += timer_count.eq(timer_count - 1)
                with m.If(timer_count == 0):
                    m.next = "LOW: FINISHED HOLD"
                with m.Else():
                    m.d.sync += self.scl_oe.eq(1)

            with m.State("LOW: FINISHED HOLD"):
                with m.If(self.scl_i):
                    m.next = "HIGH: WAIT"

        return m
