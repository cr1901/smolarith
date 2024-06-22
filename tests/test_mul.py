# amaranth: UnusedElaboratable=no

import pytest
from smolarith.mul import MulticycleMul, PipelinedMul, Sign
from collections import deque
from itertools import product
import random


def make_testbench(mod, values):
    m = mod

    if isinstance(mod, PipelinedMul):
        async def tb(ctx):
            # Pipeline previous inputs... inputs to prev.append() are what
            # just went into the multiplier at the current active edge.
            # Outputs from prev.popleft() are what went into the multiplier
            # "m.width" active edges ago. This leads to a latency of
            # "m.width" clock cycles/ticks since the multiplier saw the inputs.
            #
            # We only need m.width - 1 storage, because a latency of "1" means
            # the multiplier outputs will be immediately available after the
            # current active edge that just happened (no need to store!).
            # This testbench doesn't work with m.width == 1 :).
            prev = deque([(0, 0)]*(m.width - 1))

            # Not yielding to the simulator when values don't change
            # can result in significant speedups.
            a_prev = None
            b_prev = None
            s_prev = None

            await ctx.tick()

            ctx.set(m.inp.valid, 1)
            ctx.set(m.outp.ready, 1)

            for (a, b, s) in values:
                if s == Sign.UNSIGNED:
                    if a != a_prev:
                        ctx.set(m.inp.payload.a, a)
                    if b != b_prev:
                        ctx.set(m.inp.payload.b, b)
                else:
                    if a != a_prev:
                        ctx.set(m.inp.payload.a.as_signed(), a)
                    if b != b_prev:
                        ctx.set(m.inp.payload.b.as_signed(), b)

                if s != s_prev:
                    ctx.set(m.inp.payload.sign, s)
                await ctx.tick()
                (a_prev, b_prev, s_prev) = (a, b, s)

                (a_c, b_c) = prev.popleft()
                prev.append((a, b))

                if ctx.get(m.outp.payload.sign) == Sign.UNSIGNED.value:
                    assert a_c*b_c == ctx.get(m.outp.payload.o)
                else:
                    assert a_c*b_c == ctx.get(m.outp.payload.o.as_signed())

                # print((a, b), (a_c, b_c), a_c*b_c, (yield m.o))
                # for i in range(8):
                #     print(f"{yield m.pin[i].a:08b}, {yield m.pin[i].b:08b}")
                # for i in range(8):
                #      print(f"{yield m.pout[i]:016b}")

            # Drain pipeline.
            for _ in range(m.width):
                await ctx.tick()
                (a_c, b_c) = prev.popleft()
                prev.append((a, b))

                if ctx.get(m.outp.payload.sign) == Sign.UNSIGNED.value:
                    assert a_c*b_c == ctx.get(m.outp.payload.o)
                else:
                    assert a_c*b_c == ctx.get(m.outp.payload.o.as_signed())
    elif isinstance(mod, MulticycleMul):
        async def tb(ctx):
            # Not yielding to the simulator when values don't change
            # can result in significant speedups.
            a_prev = None
            b_prev = None
            s_prev = None

            await ctx.tick()

            ctx.set(m.inp.valid, 1)
            ctx.set(m.outp.ready, 1)

            for (a, b, s) in values:
                if s == Sign.UNSIGNED:
                    if a != a_prev:
                        ctx.set(m.inp.payload.a, a)
                    if b != b_prev:
                        ctx.set(m.inp.payload.b, b)
                else:
                    if a != a_prev:
                        ctx.set(m.inp.payload.a.as_signed(), a)
                    if b != b_prev:
                        ctx.set(m.inp.payload.b.as_signed(), b)

                if s != s_prev:
                    ctx.set(m.inp.payload.sign, s)
                ctx.set(m.inp.valid, 1)
                await ctx.tick()
                (a_prev, b_prev, s_prev) = (a, b, s)

                ctx.set(m.inp.valid, 0)
                await ctx.tick().until(m.outp.valid == 1)

                if ctx.get(m.outp.payload.sign) == Sign.UNSIGNED.value:
                    assert a*b == ctx.get(m.outp.payload.o)
                else:
                    assert a*b == ctx.get(m.outp.payload.o.as_signed())
    else:
        assert False

    return tb


@pytest.fixture(params=[Sign.UNSIGNED, Sign.SIGNED, Sign.SIGNED_UNSIGNED],
                ids=["u", "i", "iu"])
def all_values(request, mod):
    m = mod
    mode = request.param

    if mode == Sign.UNSIGNED:
        a_range = range(0, 2**m.width)
        b_range = range(0, 2**m.width)
    elif mode == Sign.SIGNED:
        a_range = range(-2**(m.width-1), 2**(m.width-1))
        b_range = range(-2**(m.width-1), 2**(m.width-1))
    else:  # Sign.SIGNED_UNSIGNED
        a_range = range(-2**(m.width-1), 2**(m.width-1))
        b_range = range(0, 2**m.width)

    return product(a_range, b_range, (mode,))


