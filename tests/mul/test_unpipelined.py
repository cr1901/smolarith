import pytest
from smolarith.mul import MulticycleMul, Sign
from itertools import product


def mk_unpipelined_testbench(m, abs_iter):
    def testbench():
        # Not yielding to the simulator when values don't change
        # can result in significant speedups.
        a_prev = None
        b_prev = None
        s_prev = None

        yield m.inp.valid.eq(1)
        yield m.outp.rdy.eq(1)

        for (a, b, s) in abs_iter:
            if s == Sign.UNSIGNED:
                if a != a_prev:
                    yield m.inp.data.a.eq(a)
                if b != b_prev:
                    yield m.inp.data.b.eq(b)
            else:
                if a != a_prev:
                    yield m.inp.data.a.as_signed().eq(a)
                if b != b_prev:
                    yield m.inp.data.b.as_signed().eq(b)

            if s != s_prev:
                yield m.inp.data.sign.eq(s)
            yield m.inp.valid.eq(1)
            yield
            (a_prev, b_prev, s_prev) = (a, b, s)

            yield m.inp.valid.eq(0)
            while not (yield m.outp.valid):
                yield

            if (yield m.outp.data.sign) == Sign.UNSIGNED.value:
                assert a*b == (yield m.outp.data.o)
            else:
                assert a*b == (yield m.outp.data.o.as_signed())

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

    return mk_unpipelined_testbench(m, product(a_range, b_range, (mode,)))


@pytest.mark.module(MulticycleMul(6, debug=True))
@pytest.mark.clks((1.0 / 12e6,))
@pytest.mark.parametrize("all_values_tb", [Sign.UNSIGNED, Sign.SIGNED,
                                           Sign.SIGNED_UNSIGNED],
                         indirect=True)
def test_unpipelined_mul(sim_mod, all_values_tb):
    sim, m = sim_mod
    sim.run(sync_processes=[all_values_tb])
