import pytest
from smolarith.base10 import _DoubleDabble, _B2ToB1000, BinaryToBCD
from amaranth.sim import Delay, Tick


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
                assert (yield m.outp[n]) == d

        yield Delay(1.0 / 12e6)

    return testbench


@pytest.fixture
def base1000_tb(mod):
    m = mod

    def testbench():
        yield Tick()

        yield m.inp.payload.eq(33333)
        yield m.inp.valid.eq(1)
        yield m.outp.ready.eq(1)
        yield Tick()

        # I make no promises about latency for a private module.
        while (yield m.outp.valid) == 0:
            yield Tick()

        assert (yield m.outp.payload[0]) == 333
        assert (yield m.outp.payload[1]) == 33

        yield Tick()

    return testbench


@pytest.fixture
def base10_tb(mod):
    m = mod

    def testbench():
        yield Tick()

        val = 543210
        yield m.inp.payload.eq(543210)
        yield m.inp.valid.eq(1)
        yield m.outp.ready.eq(1)
        yield Tick()

        # TODO: Create some guarantees about latency?
        while (yield m.outp.valid) == 0:
            yield Tick()

        for n in range(m.width):
            d = val % 10
            val //= 10
            assert (yield m.outp.payload[n]) == d

        yield Tick()

    return testbench


# 8192 should be good enough. It's the closest power of two where all 4 bits
# of the highest digit are couts from the _ShiftAdd3s (unused bits are 0).
@pytest.mark.parametrize("mod", [_DoubleDabble(i, debug=True) for i in range(4, 14)],  # noqa: E501
                         ids=[f"{i}" for i in range(4, 14)])
# @pytest.mark.parametrize("clks", [1.0 / 12e6])
def test_digit(sim, basic_tb):
    sim.run(testbenches=[basic_tb])


@pytest.mark.parametrize("mod", [_B2ToB1000()])
@pytest.mark.parametrize("clks", [1.0 / 12e6])
def test_base1000(sim, base1000_tb):
    sim.run(testbenches=[base1000_tb])


@pytest.mark.parametrize("mod", [BinaryToBCD(20)])
@pytest.mark.parametrize("clks", [1.0 / 12e6])
def test_base10(sim, base10_tb):
    sim.run(testbenches=[base10_tb])
