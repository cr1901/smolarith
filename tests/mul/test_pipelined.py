import pytest
from smolarith.mul import PipelinedMul, Sign
from collections import deque
from itertools import product
import random


def mk_pipelined_testbench(m, abs_iter):
    def testbench():
        # Pipeline previous inputs... inputs to prev.append() are what
        # will go into the multiplier at the next active edge.
        # Outputs from prev.popleft()  are what went into the multiplier
        # "m.width - 1" active edges ago. This leads to a latency of
        # "m.width" clock cycles/ticks since the multiplier saw the inputs.
        prev = deque([(0, 0)]*m.width)

        # Not yielding to the simulator when values don't change
        # can result in significant speedups.
        a_prev = None
        b_prev = None
        s_prev = None

        for (a, b, s) in abs_iter:
            if s == Sign.UNSIGNED:
                if a != a_prev:
                    yield m.a.as_unsigned().eq(a)
                if b != b_prev:
                    yield m.b.as_unsigned().eq(b)
            else:
                if a != a_prev:
                    yield m.a.eq(a)
                if b != b_prev:
                    yield m.b.eq(b)

            if s != s_prev:
                yield m.sign.eq(s)
            yield
            (a_prev, b_prev, s_prev) = (a, b, s)

            (a_c, b_c) = prev.popleft()
            prev.append((a, b))

            if (yield m.sign_out) == Sign.UNSIGNED.value:
                assert a_c*b_c == (yield m.o.as_unsigned())
            else:
                assert a_c*b_c == (yield m.o)

            # print((a, b), (a_c, b_c), a_c*b_c, (yield m.o))
            # for i in range(8):
            #     print(f"{yield m.pin[i].a:08b}, {yield m.pin[i].b:08b}")
            # for i in range(8):
            #      print(f"{yield m.pout[i]:016b}")

        # Drain pipeline.
        for _ in range(m.width):
            yield
            (a_c, b_c) = prev.popleft()
            prev.append((a, b))

            if (yield m.sign_out) == Sign.UNSIGNED.value:
                assert a_c*b_c == (yield m.o.as_unsigned())
            else:
                assert a_c*b_c == (yield m.o)

    return testbench


@pytest.fixture
def all_values_tb(request, sim_mod):
    _, m = sim_mod
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
def random_tb(sim_mod):
    _, m = sim_mod

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


@pytest.mark.module(PipelinedMul(8, debug=True))
@pytest.mark.clks((1.0 / 12e6,))
@pytest.mark.parametrize("all_values_tb", [Sign.UNSIGNED, Sign.SIGNED,
                                           Sign.SIGNED_UNSIGNED],
                         indirect=True)
def test_pipelined_mul(sim_mod, all_values_tb):
    sim, m = sim_mod
    sim.run(sync_processes=[all_values_tb])


@pytest.mark.module(PipelinedMul(32, debug=True))
@pytest.mark.clks((1.0 / 12e6,))
def test_random_32b(sim_mod, random_tb):
    sim, m = sim_mod
    random.seed(0)
    sim.run(sync_processes=[random_tb])
