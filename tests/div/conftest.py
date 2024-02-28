import pytest
from math import fmod
from smolarith.div import Sign


@pytest.fixture
def reference_tb(sim_mod, n, d, q, r, sign):
    _, m = sim_mod

    def testbench(delay):
        yield m.inp.payload.n.eq(n)
        yield m.inp.payload.d.eq(d)
        yield m.inp.payload.sign.eq(sign)
        yield m.inp.valid.eq(1)
        yield

        yield m.inp.valid.eq(0)  # Only schedule one xfer.
        yield m.outp.ready.eq(1)  # Immediately ready for retrieval.
        yield
        for _ in range(delay):
            yield

        assert (yield m.outp.valid) == 1
        assert (yield m.outp.payload.sign) == sign.value

        if (yield m.outp.payload.sign) == Sign.UNSIGNED.value:
            assert (yield m.outp.payload.q) == q
            assert (yield m.outp.payload.r) == r
        else:
            assert (yield m.outp.payload.q.as_signed()) == q
            assert (yield m.outp.payload.r.as_signed()) == r

        yield
        assert (yield m.outp.valid) == 0

    return testbench


@pytest.fixture
def mismatch_tb(sim_mod, n, d, q, r, sign):
    _, m = sim_mod

    def testbench(delay):
        yield m.inp.payload.n.eq(n)
        yield m.inp.payload.d.eq(d)
        yield m.inp.payload.sign.eq(sign)
        yield m.inp.valid.eq(1)
        yield

        yield m.inp.valid.eq(0)  # Only schedule one xfer.
        yield m.outp.ready.eq(1)  # Immediately ready for retrieval.
        yield
        for _ in range(delay):
            yield

        assert (yield m.outp.valid) == 1
        assert (yield m.outp.payload.sign) == sign.value

        if sign == Sign.UNSIGNED:
            assert (yield m.outp.payload.q) == q
            assert (yield m.outp.payload.r) == r
        else:
            assert (yield m.outp.payload.q.as_signed()) == q
            assert (yield m.outp.payload.r.as_signed()) == r

        yield
        assert (yield m.outp.valid) == 0

    return testbench


@pytest.fixture
def riscv_tb(sim_mod, n, d, q, r):
    _, m = sim_mod

    def testbench(delay):
        yield m.inp.payload.n.eq(n)
        yield m.inp.payload.d.eq(d)
        yield m.inp.payload.sign.eq(Sign.SIGNED)
        yield m.inp.valid.eq(1)
        yield

        yield m.inp.valid.eq(0)  # Only schedule one xfer.
        yield m.outp.ready.eq(1)  # Immediately ready for retrieval.
        yield
        for _ in range(delay):
            yield

        assert (yield m.outp.valid) == 1
        assert (yield m.outp.payload.q.as_signed()) == q
        assert (yield m.outp.payload.r.as_signed()) == r
        assert (yield m.outp.payload.sign) == Sign.SIGNED.value

        yield
        assert (yield m.outp.valid) == 0

    return testbench


@pytest.fixture
def signed_tb(sim_mod):
    _, m = sim_mod

    def testbench(delay):
        for n in range(-2**(m.width-1), 2**(m.width-1)):
            yield m.inp.payload.n.eq(n)
            for d in range(-2**(m.width-1), 2**(m.width-1)):
                yield m.inp.payload.d.eq(d)
                yield m.inp.payload.sign.eq(Sign.SIGNED)
                yield m.inp.valid.eq(1)
                yield

                yield m.inp.valid.eq(0)  # Only schedule one xfer.
                yield m.outp.ready.eq(1)  # Immediately ready for retrieval.
                yield
                for _ in range(delay):
                    yield

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
                    assert (yield m.outp.payload.q.as_signed()) == int(n / d)
                    assert (yield m.outp.payload.r.as_signed()) == fmod(n, d)

    return testbench


@pytest.fixture
def unsigned_tb(sim_mod):
    _, m = sim_mod

    def testbench(delay):
        for n in range(0, 2**m.width):
            yield m.inp.payload.n.eq(n)
            for d in range(0, 2**m.width):
                yield m.inp.payload.d.eq(d)
                yield m.inp.payload.sign.eq(Sign.UNSIGNED)
                yield m.inp.valid.eq(1)
                yield

                yield m.inp.valid.eq(0)  # Only schedule one xfer.
                yield m.outp.ready.eq(1)  # Immediately ready for retrieval.
                yield
                for _ in range(delay):
                    yield

                assert (yield m.outp.valid) == 1
                assert (yield m.outp.payload.sign) == Sign.UNSIGNED.value
                if d == 0:
                    assert (yield m.outp.payload.q.as_unsigned()) == \
                        2**m.width - 1
                    assert (yield m.outp.payload.r.as_unsigned()) == n
                else:
                    assert (yield m.outp.payload.q.as_unsigned()) == int(n / d)
                    assert (yield m.outp.payload.r.as_unsigned()) == fmod(n, d)

    return testbench



