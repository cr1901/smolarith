import pytest
from math import fmod
from functools import partial
from smolarith.div import LongDivider, Sign, MulticycleDiv


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
                    assert (yield m.outp.payload.q.as_signed()) == -2**(m.width-1)
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


@pytest.mark.module(LongDivider(12))
@pytest.mark.clks((1.0 / 12e6,))
@pytest.mark.parametrize("n,d,q,r,sign", [(1362, 14, 97, 4, Sign.SIGNED),
                                          (-1362, 14, -97, -4, Sign.SIGNED),
                                          (1362, -14, -97, 4, Sign.SIGNED),
                                          (-1362, -14, 97, -4, Sign.SIGNED),
                                          (1362, 14, 97, 4, Sign.UNSIGNED),])
def test_reference_div(sim_mod, reference_tb):
    sim, _ = sim_mod
    sim.run(sync_processes=[partial(reference_tb, 12 - 1)])


@pytest.mark.module(MulticycleDiv(12))
@pytest.mark.clks((1.0 / 12e6,))
@pytest.mark.parametrize("n,d,q,r,sign", [(1362, 14, 97, 4, Sign.SIGNED),
                                          (-1362, 14, -97, -4, Sign.SIGNED),
                                          (1362, -14, -97, 4, Sign.SIGNED),
                                          (-1362, -14, 97, -4, Sign.SIGNED),
                                          (1362, 14, 97, 4, Sign.UNSIGNED),])
def test_reference_div_nr(sim_mod, reference_tb):
    sim, _ = sim_mod
    sim.run(sync_processes=[partial(reference_tb, 15 - 1)])


@pytest.mark.module(LongDivider(12))
@pytest.mark.clks((1.0 / 12e6,))
@pytest.mark.parametrize("n,d,q,r,sign", [
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
    (2047, 2, 1023, 1, Sign.SIGNED)])
def test_signed_unsigned_mismatch(sim_mod, mismatch_tb):
    sim, _ = sim_mod
    sim.run(sync_processes=[partial(mismatch_tb, 12 - 1)])


@pytest.mark.module(MulticycleDiv(12))
@pytest.mark.clks((1.0 / 12e6,))
@pytest.mark.parametrize("n,d,q,r,sign", [
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
    (2047, 2, 1023, 1, Sign.SIGNED)])
def test_signed_unsigned_mismatch_nr(sim_mod, mismatch_tb):
    sim, _ = sim_mod
    sim.run(sync_processes=[partial(mismatch_tb, 15 - 1)])


@pytest.mark.module(LongDivider(32))
@pytest.mark.clks((1.0 / 12e6,))
@pytest.mark.parametrize("n,d,q,r", [(-(2**31), -1, -(2**31), 0),
                                     (1, 0, -1, 1),
                                     (-1, 0, -1, -1),
                                     (0xff, 0, -1, 0xff)])
def test_riscv_compliance(sim_mod, riscv_tb):
    sim, _ = sim_mod
    sim.run(sync_processes=[partial(riscv_tb, 32 - 1)])


@pytest.mark.module(MulticycleDiv(32))
@pytest.mark.clks((1.0 / 12e6,))
@pytest.mark.parametrize("n,d,q,r", [(-(2**31), -1, -(2**31), 0),
                                     (1, 0, -1, 1),
                                     (-1, 0, -1, -1),
                                     (0xff, 0, -1, 0xff)])
def test_riscv_compliance_nr(sim_mod, riscv_tb):
    sim, _ = sim_mod
    sim.run(sync_processes=[partial(riscv_tb, 35 - 1)])


@pytest.mark.module(LongDivider(8))
@pytest.mark.clks((1.0 / 12e6,))
def test_div_8bit_signed(sim_mod, signed_tb):
    sim, _ = sim_mod
    sim.run(sync_processes=[partial(signed_tb, 8 - 1)])


@pytest.mark.module(LongDivider(8))
@pytest.mark.clks((1.0 / 12e6,))
def test_div_8bit_unsigned(sim_mod, unsigned_tb):
    sim, m = sim_mod
    sim.run(sync_processes=[partial(unsigned_tb, 8 - 1)])


@pytest.mark.module(MulticycleDiv(8))
@pytest.mark.clks((1.0 / 12e6,))
def test_div_8bit_signed_nr(sim_mod, signed_tb):
    sim, _ = sim_mod
    sim.run(sync_processes=[partial(signed_tb, 11 - 1)])


@pytest.mark.module(MulticycleDiv(8))
@pytest.mark.clks((1.0 / 12e6,))
def test_div_8bit_unsigned_nr(sim_mod, unsigned_tb):
    sim, m = sim_mod
    sim.run(sync_processes=[partial(unsigned_tb, 11 - 1)])
