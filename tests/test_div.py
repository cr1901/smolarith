import pytest
from smolarith.div import SignedDivider


@pytest.mark.module(SignedDivider(12))
@pytest.mark.clks((1.0 / 12e6,))
@pytest.mark.parametrize("a,n,q,r", [(1362, 14, 97, 4),
                                     (-1362, 14, -97, -4),
                                     (1362, -14, -97, 4),
                                     (-1362, -14, 97, -4)])
def test_reference_div(sim_mod, a, n, q, r):
    sim, m = sim_mod

    def testbench():
        yield m.inp.a.eq(a)
        yield m.inp.n.eq(n)
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

        yield
        assert (yield m.outp.valid) == 0

    sim.run(sync_processes=[testbench])


@pytest.mark.module(SignedDivider(32))
@pytest.mark.clks((1.0 / 12e6,))
@pytest.mark.parametrize("a,n,q,r", [(-(2**31), -1, -(2**31), 0),
                                     (1, 0, -1, 1),
                                     (0xff, 0, -1, 0xff)])
def test_riscv_compliance(sim_mod, a, n, q, r):
    sim, m = sim_mod

    def testbench():
        yield m.inp.a.eq(a)
        yield m.inp.n.eq(n)
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

        yield
        assert (yield m.outp.valid) == 0

    sim.run(sync_processes=[testbench])
