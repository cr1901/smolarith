# smolarith

[![Documentation Status](https://readthedocs.org/projects/smolarith/badge/?version=latest)](https://smolarith.readthedocs.io/en/latest/?badge=latest)

Small arithmetic soft-cores for smol FPGAs. If your FPGA has hard IP
implementing functions in this repository, you should use those instead.

## Example

```python
from amaranth import signed, Module, C
from amaranth.lib.wiring import Component, Signature, Out, In
from amaranth.back.verilog import convert
from amaranth.sim import Simulator

import sys
from smolarith import mul
from smolarith.mul import MulticycleMul


class Celsius2Fahrenheit(Component):
    """Module to convert Celsius temperatures to Fahrenheit (F = 1.8*C + 32)."""

    def __init__(self, *, qc, qf, scale_const=5):
        self.qc = qc
        self.qf = qf
        self.scale_const = scale_const

        self.c_width = self.qc[0] + self.qc[1]
        self.f_width = self.qf[0] + self.qf[1]
        # 1.8 not representable. 1.78125 will have to be close enough.
        # Q1.{self.scale_const}
        self.mul_factor = C(9*2**self.scale_const // 5)
        # Q6.{self.qc[1] + self.scale_const}
        self.add_factor = C(32 << (self.qc[1] + self.scale_const))
        # Mul result will have self.qc[1] + self.scale_const fractional bits.
        # Adjust to desired Fahrenheit precision.
        self.extra_bits = self.qc[1] + self.scale_const - self.qf[1]

        # Output will be 2*max(self.mul_factor.width, self.c_width)...
        # more bits than we need.
        self.mul = MulticycleMul(width=max(self.mul_factor.width,
                                           self.c_width))

        super().__init__({
            "c": In(Signature({
                "payload": Out(signed(self.c_width)),
                "ready": In(1),
                "valid": Out(1)
            })),
            "f": Out(Signature({
                "payload": Out(signed(self.f_width)),
                "ready": In(1),
                "valid": Out(1)
            }))
        })

    def elaborate(self, plat):
        m = Module()
        m.submodules.mul = self.mul

        m.d.comb += [
            # res = 1.8*C
            self.c.ready.eq(self.mul.inp.ready),
            self.mul.inp.valid.eq(self.c.valid),
            self.mul.inp.payload.a.eq(self.c.payload),
            self.mul.inp.payload.b.eq(self.mul_factor),
            self.mul.inp.payload.sign.eq(mul.Sign.SIGNED_UNSIGNED),

            # F = res + 32, scaled to remove frac bits we don't need.
            self.f.payload.eq((self.mul.outp.payload.o + self.add_factor) >>
                              self.extra_bits),
            self.f.valid.eq(self.mul.outp.valid),
            self.mul.outp.ready.eq(self.f.ready)
        ]

        return m


def sim(*, c2f, start_c, end_c, gtkw=False):
    sim = Simulator(c2f)
    sim.add_clock(1e-6)

    def proc():
        yield c2f.f.ready.eq(1)
        yield

        for i in range(start_c, end_c):
            yield c2f.c.payload.eq(i)
            yield c2f.c.valid.eq(1)
            yield
            yield c2f.c.valid.eq(0)

            # Wait for module to calculate results.
            while (yield c2f.f.valid) != 1:
                yield

            # This is a low-effort attempt to print fixed-point numbers
            # by converting them into floating point.
            print((yield c2f.c.payload) / 2**c2f.qc[1],
                  (yield c2f.f.payload) / 2**c2f.qf[1])

    sim.add_sync_process(proc)

    if gtkw:
        with sim.write_vcd("c2f.vcd", "c2f.gtkw"):
            sim.run()
    else:
        sim.run()


if __name__ == "__main__":
    # See: https://en.wikipedia.org/wiki/Q_(number_format)
    c2f = Celsius2Fahrenheit(qc=(8, 3), qf=(10, 3), scale_const=15)

    if len(sys.argv) > 1 and sys.argv[1] == "sim":
        if len(sys.argv) >= 2:
            start_c = int(float(sys.argv[2]) * 2**c2f.qc[1])
        else:
            start_c = -2**(c2f.qc[0] + c2f.qc[1] - 1)

        if len(sys.argv) >= 3:
            end_c = int(float(sys.argv[3]) * 2**c2f.qc[1])
        else:
            end_c = 2**(c2f.qc[0] + c2f.qc[1] - 1)

        sim(c2f=c2f, start_c=start_c, end_c=end_c, gtkw=True)
    else:
        print(convert(c2f))
```
