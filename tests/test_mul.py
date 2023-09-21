
import pytest
from smolarith.mul import PipelinedMul, PipelinedMulSigned, \
    PipelinedMulSignedUnsigned
from collections import deque


@pytest.mark.module(PipelinedMul(8))
@pytest.mark.clks((1.0 / 12e6,))
def test_pipelined_mul(sim_mod):
    sim, m = sim_mod

    def testbench():
        # Pipeline previous inputs... inputs to prev.append() are what
        # will go into the multiplier at the next active edge.
        # Outputs from prev.popleft()  are what went into the multiplier
        # "m.width - 1" active edges ago. This leads to a latency of
        # "m.width" clock cycles/ticks since the multiplier saw the inputs.
        prev = deque([(0, 0)]*m.width)

        for a in range(0, 2**m.width):
            print(a)
            yield m.a.eq(a)
            for b in range(0, 2**m.width):
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

    sim.run(sync_processes=[testbench])


@pytest.mark.module(PipelinedMulSigned(8, debug=True))
@pytest.mark.clks((1.0 / 12e6,))
def test_pipelined_mul_signed(sim_mod):
    sim, m = sim_mod

    def testbench():
        # Pipeline previous inputs... inputs to prev.append() are what
        # will go into the multiplier at the next active edge.
        # Outputs from prev.popleft()  are what went into the multiplier
        # "m.width - 1" active edges ago. This leads to a latency of
        # "m.width" clock cycles/ticks since the multiplier saw the inputs.
        prev = deque([(0, 0)]*m.width)

        for a in range(-2**(m.width-1), 2**(m.width-1)):
            yield m.a.eq(a)
            for b in range(-2**(m.width-1), 2**(m.width-1)):
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

    sim.run(sync_processes=[testbench])


@pytest.mark.module(PipelinedMulSignedUnsigned(8, debug=True))
@pytest.mark.clks((1.0 / 12e6,))
def test_pipelined_mul_signed_unsigned(sim_mod):
    sim, m = sim_mod

    def testbench():
        # Pipeline previous inputs... inputs to prev.append() are what
        # will go into the multiplier at the next active edge.
        # Outputs from prev.popleft()  are what went into the multiplier
        # "m.width - 1" active edges ago. This leads to a latency of
        # "m.width" clock cycles/ticks since the multiplier saw the inputs.
        prev = deque([(0, 0)]*m.width)

        for a in range(-2**(m.width-1), 2**(m.width-1)):
            yield m.a.eq(a)
            for b in range(0, 2**m.width):
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

    sim.run(sync_processes=[testbench])
