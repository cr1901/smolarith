import pytest
from functools import partial
from smolarith.div import LongDivider, Sign


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


@pytest.mark.module(LongDivider(32))
@pytest.mark.clks((1.0 / 12e6,))
@pytest.mark.parametrize("n,d,q,r", [(-(2**31), -1, -(2**31), 0),
                                     (1, 0, -1, 1),
                                     (-1, 0, -1, -1),
                                     (0xff, 0, -1, 0xff)])
def test_riscv_compliance(sim_mod, riscv_tb):
    sim, _ = sim_mod
    sim.run(sync_processes=[partial(riscv_tb, 32 - 1)])


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
