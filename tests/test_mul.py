# amaranth: UnusedElaboratable=no

import pytest
from smolarith.mul import MulticycleMul, PipelinedMul, Sign
from collections import deque
from itertools import product
from functools import partial
import random
from amaranth.sim import Tick


def amaranth_tb(tb):
    def wrapper(*args, **kwargs):
        return partial(tb, *args, **kwargs)
    return wrapper


@pytest.fixture
def make_testbench(mod):
    m = mod

    if isinstance(mod, PipelinedMul):
        @amaranth_tb
        def tb(values):
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

            for (a, b, s) in values:
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
    elif isinstance(mod, MulticycleMul):
        @amaranth_tb
        def tb(values):
            # Not yielding to the simulator when values don't change
            # can result in significant speedups.
            a_prev = None
            b_prev = None
            s_prev = None

            yield Tick()

            yield m.inp.valid.eq(1)
            yield m.outp.ready.eq(1)

            for (a, b, s) in values:
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
                yield m.inp.valid.eq(1)
                yield Tick()
                (a_prev, b_prev, s_prev) = (a, b, s)

                yield m.inp.valid.eq(0)
                while not (yield m.outp.valid):
                    yield Tick()

                if (yield m.outp.payload.sign) == Sign.UNSIGNED.value:
                    assert a*b == (yield m.outp.payload.o)
                else:
                    assert a*b == (yield m.outp.payload.o.as_signed())
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
def random_vals(request):
    def vals():
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

    return vals()


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


@pytest.mark.parametrize("mod", [PipelinedMul(8, debug=True),
                                 MulticycleMul(6)])
@pytest.mark.parametrize("clks", [1.0 / 12e6])
def test_all_values(sim, all_values, make_testbench):
    sim.run(testbenches=[make_testbench(all_values)])


@pytest.mark.parametrize("mod", [PipelinedMul(32, debug=True),
                                 MulticycleMul(32)])
@pytest.mark.parametrize("clks", [1.0 / 12e6])
def test_random_32b(sim, random_vals, make_testbench):
    random.seed(0)
    sim.run(testbenches=[make_testbench(random_vals)])


@pytest.mark.parametrize("mod,clks", [(PipelinedMul(8, debug=True),
                                       1.0 / 12e6)])
def test_pipeline_stall(sim, pipeline_tb):
    sim.run(testbenches=[pipeline_tb])
