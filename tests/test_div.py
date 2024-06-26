# amaranth: UnusedElaboratable=no

import pytest
from math import fmod
from smolarith.div import Sign, LongDivider, MulticycleDiv, Impl
import random


@pytest.fixture
def basic_testbench(mod, values, delay):
    m = mod

    async def testbench(ctx):
        (n, d, q, r, sign) = values
        await ctx.tick()

        ctx.set(m.inp.payload.n, n)
        ctx.set(m.inp.payload.d, d)
        ctx.set(m.inp.payload.sign, sign)
        ctx.set(m.inp.valid, 1)
        await ctx.tick()

        ctx.set(m.inp.valid, 0)  # Only schedule one xfer.
        ctx.set(m.outp.ready, 1)  # Immediately ready for retrieval.
        await ctx.tick().repeat(delay + 1)

        assert ctx.get(m.outp.valid) == 1
        assert ctx.get(m.outp.payload.sign) == sign.value

        if sign == Sign.UNSIGNED:
            assert ctx.get(m.outp.payload.q) == q
            assert ctx.get(m.outp.payload.r) == r
        else:
            assert ctx.get(m.outp.payload.q.as_signed()) == q
            assert ctx.get(m.outp.payload.r.as_signed()) == r

        await ctx.tick()
        assert ctx.get(m.outp.valid) == 0

    return testbench


@pytest.fixture(params=[Sign.UNSIGNED, Sign.SIGNED],
                ids=["i", "u"])
def all_values_tb(request, mod, delay):
    m = mod
    sign = request.param

    if sign == Sign.SIGNED:
        async def tb(ctx):
            await ctx.tick()

            for n in range(-2**(m.width-1), 2**(m.width-1)):
                ctx.set(m.inp.payload.n, n)
                for d in range(-2**(m.width-1), 2**(m.width-1)):
                    ctx.set(m.inp.payload.d, d)
                    ctx.set(m.inp.payload.sign, Sign.SIGNED)
                    ctx.set(m.inp.valid, 1)
                    await ctx.tick()

                    ctx.set(m.inp.valid, 0)  # Only schedule one xfer.
                    ctx.set(m.outp.ready, 1)  # Immediately ready for retrieval.  # noqa: E501
                    await ctx.tick().repeat(delay + 1)

                    assert ctx.get(m.outp.valid) == 1
                    assert ctx.get(m.outp.payload.sign) == Sign.SIGNED.value
                    if n == -2**(m.width-1) and d == -1:
                        assert ctx.get(m.outp.payload.q.as_signed()) == \
                            -2**(m.width-1)
                        assert ctx.get(m.outp.payload.r.as_signed()) == 0
                    elif d == 0:
                        assert ctx.get(m.outp.payload.q.as_signed()) == -1
                        assert ctx.get(m.outp.payload.r.as_signed()) == n
                    else:
                        assert ctx.get(m.outp.payload.q.as_signed()) == \
                            int(n / d)
                        assert ctx.get(m.outp.payload.r.as_signed()) == \
                            fmod(n, d)

                    await ctx.tick()
    else:  # Sign.UNSIGNED
        async def tb(ctx):
            await ctx.tick()

            for n in range(0, 2**m.width):
                ctx.set(m.inp.payload.n, n)
                for d in range(0, 2**m.width):
                    ctx.set(m.inp.payload.d, d)
                    ctx.set(m.inp.payload.sign, Sign.UNSIGNED)
                    ctx.set(m.inp.valid, 1)
                    await ctx.tick()

                    ctx.set(m.inp.valid, 0)  # Only schedule one xfer.
                    ctx.set(m.outp.ready, 1)  # Immediately ready for retrieval.  # noqa: E501
                    await ctx.tick().repeat(delay + 1)

                    assert ctx.get(m.outp.valid) == 1
                    assert ctx.get(m.outp.payload.sign) == Sign.UNSIGNED.value
                    if d == 0:
                        assert ctx.get(m.outp.payload.q.as_unsigned()) == \
                            2**m.width - 1
                        assert ctx.get(m.outp.payload.r.as_unsigned()) == n
                    else:
                        assert ctx.get(m.outp.payload.q.as_unsigned()) == \
                            int(n / d)
                        assert ctx.get(m.outp.payload.r.as_unsigned()) == \
                            fmod(n, d)

                    await ctx.tick()
    
    return tb


