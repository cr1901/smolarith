import pytest
from smolarith.mul import PipelinedMul, PipelinedMulSigned, \
    PipelinedMulSignedUnsigned
from collections import deque


@pytest.fixture
def all_values_tb(request, sim_mod):
    _, m = sim_mod
    mode = request.param

    if mode == "unsigned":
        a_range = range(0, 2**m.width)
        b_range = range(0, 2**m.width)
    elif mode == "signed":
        a_range = range(-2**(m.width-1), 2**(m.width-1))
        b_range = range(-2**(m.width-1), 2**(m.width-1))
    elif mode == "signed-unsigned":
        a_range = range(-2**(m.width-1), 2**(m.width-1))
        b_range = range(0, 2**m.width)
    else:
        raise ValueError("mode must be one of: \"unsigned\", \"signed\", or"
                         f" \"signed-unsigned\", not {mode}")

    def testbench():
        # Pipeline previous inputs... inputs to prev.append() are what
        # will go into the multiplier at the next active edge.
        # Outputs from prev.popleft()  are what went into the multiplier
        # "m.width - 1" active edges ago. This leads to a latency of
        # "m.width" clock cycles/ticks since the multiplier saw the inputs.
        prev = deque([(0, 0)]*m.width)

        for a in a_range:
            yield m.a.eq(a)
            for b in b_range:
                yield m.b.eq(b)

                yield
                (a_c, b_c) = prev.popleft()
                prev.append((a, b))

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

            assert a_c*b_c == (yield m.o)

    return testbench


@pytest.mark.clks((1.0 / 12e6,))
@pytest.mark.parametrize("all_values_tb",
                         [pytest.param("unsigned",
                                       marks=pytest.mark.module(PipelinedMul(8, debug=True))),  # noqa: E501
                          pytest.param("signed",
                                       marks=pytest.mark.module(PipelinedMulSigned(8, debug=True))),  # noqa: E501
                          pytest.param("signed-unsigned",
                                       marks=pytest.mark.module(PipelinedMulSignedUnsigned(8, debug=True)))],  # noqa: E501
                         indirect=True)
def test_pipelined_mul(sim_mod, all_values_tb):
    sim, m = sim_mod
    sim.run(sync_processes=[all_values_tb])
