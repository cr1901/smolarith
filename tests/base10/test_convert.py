import pytest
from smolarith.base10 import _DoubleDabble, _B2ToB1000, BinaryToBCD


@pytest.fixture
def basic_tb(mod):
    m = mod

    async def testbench(ctx):
        for i in range(2**m.width):
            await ctx.delay(1.0 / 12e6)
            ctx.set(m.inp, i)

            for n in range(m.width):
                d = i % 10
                i //= 10
                assert ctx.get(m.outp[n]) == d

        await ctx.delay(1.0 / 12e6)

    return testbench


@pytest.fixture
def base1000_tb(mod):
    m = mod

    async def testbench(ctx):
        await ctx.tick()

        ctx.set(m.inp.payload, 33333)
        ctx.set(m.inp.valid, 1)
        ctx.set(m.outp.ready, 1)
        await ctx.tick()

        # I make no promises about latency for a private module.
        await ctx.tick().until(m.outp.valid == 1)

        assert ctx.get(m.outp.payload[0]) == 333
        assert ctx.get(m.outp.payload[1]) == 33

        await ctx.tick()

    return testbench


@pytest.fixture
def base10_tb(mod):
    m = mod

    async def testbench(ctx):
        await ctx.tick()

        val = 543210
        ctx.set(m.inp.payload, 543210)
        ctx.set(m.inp.valid, 1)
        ctx.set(m.outp.ready, 1)
        await ctx.tick()

        # TODO: Create some guarantees about latency?
        await ctx.tick().until(m.outp.valid == 1)

        for n in range(m.width):
            d = val % 10
            val //= 10
            assert ctx.get(m.outp.payload[n]) == d

        await ctx.tick()

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
