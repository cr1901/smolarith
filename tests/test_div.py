# amaranth: UnusedElaboratable=no

import pytest
from math import fmod
from smolarith.div import Sign, LongDivider, MulticycleDiv, Impl
from amaranth.sim import Tick
import random
from functools import partial


def amaranth_tb(tb):
    def wrapper(*args, **kwargs):
        return partial(tb, *args, **kwargs)
    return wrapper


@pytest.fixture
def make_basic_testbench(mod):
    m = mod

    @amaranth_tb
    def testbench(values, delay):
        (n, d, q, r, sign) = values
        yield Tick()

        yield m.inp.payload.n.eq(n)
        yield m.inp.payload.d.eq(d)
        yield m.inp.payload.sign.eq(sign)
        yield m.inp.valid.eq(1)
        yield Tick()

        yield m.inp.valid.eq(0)  # Only schedule one xfer.
        yield m.outp.ready.eq(1)  # Immediately ready for retrieval.
        yield Tick()
        for _ in range(delay):
            yield Tick()

        assert (yield m.outp.valid) == 1
        assert (yield m.outp.payload.sign) == sign.value

        if sign == Sign.UNSIGNED:
            assert (yield m.outp.payload.q) == q
            assert (yield m.outp.payload.r) == r
        else:
            assert (yield m.outp.payload.q.as_signed()) == q
            assert (yield m.outp.payload.r.as_signed()) == r

        yield Tick()
        assert (yield m.outp.valid) == 0

    return testbench


@pytest.fixture(params=[(1362, 14, 97, 4, Sign.SIGNED),
                        (-1362, 14, -97, -4, Sign.SIGNED),
                        (1362, -14, -97, 4, Sign.SIGNED),
                        (-1362, -14, 97, -4, Sign.SIGNED),
                        (1362, 14, 97, 4, Sign.UNSIGNED)],
                ids=["i1", "i2", "i3", "i4", "u"])
def reference_values(request):
    return request.param


@pytest.fixture(params=[(-(2**31), -1, -(2**31), 0, Sign.SIGNED),
                        (1, 0, -1, 1, Sign.SIGNED),
                        (-1, 0, -1, -1, Sign.SIGNED),
                        (0xff, 0, 2**32 - 1, 0xff, Sign.UNSIGNED)],
                ids=["ov", "zero1", "zero2", "zero3"])
def riscv_values(request):
    return request.param


@pytest.fixture(params=[
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
    (2047, 2, 1023, 1, Sign.SIGNED)],
    ids=["u1", "i1", "u2", "i2", "u3", "i3", "u4", "i4"])
def mismatch_values(request):
    return request.param


@pytest.fixture(params=[Sign.UNSIGNED, Sign.SIGNED],
                ids=["i", "u"])
