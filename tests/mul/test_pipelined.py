# amaranth: UnusedElaboratable=no

import pytest
from smolarith.mul import PipelinedMul, Sign
from collections import deque
from itertools import product
import random
from amaranth.sim import Tick


def mk_pipelined_testbench(m, abs_iter):
    def testbench():
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

        yield Tick()

        yield m.inp.valid.eq(1)
        yield m.outp.ready.eq(1)

        for (a, b, s) in abs_iter:
            if s == Sign.UNSIGNED:
                if a != a_prev:
                    yield m.inp.payload.a.eq(a)
                if b != b_prev:
                    yield m.inp.payload.b.eq(b)
            else:
                if a != a_prev:
                    yield m.inp.payload.a.as_signed().eq(a)
                if b != b_prev:
                    yield m.inp.payload.b.as_signed().eq(b)

            if s != s_prev:
                yield m.inp.payload.sign.eq(s)
            yield Tick()
            (a_prev, b_prev, s_prev) = (a, b, s)

            (a_c, b_c) = prev.popleft()
            prev.append((a, b))

            if (yield m.outp.payload.sign) == Sign.UNSIGNED.value:
                assert a_c*b_c == (yield m.outp.payload.o)
            else:
                assert a_c*b_c == (yield m.outp.payload.o.as_signed())

            # print((a, b), (a_c, b_c), a_c*b_c, (yield m.o))
            # for i in range(8):
            #     print(f"{yield m.pin[i].a:08b}, {yield m.pin[i].b:08b}")
            # for i in range(8):
            #      print(f"{yield m.pout[i]:016b}")

        # Drain pipeline.
        for _ in range(m.width):
            yield Tick()
            (a_c, b_c) = prev.popleft()
            prev.append((a, b))

            if (yield m.outp.payload.sign) == Sign.UNSIGNED.value:
                assert a_c*b_c == (yield m.outp.payload.o)
            else:
                assert a_c*b_c == (yield m.outp.payload.o.as_signed())

    return testbench


@pytest.fixture
def all_values_tb(request, mod):
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

    return mk_pipelined_testbench(m, product(a_range, b_range, (mode,)))


@pytest.fixture
def random_tb(mod):
    m = mod

    def random_muls():
        for i in range(256):
            a = random.randint(-2**31, (2**31)-1)
            b = random.randint(-2**31, (2**31)-1)
            s = random.choice([Sign.UNSIGNED, Sign.SIGNED,
                               Sign.SIGNED_UNSIGNED])

            if s == Sign.UNSIGNED:
                if a < 0:
                    a *= -1
                if b < 0:
                    b *= -1
            elif s == Sign.SIGNED_UNSIGNED and b < 0:
                b *= -1

            yield (a, b, s)

    return mk_pipelined_testbench(m, random_muls())


@pytest.fixture
def pipeline_tb(mod):
    def testbench():
        m = mod

        yield Tick()

        yield m.inp.payload.sign.eq(Sign.UNSIGNED)
        yield m.inp.payload.a.eq(1)
        yield m.inp.payload.b.eq(1)
        yield m.inp.valid.eq(1)
        yield m.outp.ready.eq(1)
        yield Tick()

        yield m.inp.payload.a.eq(2)
        yield m.inp.payload.b.eq(2)
        yield Tick()

        # Pipeline should continue working...
        yield m.inp.valid.eq(0)
        yield Tick()

        yield m.inp.valid.eq(1)
        yield m.inp.payload.a.eq(3)
        yield m.inp.payload.b.eq(3)
        yield Tick()

        yield m.inp.payload.a.eq(4)
        yield m.inp.payload.b.eq(4)
        yield Tick()

        yield m.inp.valid.eq(0)
        for _ in range(3):
            yield Tick()

        yield m.outp.ready.eq(0)
        assert (yield m.outp.valid) == 1
        assert (yield m.outp.payload.sign) == Sign.UNSIGNED
        assert (yield m.outp.payload.o) == 1
        # Pipeline should stall...
        assert (yield m.inp.ready) == 0
        yield Tick()

        # Until we indicate we're ready to accept data.
        yield m.outp.ready.eq(1)
        assert (yield m.inp.ready) == 1
        yield Tick()

        assert (yield m.outp.valid) == 1
        assert (yield m.outp.payload.sign) == Sign.UNSIGNED
        assert (yield m.outp.payload.o) == 4
        assert (yield m.inp.ready) == 1
        yield Tick()

        assert (yield m.outp.valid) == 0
        assert (yield m.inp.ready) == 1
        yield Tick()

        assert (yield m.outp.valid) == 1
        assert (yield m.outp.payload.sign) == Sign.UNSIGNED
        assert (yield m.outp.payload.o) == 9
        assert (yield m.inp.ready) == 1
        yield Tick()

        assert (yield m.outp.valid) == 1
        assert (yield m.outp.payload.sign) == Sign.UNSIGNED
        assert (yield m.outp.payload.o) == 16
        assert (yield m.inp.ready) == 1
        yield Tick()

        assert (yield m.outp.valid) == 0
        assert (yield m.inp.ready) == 1
        yield Tick()

    return testbench


@pytest.mark.parametrize("all_values_tb", [Sign.UNSIGNED, Sign.SIGNED,
                                           Sign.SIGNED_UNSIGNED],
                         indirect=True)
@pytest.mark.parametrize("mod,clks", [(PipelinedMul(8, debug=True),
                                       1.0 / 12e6)])
def test_pipelined_mul(sim, all_values_tb):
    sim.run(testbenches=[all_values_tb])


@pytest.mark.parametrize("mod,clks", [(PipelinedMul(32, debug=True),
                                       1.0 / 12e6)])
def test_random_32b(sim, random_tb):
    random.seed(0)
    sim.run(testbenches=[random_tb])


@pytest.mark.parametrize("mod,clks", [(PipelinedMul(8, debug=True),
                                       1.0 / 12e6)])
def test_pipeline_stall(sim, pipeline_tb):
    sim.run(testbenches=[pipeline_tb])
