from .. import sim
from . import Top


class TestTop(sim.TestCase):
    SIM_CLOCK = 1e-6

    def test_sim_top(self, dut: Top) -> sim.Procedure:
        yield dut.scl_i.eq(1)
        yield
        yield dut.switch.eq(1)
        yield
        yield dut.switch.eq(0)
        yield dut.scl_i.eq(0)
        yield
        yield
        yield
        yield
        yield
        yield
        yield dut.scl_i.eq(1)
        yield
        yield