@pytest.fixture
def random_vals(mod):
    w = mod.width -1

    def shift_to_unsigned(v):
        if v == -2**w:
            return 0  # Most negative value maps to 0.
        elif v < 0:
            return v * -1
        else:  # v >= 0
            return v | (1 << 31)

    def vals():
        for i in range(256):
            a = random.randint(-2**w, (2**w)-1)
            b = random.randint(-2**w, (2**w)-1)
            s = random.choice([Sign.UNSIGNED, Sign.SIGNED,
                               Sign.SIGNED_UNSIGNED])

            if s == Sign.UNSIGNED:
                a = shift_to_unsigned(a)
                b = shift_to_unsigned(b)
            elif s == Sign.SIGNED_UNSIGNED and b < 0:
                b = shift_to_unsigned(b)

            yield (a, b, s)

    return vals()


@pytest.fixture
def pipeline_tb(mod):
    async def testbench(ctx):
        m = mod

        await ctx.tick()

        ctx.set(m.inp.payload.sign, Sign.UNSIGNED)
        ctx.set(m.inp.payload.a, 1)
        ctx.set(m.inp.payload.b, 1)
        ctx.set(m.inp.valid, 1)
        ctx.set(m.outp.ready, 1)
        await ctx.tick()

        ctx.set(m.inp.payload.a, 2)
        ctx.set(m.inp.payload.b, 2)
        await ctx.tick()

        # Pipeline should continue working...
        ctx.set(m.inp.valid, 0)
        await ctx.tick()

        ctx.set(m.inp.valid, 1)
        ctx.set(m.inp.payload.a, 3)
        ctx.set(m.inp.payload.b, 3)
        await ctx.tick()

        ctx.set(m.inp.payload.a, 4)
        ctx.set(m.inp.payload.b, 4)
        await ctx.tick()

        ctx.set(m.inp.valid, 0)
        await ctx.tick().repeat(3)

        ctx.set(m.outp.ready, 0)
        assert ctx.get(m.outp.valid) == 1
        assert ctx.get(m.outp.payload.sign) == Sign.UNSIGNED
        assert ctx.get(m.outp.payload.o) == 1
        # Pipeline should stall...
        assert ctx.get(m.inp.ready) == 0
        await ctx.tick()

        # Until we indicate we're ready to accept data.
        ctx.set(m.outp.ready, 1)
        assert ctx.get(m.inp.ready) == 1
        await ctx.tick()

        assert ctx.get(m.outp.valid) == 1
        assert ctx.get(m.outp.payload.sign) == Sign.UNSIGNED
        assert ctx.get(m.outp.payload.o) == 4
        assert ctx.get(m.inp.ready) == 1
        await ctx.tick()

        assert ctx.get(m.outp.valid) == 0
        assert ctx.get(m.inp.ready) == 1
        await ctx.tick()

        assert ctx.get(m.outp.valid) == 1
        assert ctx.get(m.outp.payload.sign) == Sign.UNSIGNED
        assert ctx.get(m.outp.payload.o) == 9
        assert ctx.get(m.inp.ready) == 1
        await ctx.tick()

        assert ctx.get(m.outp.valid) == 1
        assert ctx.get(m.outp.payload.sign) == Sign.UNSIGNED
        assert ctx.get(m.outp.payload.o) == 16
        assert ctx.get(m.inp.ready) == 1
        await ctx.tick()

        assert ctx.get(m.outp.valid) == 0
        assert ctx.get(m.inp.ready) == 1
        await ctx.tick()

    return testbench


@pytest.mark.parametrize("mod", [PipelinedMul(8, debug=True),
                                 MulticycleMul(6)])
@pytest.mark.parametrize("clks", [1.0 / 12e6])
def test_all_values(sim, mod, all_values):
    sim.run(testbenches=[make_testbench(mod, all_values)])


@pytest.mark.parametrize("mod", [PipelinedMul(32, debug=True),
                                 MulticycleMul(32),
                                 PipelinedMul(64, debug=True),
                                 MulticycleMul(64)],
                         ids=["p32", "m32", "p64", "m64"])
@pytest.mark.parametrize("clks", [1.0 / 12e6])
def test_random(sim, mod, random_vals):
    random.seed(0)
    sim.run(testbenches=[make_testbench(mod, random_vals)])


@pytest.mark.parametrize("mod,clks", [(PipelinedMul(8, debug=True),
                                       1.0 / 12e6)])
def test_pipeline_stall(sim, pipeline_tb):
    sim.run(testbenches=[pipeline_tb])
