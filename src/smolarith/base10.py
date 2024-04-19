"""Components for doing base-10 arithmetic and conversion."""

import math

from amaranth import Cat, Elaboratable, Module, Signal, signed, C, unsigned
from amaranth.lib.data import StructLayout
from amaranth.lib.wiring import Signature, In, Out, Component
from amaranth.lib.enum import Enum, auto


def _base10_width(x):
    return math.ceil(math.log10(2**x))


# FIXME: All of this needs to be documented better...
# * DoubleDabble is base-2 Horner's method for base conversion, where the
#   representation in base 10 is BCD.
# * Horner's method alternates between multiplying and adding. The add
#   part either adds 0 or 1 to our running result. When coupled with the below
#   multiplies by 2, the add is morally equivalent to shifting in the MSB of
#   our binary number.
# * Multiplying by 2 in BCD is the same doing a BCD addition with the
#   value we currently have, so all multplies in Horner's method become BCD
#   adds.
# * BCD addition requires an add-6 step to carry over to the next digit if the
#   digit is > 9. This is equivalent to adding 3 before doubling our current
#   amount if the current digit is >= 5.
# * Once we have shifted all the binary digits, we are done; there is no
#   final multiply step after the final shift (it's a multiply by 2^0 :)).
class _DoubleDabble(Component):
    class _ShiftAdd3(Component):
        def __init__(self, *, final=False):
            self.final = final
            super().__init__({
                "cin": In(1),
                "inp": In(3),
                "outp": Out(3),
                "cout": Out(1)
            })

        def elaborate(self, platform):
            m = Module()
            shreg = Signal(4)
            shreg_plus3 = Signal(4)

            m.d.comb += [
                shreg.eq(Cat(self.cin, self.inp)),
                shreg_plus3.eq(shreg + 3),
                self.cout.eq(shreg[-1]),
                self.outp.eq(shreg[:-1])
            ]

            if not self.final:
                with m.If(shreg >= 5):
                    m.d.comb += [
                        self.cout.eq(shreg_plus3[-1]),
                        self.outp.eq(shreg_plus3[:-1])
                    ]

            return m

    def __init__(self, width, debug=False):
        if width <= 3:
            raise ValueError("BCD conversion is only meaningful for signals "
                             "of width 4 or greater")

        self.width = width
        self.num_bcd_digits = _base10_width(self.width)
        self.debug = debug

        if self.debug:
            print(self.num_bcd_digits)

        super().__init__({
            "inp": In(self.width),
            "outp": Out(4*self.num_bcd_digits)
        })

    def elaborate(self, plat):
        m = Module()

        sa3s = list()
        level = 0

        while level < self.num_bcd_digits - 1:
            # Optimization that removes some SA3s, based on pen-and-paper
            # sketches. The first 3 SA3s from each level can be merged into a
            # single SA3, because many of their inputs are set to 0. They will
            # never see values > 5, and thus all they do is shift.
            start_depth = 3*(level + 1) - 1
            num_sa3s_in_level = self.width - start_depth

            # Use a dictionary to make indexing easier.
            sa3s[level:] = [dict()]

            if self.debug:
                print(level, start_depth)

            if level == 0:
                root_sa3 = _DoubleDabble._ShiftAdd3()
                sa3s[level][start_depth] = root_sa3
                m.submodules[f"sa3_{level}_{start_depth}"] = root_sa3

                m.d.comb += [
                    sa3s[level][start_depth].inp.eq(Cat(self.inp[-2],
                                                        self.inp[-1],
                                                        0)),
                    sa3s[level][start_depth].cin.eq(self.inp[-3]),
                ]
            else:
                root_sa3 = _DoubleDabble._ShiftAdd3(final = 
                                                    (num_sa3s_in_level == 1))
                sa3s[level][start_depth] = root_sa3
                m.submodules[f"sa3_{level}_{start_depth}"] = root_sa3

                m.d.comb += [
                    sa3s[level][start_depth].inp.eq(
                        Cat(sa3s[level - 1][start_depth - 2].cout,
                            sa3s[level - 1][start_depth - 3].cout,
                            0)
                    ),
                    sa3s[level][start_depth].cin.eq(
                        sa3s[level - 1][start_depth - 1].cout),
                ]

            for i in range(start_depth + 1, start_depth + num_sa3s_in_level):
                is_final = (i == start_depth + num_sa3s_in_level - 1)

                if self.debug:
                    print(level, i, is_final)

                sa3 = _DoubleDabble._ShiftAdd3(final = is_final)
                sa3s[level][i] = sa3
                m.submodules[f"sa3_{level}_{i}"] = sa3

                m.d.comb += sa3s[level][i].inp.eq(sa3s[level][i - 1].outp)
                if level == 0:
                    m.d.comb += sa3s[level][i].cin.eq(self.inp[-i - 1])
                else:
                    m.d.comb += \
                        sa3s[level][i].cin.eq(sa3s[level - 1][i - 1].cout)
                    
            m.d.comb += self.outp[4*level:4*(level+1)].eq(
                Cat(sa3s[level][i].outp, sa3s[level][i].cout))

            level += 1

        last_digit = Signal(4)
        final_depth = self.width - 1

        if self.debug:
            print(num_sa3s_in_level)

        # Collect unused couts from last level into highest digit.
        for i in range(num_sa3s_in_level - 1):            
            m.d.comb += last_digit[i].eq(
                sa3s[level - 1][final_depth - i - 1].cout)
        
        m.d.comb += self.outp[4*level:4*(level+1)].eq(last_digit)

        return m
