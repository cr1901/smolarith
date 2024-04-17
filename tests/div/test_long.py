# amaranth: UnusedElaboratable=no

import pytest
from functools import partial
from smolarith.div import LongDivider, Sign


@pytest.mark.parametrize("n,d,q,r,sign", [(1362, 14, 97, 4, Sign.SIGNED),
                                          (-1362, 14, -97, -4, Sign.SIGNED),
                                          (1362, -14, -97, 4, Sign.SIGNED),
                                          (-1362, -14, 97, -4, Sign.SIGNED),
                                          (1362, 14, 97, 4, Sign.UNSIGNED),])
@pytest.mark.parametrize("mod,clks", [(LongDivider(12),
                                       1.0 / 12e6)]) 
def test_reference_div(sim, reference_tb):
    sim.run(testbenches=[partial(reference_tb, 11 - 1)])


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
@pytest.mark.parametrize("mod,clks", [(LongDivider(12),
                                       1.0 / 12e6)]) 
def test_signed_unsigned_mismatch(sim, mismatch_tb):
    sim.run(testbenches=[partial(mismatch_tb, 11 - 1)])


@pytest.mark.parametrize("n,d,q,r", [(-(2**31), -1, -(2**31), 0),
                                     (1, 0, -1, 1),
                                     (-1, 0, -1, -1),
                                     (0xff, 0, -1, 0xff)])
@pytest.mark.parametrize("mod,clks", [(LongDivider(32),
                                       1.0 / 12e6)]) 
def test_riscv_compliance(sim, riscv_tb):
    sim.run(testbenches=[partial(riscv_tb, 31 - 1)])


@pytest.mark.parametrize("mod,clks", [(LongDivider(8),
                                       1.0 / 12e6)]) 
def test_div_8bit_signed(sim, signed_tb):
    sim.run(testbenches=[partial(signed_tb, 7 - 1)])


@pytest.mark.parametrize("mod,clks", [(LongDivider(8),
                                       1.0 / 12e6)]) 
def test_div_8bit_unsigned(sim, unsigned_tb):
    sim.run(testbenches=[partial(unsigned_tb, 7 - 1)])