def all_values_tb(request, mod):
    m = mod
    sign = request.param

    if sign == Sign.SIGNED:
        @amaranth_tb
        def tb(delay):
            yield Tick()

            for n in range(-2**(m.width-1), 2**(m.width-1)):
                yield m.inp.payload.n.eq(n)
                for d in range(-2**(m.width-1), 2**(m.width-1)):
                    yield m.inp.payload.d.eq(d)
                    yield m.inp.payload.sign.eq(Sign.SIGNED)
                    yield m.inp.valid.eq(1)
                    yield Tick()

                    yield m.inp.valid.eq(0)  # Only schedule one xfer.
                    yield m.outp.ready.eq(1)  # Immediately ready for retrieval.  # noqa: E501
                    yield Tick()
                    for _ in range(delay):
                        yield Tick()

                    assert (yield m.outp.valid) == 1
                    assert (yield m.outp.payload.sign) == Sign.SIGNED.value
                    if n == -2**(m.width-1) and d == -1:
                        assert (yield m.outp.payload.q.as_signed()) == \
                            -2**(m.width-1)
                        assert (yield m.outp.payload.r.as_signed()) == 0
                    elif d == 0:
                        assert (yield m.outp.payload.q.as_signed()) == -1
                        assert (yield m.outp.payload.r.as_signed()) == n
                    else:
                        assert (yield m.outp.payload.q.as_signed()) == \
                            int(n / d)
                        assert (yield m.outp.payload.r.as_signed()) == \
                            fmod(n, d)

                    yield Tick()
    else:  # Sign.UNSIGNED
        @amaranth_tb
        def tb(delay):
            yield Tick()

            for n in range(0, 2**m.width):
                yield m.inp.payload.n.eq(n)
                for d in range(0, 2**m.width):
                    yield m.inp.payload.d.eq(d)
                    yield m.inp.payload.sign.eq(Sign.UNSIGNED)
                    yield m.inp.valid.eq(1)
                    yield Tick()

                    yield m.inp.valid.eq(0)  # Only schedule one xfer.
                    yield m.outp.ready.eq(1)  # Immediately ready for retrieval.  # noqa: E501
                    yield Tick()
                    for _ in range(delay):
                        yield Tick()

                    assert (yield m.outp.valid) == 1
                    assert (yield m.outp.payload.sign) == Sign.UNSIGNED.value
                    if d == 0:
                        assert (yield m.outp.payload.q.as_unsigned()) == \
                            2**m.width - 1
                        assert (yield m.outp.payload.r.as_unsigned()) == n
                    else:
                        assert (yield m.outp.payload.q.as_unsigned()) == \
                            int(n / d)
                        assert (yield m.outp.payload.r.as_unsigned()) == \
                            fmod(n, d)

                    yield Tick()
    
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
def random_values_tb(mod, random_vals):
    m = mod

    @amaranth_tb
    def tb(delay):
        yield Tick()

        for (n, d, s) in random_vals:
            yield m.inp.payload.n.eq(n)
            yield m.inp.payload.d.eq(d)
            yield m.inp.payload.sign.eq(s)
            yield m.inp.valid.eq(1)
            yield Tick()

            yield m.inp.valid.eq(0)  # Only schedule one xfer.
            yield m.outp.ready.eq(1)  # Immediately ready for retrieval.  # noqa: E501
            yield Tick()
            for _ in range(delay):
                yield Tick()

            assert (yield m.outp.valid) == 1
            assert (yield m.outp.payload.sign) == s.value

            if s == Sign.SIGNED:
                if n == -2**(m.width-1) and d == -1:
                    assert (yield m.outp.payload.q.as_signed()) == \
                        -2**(m.width-1)
                    assert (yield m.outp.payload.r.as_signed()) == 0
                elif d == 0:
                    assert (yield m.outp.payload.q.as_signed()) == -1
                    assert (yield m.outp.payload.r.as_signed()) == n
                else:
                    assert (yield m.outp.payload.q.as_signed()) == \
                        int(n / d)
                    assert (yield m.outp.payload.r.as_signed()) == \
                        fmod(n, d)
            else:
                if d == 0:
                    assert (yield m.outp.payload.q.as_unsigned()) == \
                        2**m.width - 1
                    assert (yield m.outp.payload.r.as_unsigned()) == n
                else:
                    assert (yield m.outp.payload.q.as_unsigned()) == \
                        int(n / d)
                    assert (yield m.outp.payload.r.as_unsigned()) == \
                        fmod(n, d)

            yield Tick()

    return tb


DIV_IDS=["nr", "res", "long"]


@pytest.mark.parametrize("mod,delay", [
    (MulticycleDiv(12, impl=Impl.NON_RESTORING), 15 - 1),
    (MulticycleDiv(12, impl=Impl.RESTORING), 14 - 1),
    (LongDivider(12), 11 - 1)],
    ids=DIV_IDS)
@pytest.mark.parametrize("clks", [1.0 / 12e6]) 
def test_reference_div(sim, make_basic_testbench, reference_values, delay):
    sim.run(testbenches=[make_basic_testbench(reference_values, delay)])


@pytest.mark.parametrize("mod,delay", [
    (MulticycleDiv(32, impl=Impl.NON_RESTORING), 35 - 1),
    (MulticycleDiv(32, impl=Impl.RESTORING), 34 - 1),
    (LongDivider(32), 31 - 1)],
    ids=DIV_IDS)
@pytest.mark.parametrize("clks", [1.0 / 12e6])
def test_riscv_compliance(sim, make_basic_testbench, riscv_values, delay):
    sim.run(testbenches=[make_basic_testbench(riscv_values, delay)])


@pytest.mark.parametrize("mod,delay", [
    (MulticycleDiv(12, impl=Impl.NON_RESTORING), 15 - 1),
    (MulticycleDiv(12, impl=Impl.RESTORING), 14 - 1),
    (LongDivider(12), 11 - 1)],
    ids=DIV_IDS)
@pytest.mark.parametrize("clks", [1.0 / 12e6])
def test_signed_unsigned_mismatch(sim, make_basic_testbench, mismatch_values,
                                  delay):
    sim.run(testbenches=[make_basic_testbench(mismatch_values, delay)])


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
def test_random(sim, random_values_tb, delay):
    random.seed(0)
    sim.run(testbenches=[random_values_tb(delay)])


@pytest.mark.parametrize("mod,delay", [
    (MulticycleDiv(8, impl=Impl.NON_RESTORING), 11 - 1),
    (MulticycleDiv(8, impl=Impl.RESTORING), 10 - 1),
    (LongDivider(8), 7 - 1)],
    ids=DIV_IDS)
@pytest.mark.parametrize("clks", [1.0 / 12e6]) 
def test_all_values(sim, all_values_tb, delay):
    sim.run(testbenches=[all_values_tb(delay)])
