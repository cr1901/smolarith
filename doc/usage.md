# `smolarith` Quickstart And Usage

## Installation

`smolarith` is available on [PyPI](https://pypi.org/p/smolarith/). Rather than
use `pip install smolarith` for a system-wide install, it is expected that you
will import `smolarith` as a dependency as part of a larger Amaranth project.

Using the [Amaranth template project](https://github.com/amaranth-lang/template-fpga)
as a reference, you would fork that template and then run:

```
pdm add smolarith
```

All commands which invoke the Python interpreter that `pdm` is using (probably
in a virtualenv) will now have access to `smolarith`.

## Usage
`smolarith` modules all use Amaranth {doc}`streams <amaranth:stdlib/stream>`.
Data transfer using Amaranth streams follow a minimal "valid-ready"
unidirectional protocol. Each `smolarith` module has at least
two streams:

* One stream where the `smolarith` module accepts data from an initiator/producer;
  i.e. the `smolarith` module is a responder/consumer.
* Another stream to return results from the module; i.e. the `smolarith` module
  is the initiator/producer.
  
Detailed rules for stream transfers are explained in the {ref}`Amaranth docs <amaranth:stream-rules>`.
Unless otherwise noted, all stream directions are from the initiatior's point-of-view.

Here is a self-contained example of a streaming core that uses {class}`~smolarith.mul.MulticycleMul`
to perform Celsius to Fahrenheit conversion, governed by the equation
{math}`F(t) = 1.8*C(t) + 32`:

```python
from amaranth import signed, Module, C
from amaranth.lib.wiring import Component, Out, In
from amaranth.lib.stream import Signature
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

        # Output will be 2*max(len(self.mul_factor), self.c_width)...
        # more bits than we need.
        self.mul = MulticycleMul(width=max(len(self.mul_factor),
                                           self.c_width))

        super().__init__({
            "c": In(Signature(signed(self.c_width))),
            "f": Out(Signature(signed(self.f_width))),
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

    async def tb(ctx):
        await ctx.tick()

        ctx.set(c2f.f.ready, 1)
        await ctx.tick()

        for i in range(start_c, end_c):
            ctx.set(c2f.c.payload, i)
            ctx.set(c2f.c.valid, 1)
            await ctx.tick()
            ctx.set(c2f.c.valid, 0)

            # Wait for module to calculate results.
            await ctx.tick().until(c2f.f.valid == 1)

            # This is a low-effort attempt to print fixed-point numbers
            # by converting them into floating point.
            print(ctx.get(c2f.c.payload) / 2**c2f.qc[1],
                  ctx.get(c2f.f.payload) / 2**c2f.qf[1])

    sim.add_testbench(tb)

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

        sim(c2f=c2f, start_c=start_c, end_c=end_c, gtkw=False)
    else:
        print(convert(c2f))
```

To run this code, copy and paste the above into a file called `c2f.py` at the
root of your forked template repo, and then run:

```sh
pdm run c2f.py sim -0.5 0.5
```

You should get output similar to the following, showing a working Celsius to
Fahrenheit converter!

```sh
-0.5 31.0
-0.375 31.25
-0.25 31.5
-0.125 31.75
0.0 32.0
0.125 32.125
0.25 32.375
0.375 32.625
```

<!-- This is the best way I've figured out to test the above code in a doctest,
I'm afraid... -->
```{testsetup}
from amaranth import signed, Module, C
from amaranth.lib.wiring import Component, Out, In
from amaranth.lib.stream import Signature
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

        # Output will be 2*max(len(self.mul_factor), self.c_width)...
        # more bits than we need.
        self.mul = MulticycleMul(width=max(len(self.mul_factor),
                                           self.c_width))

        super().__init__({
            "c": In(Signature(signed(self.c_width))),
            "f": Out(Signature(signed(self.f_width))),
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

    async def tb(ctx):
        await ctx.tick()

        ctx.set(c2f.f.ready, 1)
        await ctx.tick()

        for i in range(start_c, end_c):
            ctx.set(c2f.c.payload, i)
            ctx.set(c2f.c.valid, 1)
            await ctx.tick()
            ctx.set(c2f.c.valid, 0)

            # Wait for module to calculate results.
            await ctx.tick().until(c2f.f.valid == 1)

            # This is a low-effort attempt to print fixed-point numbers
            # by converting them into floating point.
            print(ctx.get(c2f.c.payload) / 2**c2f.qc[1],
                  ctx.get(c2f.f.payload) / 2**c2f.qf[1])

    sim.add_testbench(tb)

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

        sim(c2f=c2f, start_c=start_c, end_c=end_c, gtkw=False)
    else:
        print(convert(c2f))
```

```{testcode}
:hide:
c2f = Celsius2Fahrenheit(qc=(8, 3), qf=(10, 3), scale_const=15)
sim(c2f=c2f, start_c=-4, end_c=4, gtkw=False)
```

```{testoutput}
:hide:
-0.5 31.0
-0.375 31.25
-0.25 31.5
-0.125 31.75
0.0 32.0
0.125 32.125
0.25 32.375
0.375 32.625
```
