import pytest
from math import fmod
from smolarith.div import SignedDivider


@pytest.mark.module(SignedDivider(12))
@pytest.mark.clks((1.0 / 12e6,))
@pytest.mark.parametrize("a,n,q,r,signed", [(1362, 14, 97, 4, True),
                                            (-1362, 14, -97, -4, True),
                                            (1362, -14, -97, 4, True),
                                            (-1362, -14, 97, -4, True),
                                            (1362, 14, 97, 4, False),])
def test_reference_div(sim_mod, a, n, q, r, signed):
    sim, m = sim_mod

    def testbench():
        yield m.inp.a.eq(a)
        yield m.inp.n.eq(n)
        yield m.inp.signed.eq(signed)
        yield m.inp.valid.eq(1)
        yield

        yield m.inp.valid.eq(0)  # Only schedule one xfer.
        yield m.outp.rdy.eq(1)  # Immediately ready for retrieval.
        yield
        for _ in range(11):
            yield

        assert (yield m.outp.valid) == 1
        assert (yield m.outp.q) == q
        assert (yield m.outp.r) == r
        assert (yield m.outp.signed) == signed

        yield
        assert (yield m.outp.valid) == 0

    sim.run(sync_processes=[testbench])


@pytest.mark.module(SignedDivider(12))
@pytest.mark.clks((1.0 / 12e6,))
@pytest.mark.parametrize("a,n,q,r,signed", [
                                            # 100000000001
                                            (2049, 2, 1024, 1, False),
                                            # 100000000001
                                            (-2047, 2, -1023, -1, True),
                                            # 011111111111
                                            (2047, 2, 1023, 1, False),
                                            # 011111111111
                                            (2047, 2, 1023, 1, True)])
def test_signed_unsigned_mismatch(sim_mod, a, n, q, r, signed):
    sim, m = sim_mod

    def testbench():
        yield m.inp.a.eq(a)
        yield m.inp.n.eq(n)
        yield m.inp.signed.eq(signed)
        yield m.inp.valid.eq(1)
        yield

        yield m.inp.valid.eq(0)  # Only schedule one xfer.
        yield m.outp.rdy.eq(1)  # Immediately ready for retrieval.
        yield
        for _ in range(11):
            yield

        assert (yield m.outp.valid) == 1
        assert (yield m.outp.q) == q
        assert (yield m.outp.r) == r
        assert (yield m.outp.signed) == signed

        yield
        assert (yield m.outp.valid) == 0

    sim.run(sync_processes=[testbench])


@pytest.mark.module(SignedDivider(32))
@pytest.mark.clks((1.0 / 12e6,))
@pytest.mark.parametrize("a,n,q,r", [(-(2**31), -1, -(2**31), 0),
                                     (1, 0, -1, 1),
                                     (-1, 0, -1, -1),
                                     (0xff, 0, -1, 0xff)])
def test_riscv_compliance(sim_mod, a, n, q, r):
    sim, m = sim_mod

    def testbench():
        yield m.inp.a.eq(a)
        yield m.inp.n.eq(n)
        yield m.inp.signed.eq(1)
        yield m.inp.valid.eq(1)
        yield

        yield m.inp.valid.eq(0)  # Only schedule one xfer.
        yield m.outp.rdy.eq(1)  # Immediately ready for retrieval.
        yield
        for _ in range(31):
            yield

        assert (yield m.outp.valid) == 1
        assert (yield m.outp.q) == q
        assert (yield m.outp.r) == r
        assert (yield m.outp.signed) == 1

        yield
        assert (yield m.outp.valid) == 0

    sim.run(sync_processes=[testbench])


@pytest.mark.module(SignedDivider(8))
@pytest.mark.clks((1.0 / 12e6,))
def test_div_8bit_signed(sim_mod):
    sim, m = sim_mod

    def testbench():
        # Pipeline previous inputs... inputs to prev.append() are what
        # will go into the multiplier at the next active edge.
        # Outputs from prev.popleft()  are what went into the multiplier
        # "m.width - 1" active edges ago. This leads to a latency of
        # "m.width" clock cycles/ticks since the multiplier saw the inputs.

        for a in range(-2**(m.width-1), 2**(m.width-1)):
            yield m.inp.a.eq(a)
            for n in range(-2**(m.width-1), 2**(m.width-1)):
                yield m.inp.n.eq(n)
                yield m.inp.signed.eq(1)
                yield m.inp.valid.eq(1)
                yield

                yield m.inp.valid.eq(0)  # Only schedule one xfer.
                yield m.outp.rdy.eq(1)  # Immediately ready for retrieval.
                yield
                for _ in range(7):
                    yield

                assert (yield m.outp.valid) == 1
                assert (yield m.outp.signed) == 1
                if a == -2**(m.width-1) and n == -1:
                    assert (yield m.outp.q) == -2**(m.width-1)
                    assert (yield m.outp.r) == 0
                elif n == 0:
                    assert (yield m.outp.q) == -1
                    assert (yield m.outp.r) == a
                else:
                    assert (yield m.outp.q) == int(a / n)
                    assert (yield m.outp.r) == fmod(a, n)

    sim.run(sync_processes=[testbench])


@pytest.mark.module(SignedDivider(8))
@pytest.mark.clks((1.0 / 12e6,))
def test_div_8bit_unsigned(sim_mod):
    sim, m = sim_mod

    def testbench():
        # Pipeline previous inputs... inputs to prev.append() are what
        # will go into the multiplier at the next active edge.
        # Outputs from prev.popleft()  are what went into the multiplier
        # "m.width - 1" active edges ago. This leads to a latency of
        # "m.width" clock cycles/ticks since the multiplier saw the inputs.

        for a in range(0, 2**m.width):
            yield m.inp.a.as_unsigned().eq(a)
            for n in range(0, 2**m.width):
                yield m.inp.n.as_unsigned().eq(n)
                yield m.inp.signed.eq(0)
                yield m.inp.valid.eq(1)
                yield

                yield m.inp.valid.eq(0)  # Only schedule one xfer.
                yield m.outp.rdy.eq(1)  # Immediately ready for retrieval.
                yield
                for _ in range(7):
                    yield

                assert (yield m.outp.valid) == 1
                assert (yield m.outp.signed) == 0
                if n == 0:
                    assert (yield m.outp.q.as_unsigned()) == 2**m.width - 1
                    assert (yield m.outp.r.as_unsigned()) == a
                else:
                    assert (yield m.outp.q.as_unsigned()) == int(a / n)
                    assert (yield m.outp.r.as_unsigned()) == fmod(a, n)

    sim.run(sync_processes=[testbench])