@pytest.fixture
def random_vals(mod):
    w = mod.width -1

    def shift_to_unsigned(v):
        if v == -2*w:
            return 0  # Most negative value maps to 0.
        elif v < 0:
            return v * -1
        else:  # v >= 0
            return v | (1 << w)

    def vals():
        for i in range(256):
            n = random.randint(-2**w, (2**w)-1)
            d = random.randint(-2**w, (2**w)-1)
            s = random.choice([Sign.UNSIGNED, Sign.SIGNED])

            if s == Sign.UNSIGNED:
                n = shift_to_unsigned(n)
                d = shift_to_unsigned(d)

                assert n >= 0
                assert d >= 0

            yield (n, d, s)

    return vals()


@pytest.fixture
def random_values_tb(mod, random_vals, delay):
    m = mod

    async def tb(ctx):
        await ctx.tick()

        for (n, d, s) in random_vals:
            ctx.set(m.inp.payload.n, n)
            ctx.set(m.inp.payload.d, d)
            ctx.set(m.inp.payload.sign, s)
            ctx.set(m.inp.valid, 1)
            await ctx.tick()

            ctx.set(m.inp.valid, 0)  # Only schedule one xfer.
            ctx.set(m.outp.ready, 1)  # Immediately ready for retrieval.  # noqa: E501
            await ctx.tick().repeat(delay + 1)

            assert ctx.get(m.outp.valid) == 1
            assert ctx.get(m.outp.payload.sign) == s.value

            if s == Sign.SIGNED:
                if n == -2**(m.width-1) and d == -1:
                    assert ctx.get(m.outp.payload.q.as_signed()) == \
                        -2**(m.width-1)
                    assert ctx.get(m.outp.payload.r.as_signed()) == 0
                elif d == 0:
                    assert ctx.get(m.outp.payload.q.as_signed()) == -1
                    assert ctx.get(m.outp.payload.r.as_signed()) == n
                else:
                    assert ctx.get(m.outp.payload.q.as_signed()) == \
                        int(n / d)
                    assert ctx.get(m.outp.payload.r.as_signed()) == \
                        fmod(n, d)
            else:
                if d == 0:
                    assert ctx.get(m.outp.payload.q.as_unsigned()) == \
                        2**m.width - 1
                    assert ctx.get(m.outp.payload.r.as_unsigned()) == n
                else:
                    assert ctx.get(m.outp.payload.q.as_unsigned()) == \
                        int(n / d)
                    assert ctx.get(m.outp.payload.r.as_unsigned()) == \
                        fmod(n, d)

            await ctx.tick()

    return tb


DIV_IDS=["nr", "res", "long"]


@pytest.mark.parametrize("mod,delay", [
    (MulticycleDiv(12, impl=Impl.NON_RESTORING), 15 - 1),
    (MulticycleDiv(12, impl=Impl.RESTORING), 14 - 1),
    (LongDivider(12), 11 - 1)],
    ids=DIV_IDS)
@pytest.mark.parametrize("clks", [1.0 / 12e6])
@pytest.mark.parametrize("values", [(1362, 14, 97, 4, Sign.SIGNED),
                                    (-1362, 14, -97, -4, Sign.SIGNED),
                                    (1362, -14, -97, 4, Sign.SIGNED),
                                    (-1362, -14, 97, -4, Sign.SIGNED),
                                    (1362, 14, 97, 4, Sign.UNSIGNED)],
                         ids=["i1", "i2", "i3", "i4", "u"])
def test_reference_div(sim, basic_testbench):
    sim.run(testbenches=[basic_testbench])


