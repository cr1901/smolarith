import pytest
from math import fmod
from smolarith.div import LongDivider, Sign


@pytest.mark.module(LongDivider(12))
@pytest.mark.clks((1.0 / 12e6,))
@pytest.mark.parametrize("n,d,q,r,sign", [(1362, 14, 97, 4, Sign.SIGNED),
                                          (-1362, 14, -97, -4, Sign.SIGNED),
                                          (1362, -14, -97, 4, Sign.SIGNED),
                                          (-1362, -14, 97, -4, Sign.SIGNED),
                                          (1362, 14, 97, 4, Sign.UNSIGNED),])
def test_reference_div(sim_mod, n, d, q, r, sign):
    sim, m = sim_mod

    def testbench():
        yield m.inp.data.n.eq(n)
        yield m.inp.data.d.eq(d)
        yield m.inp.data.sign.eq(sign)
        yield m.inp.valid.eq(1)
        yield

        yield m.inp.valid.eq(0)  # Only schedule one xfer.
        yield m.outp.rdy.eq(1)  # Immediately ready for retrieval.
        yield
        for _ in range(11):
            yield

        assert (yield m.outp.valid) == 1
        assert (yield m.outp.data.sign) == sign

        if (yield m.outp.data.sign) == Sign.UNSIGNED.value:
            assert (yield m.outp.data.q) == q
            assert (yield m.outp.data.r) == r
        else:
            assert (yield m.outp.data.q.as_signed()) == q
            assert (yield m.outp.data.r.as_signed()) == r

        yield
        assert (yield m.outp.valid) == 0

    sim.run(sync_processes=[testbench])


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
def test_signed_unsigned_mismatch(sim_mod, n, d, q, r, sign):
    sim, m = sim_mod

    def testbench():
        yield m.inp.data.n.eq(n)
        yield m.inp.data.d.eq(d)
        yield m.inp.data.sign.eq(sign)
        yield m.inp.valid.eq(1)
        yield

        yield m.inp.valid.eq(0)  # Only schedule one xfer.
        yield m.outp.rdy.eq(1)  # Immediately ready for retrieval.
        yield
        for _ in range(11):
            yield

        assert (yield m.outp.valid) == 1
        assert (yield m.outp.data.sign) == sign

        if sign == Sign.UNSIGNED.value:
            assert (yield m.outp.data.q) == q
            assert (yield m.outp.data.r) == r
        else:
            assert (yield m.outp.data.q.as_signed()) == q
            assert (yield m.outp.data.r.as_signed()) == r

        yield
        assert (yield m.outp.valid) == 0

    sim.run(sync_processes=[testbench])


@pytest.mark.module(LongDivider(32))
@pytest.mark.clks((1.0 / 12e6,))
@pytest.mark.parametrize("n,d,q,r", [(-(2**31), -1, -(2**31), 0),
                                     (1, 0, -1, 1),
                                     (-1, 0, -1, -1),
                                     (0xff, 0, -1, 0xff)])
def test_riscv_compliance(sim_mod, n, d, q, r):
    sim, m = sim_mod

    def testbench():
        yield m.inp.data.n.eq(n)
        yield m.inp.data.d.eq(d)
        yield m.inp.data.sign.eq(Sign.SIGNED)
        yield m.inp.valid.eq(1)
        yield

        yield m.inp.valid.eq(0)  # Only schedule one xfer.
        yield m.outp.rdy.eq(1)  # Immediately ready for retrieval.
        yield
        for _ in range(31):
            yield

        assert (yield m.outp.valid) == 1
        assert (yield m.outp.data.q.as_signed()) == q
        assert (yield m.outp.data.r.as_signed()) == r
        assert (yield m.outp.data.sign) == Sign.SIGNED

        yield
        assert (yield m.outp.valid) == 0

    sim.run(sync_processes=[testbench])


@pytest.mark.module(LongDivider(8))
@pytest.mark.clks((1.0 / 12e6,))
def test_div_8bit_signed(sim_mod):
    sim, m = sim_mod

    def testbench():
        for n in range(-2**(m.width-1), 2**(m.width-1)):
            yield m.inp.data.n.eq(n)
            for d in range(-2**(m.width-1), 2**(m.width-1)):
                yield m.inp.data.d.eq(d)
                yield m.inp.data.sign.eq(Sign.SIGNED)
                yield m.inp.valid.eq(1)
                yield

                yield m.inp.valid.eq(0)  # Only schedule one xfer.
                yield m.outp.rdy.eq(1)  # Immediately ready for retrieval.
                yield
                for _ in range(7):
                    yield

                assert (yield m.outp.valid) == 1
                assert (yield m.outp.data.sign) == Sign.SIGNED
                if n == -2**(m.width-1) and d == -1:
                    assert (yield m.outp.data.q.as_signed()) == -2**(m.width-1)
                    assert (yield m.outp.data.r.as_signed()) == 0
                elif d == 0:
                    assert (yield m.outp.data.q.as_signed()) == -1
                    assert (yield m.outp.data.r.as_signed()) == n
                else:
                    assert (yield m.outp.data.q.as_signed()) == int(n / d)
                    assert (yield m.outp.data.r.as_signed()) == fmod(n, d)

    sim.run(sync_processes=[testbench])


@pytest.mark.module(LongDivider(8))
@pytest.mark.clks((1.0 / 12e6,))
def test_div_8bit_unsigned(sim_mod):
    sim, m = sim_mod

    def testbench():
        for n in range(0, 2**m.width):
            yield m.inp.data.n.eq(n)
            for d in range(0, 2**m.width):
                yield m.inp.data.d.eq(d)
                yield m.inp.data.sign.eq(Sign.UNSIGNED)
                yield m.inp.valid.eq(1)
                yield

                yield m.inp.valid.eq(0)  # Only schedule one xfer.
                yield m.outp.rdy.eq(1)  # Immediately ready for retrieval.
                yield
                for _ in range(7):
                    yield

                assert (yield m.outp.valid) == 1
                assert (yield m.outp.data.sign) == Sign.UNSIGNED
                if d == 0:
                    assert (yield m.outp.data.q.as_unsigned()) == \
                        2**m.width - 1
                    assert (yield m.outp.data.r.as_unsigned()) == n
                else:
                    assert (yield m.outp.data.q.as_unsigned()) == int(n / d)
                    assert (yield m.outp.data.r.as_unsigned()) == fmod(n, d)

    sim.run(sync_processes=[testbench])
