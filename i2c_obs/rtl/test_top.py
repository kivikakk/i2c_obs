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

        STRETCHES = [0, 0, 3, 3]
        for ix, expected in enumerate(STRETCHES):
            yield dut.scl_i.eq(0)
            yield
            yield
            yield

            yield dut.scl_i.eq(1)
            yield
            actual = 0
            while (yield dut.scl_oe):
                actual += 1
                yield
            self.assertEqual(
                actual,
                expected,
                f"ix {ix} expected {expected} stretched cycles, got {actual}",
            )
            yield
            yield