@pytest.mark.parametrize("mod,delay", [
    (MulticycleDiv(32, impl=Impl.NON_RESTORING), 35 - 1),
    (MulticycleDiv(32, impl=Impl.RESTORING), 34 - 1),
    (LongDivider(32), 31 - 1)],
    ids=DIV_IDS)
@pytest.mark.parametrize("clks", [1.0 / 12e6])
@pytest.mark.parametrize("values", [(-(2**31), -1, -(2**31), 0, Sign.SIGNED),
                                    (1, 0, -1, 1, Sign.SIGNED),
                                    (-1, 0, -1, -1, Sign.SIGNED),
                                    (0xff, 0, 2**32 - 1, 0xff, Sign.UNSIGNED)],
                         ids=["ov", "zero1", "zero2", "zero3"])
def test_riscv_compliance(sim, basic_testbench):
    sim.run(testbenches=[basic_testbench])


@pytest.mark.parametrize("mod,delay", [
    (MulticycleDiv(12, impl=Impl.NON_RESTORING), 15 - 1),
    (MulticycleDiv(12, impl=Impl.RESTORING), 14 - 1),
    (LongDivider(12), 11 - 1)],
    ids=DIV_IDS)
@pytest.mark.parametrize("clks", [1.0 / 12e6])
@pytest.mark.parametrize("values", 
                         [  
                             # 100000000001
                             (2049, 2, 1024, 1, Sign.UNSIGNED),
                             # 100000000001
                             (-2047, 2, -1023, -1, Sign.SIGNED),
                             # 100000000000
                             (2048, 2, 1024, 0, Sign.UNSIGNED),
                             # 100000000000
                             (-2048, 2, -1024, 0, Sign.SIGNED),
                             # 100000000000
                             (2048, 1, 2048, 0, Sign.UNSIGNED),
                             # 100000000000
                             (-2048, 1, -2048, 0, Sign.SIGNED),
                             # 011111111111
                             (2047, 2, 1023, 1, Sign.UNSIGNED),
                             # 011111111111
                             (2047, 2, 1023, 1, Sign.SIGNED)
                         ],
                         ids=["u1", "i1", "u2", "i2", "u3", "i3", "u4", "i4"])
def test_signed_unsigned_mismatch(sim, basic_testbench):
    sim.run(testbenches=[basic_testbench])


# FIXME: Use of fmod to calculate remainder causes precision issues for
# testing 64-bit dividers.
@pytest.mark.parametrize("mod,delay", [
    (MulticycleDiv(32, impl=Impl.NON_RESTORING), 35 - 1),
    (MulticycleDiv(32, impl=Impl.RESTORING), 34 - 1),
    (LongDivider(32), 31 - 1),
    pytest.param(MulticycleDiv(64, impl=Impl.NON_RESTORING), 67 - 1,
                 marks=pytest.mark.xfail(reason="fmod precision issues")),
    pytest.param(MulticycleDiv(64, impl=Impl.RESTORING), 66 - 1,
                 marks=pytest.mark.xfail(reason="fmod precision issues")),
    pytest.param(LongDivider(64), 63 - 1,
                 marks=pytest.mark.xfail(reason="fmod precision issues"))],
    ids=["n32", "r32", "l32", "n64", "r64", "l64"])
@pytest.mark.parametrize("clks", [1.0 / 12e6])
def test_random(sim, random_values_tb):
    random.seed(0)
    sim.run(testbenches=[random_values_tb])


@pytest.mark.parametrize("mod,delay", [
    (MulticycleDiv(8, impl=Impl.NON_RESTORING), 11 - 1),
    (MulticycleDiv(8, impl=Impl.RESTORING), 10 - 1),
    (LongDivider(8), 7 - 1)],
    ids=DIV_IDS)
@pytest.mark.parametrize("clks", [1.0 / 12e6]) 
def test_all_values(sim, all_values_tb):
    sim.run(testbenches=[all_values_tb])
