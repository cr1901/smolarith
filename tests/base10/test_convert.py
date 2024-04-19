import pytest
from smolarith.base10 import _DoubleDabble
from amaranth.sim import Delay


@pytest.fixture
def basic_tb(mod):
    m = mod

    def testbench():
        for i in range(2**m.width):
            yield Delay(1.0 / 12e6)
            yield m.inp.eq(i)

            for n in range(m.width):
                d = i % 10
                i //= 10
                assert (yield m.outp[4*n:4*(n+1)]) == d

        yield Delay(1.0 / 12e6)

    return testbench


# 8192 should be good enough. It's the closest power of two where all 4 bits
# of the highest digit are couts from the _ShiftAdd3s (unused bits are 0).
@pytest.mark.parametrize("mod", [_DoubleDabble(i, debug=True) for i in range(4, 14)],
                         ids=[f"{i}" for i in range(4, 14)])
# @pytest.mark.parametrize("clks", [1.0 / 12e6])
def test_digit(sim, basic_tb):
    sim.run(testbenches=[basic_tb])
