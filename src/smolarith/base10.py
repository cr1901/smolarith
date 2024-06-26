"""Components for doing base-10 arithmetic and conversion."""

from enum import auto
import enum
import math

from amaranth import Cat, Module, Signal
from amaranth.lib.data import ArrayLayout
from amaranth.lib.wiring import In, Out, Component, connect, flipped
from amaranth.lib import stream


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
            "outp": Out(ArrayLayout(4, self.num_bcd_digits))
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
                    
            m.d.comb += self.outp[level].eq(
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
        
        m.d.comb += self.outp[level].eq(last_digit)

        return m


def binary_input_signature(width):
    """Create a parametric binary input data port.

    This function returns a :class:`~amaranth:amaranth.lib.stream.Signature`
    that's usable as a transfer initiator to a Binary-to-BCD converter. A
    conversion starts on the current cycle when both ``valid`` and ``rdy`` are
    asserted.

    Parameters
    ----------
    width : int
        Width in bits of the binary input.

    Returns
    -------
    :class:`~amaranth:amaranth.lib.stream.Signature`
        :py:`Signature(unsigned(width))`
    """
    return stream.Signature(width)


def _base1000_signature(num_digits):
    """Create a parametric Base1000 data port.

    This function returns a :class:`~amaranth:amaranth.lib.stream.Signature`
    that's usable as a transfer initiator **from** a Binary-to-Base1000
    converter.

    .. note:: For a core responding **to** a Binary-to-Base1000 converter,
              which is the typical use case, you will want to use this
              Signature with the :data:`~amaranth:amaranth.lib.wiring.In` flow,
              like so:

              .. doctest::

                  >>> from smolarith.base10 import _base1000_signature
                  >>> from amaranth.lib.wiring import Signature, In
                  >>> my_receiver_sig = Signature({
                  ...     "inp": In(_base1000_signature(num_digits=2))
                  ... })

    Parameters
    ----------
    num_digits : int
        Number of digits in the base-1000 output.

    Returns
    -------
    :class:`~amaranth:amaranth.lib.stream.Signature`
        :py:`Signature(ArrayLayout(10, num_digits))`.

        Each array element represents a Base-1000 number
        in base-2, where *it is assumed that each digit <= 999*.
    """
    return stream.Signature(ArrayLayout(10, num_digits))


def bcd_output_signature(num_digits):
    """Create a parametric BCD data output port.

    This function returns a :class:`~amaranth:amaranth.lib.wiring.Signature`
    that's usable as a transfer initiator **from** a Binary-to-BCD
    converter.

    .. note:: For a core responding **to** a Binary-to-BCD converter,
              which is the typical use case, you will want to use this
              Signature with the :data:`~amaranth:amaranth.lib.wiring.In` flow,
              like so:

              .. doctest::

                  >>> from smolarith.base10 import bcd_output_signature
                  >>> from amaranth.lib.wiring import Signature, In
                  >>> my_receiver_sig = Signature({
                  ...     "inp": In(bcd_output_signature(num_digits=2))
                  ... })

    Parameters
    ----------
    num_digits : int
        Number of digits in the BCD output.

    Returns
    -------
    :class:`amaranth:amaranth.lib.stream.Signature`
        :py:`Signature(ArrayLayout(4, num_digits))`

        Each array element represents a Packed BCD number
        in base-2, where *it is assumed that each digit <= 9*.
    """
    return stream.Signature(ArrayLayout(4, num_digits))


def _mac24(x, y):
    return 24*x + y


# H. C. Neto and M. P. Vestias, "Decimal multiplier on FPGA using embedded
# binary multipliers,"  2008 International Conference on Field Programmable
# Logic and Applications, Heidelberg, Germany, 2008, pp. 197-202,
# doi: 10.1109/FPL.2008.4629931.
class _B2ToB1000(Component):
    def __init__(self, pipeline_stages=3):
        self.pipeline_stages = pipeline_stages
        super().__init__({
            "inp": In(binary_input_signature(20)),
            "outp": Out(_base1000_signature(2))
        })

    def elaborate(self, plat):
        if self.pipeline_stages == 3:
            return self._pipelined_3(plat)
        else:
            raise NotImplementedError("_B2ToB1000 has not been implemented "
                                      f"with {self.pipeline_stages} pipeline "
                                      "stages")

    def _pipelined_3(self, plat):
        m = Module()

        b2 = Signal(10)
        c = Signal(15)
        d0_guess = Signal(11)
        d1_guess = Signal(10)

        valid = Signal(ArrayLayout(1, 2))
        not_stalled = Signal()

        with m.If(~self.outp.valid | self.outp.ready):
            m.d.comb += not_stalled.eq(1)
        m.d.comb += self.inp.ready.eq(not_stalled)

        m.d.sync += valid[0].eq(0)
        with m.If(not_stalled & self.inp.valid):
            m.d.sync += valid[0].eq(1)
            m.d.sync += b2.eq(self.inp.payload[10:])
            m.d.sync += c.eq(_mac24(self.inp.payload[10:],
                                    self.inp.payload[0:10]))

        with m.If(not_stalled):
            m.d.sync += [
                valid[1].eq(valid[0]),
                d0_guess.eq(_mac24(c[10:], c[:10])),
                d1_guess.eq(b2 + c[10:])
            ]

        with m.If(not_stalled):
            m.d.sync += self.outp.valid.eq(valid[1])

            with m.If(d0_guess > 999):
                m.d.sync += [
                    self.outp.payload[0].eq(d0_guess + 24),
                    self.outp.payload[1].eq(d1_guess + 1)
                ]
            with m.Else():
                m.d.sync += [
                    self.outp.payload[0].eq(d0_guess),
                    self.outp.payload[1].eq(d1_guess)
                ]

        return m


class BinaryToBCD(Component):
    class Limit(enum.Enum):
        LARGEST_POWER_10 = auto()
        ENTIRE_RANGE = auto()

    def __init__(self, width, limit=Limit.LARGEST_POWER_10):
        self.width = width
        self.num_bcd_digits = _base10_width(self.width)

        super().__init__({
            "inp": In(binary_input_signature(20)),
            "outp": Out(bcd_output_signature(self.num_bcd_digits))
        })

    def elaborate(self, plat):
        m = Module()

        # It's not worth using _B2ToB1000 for just 24 values for width == 10.
        if self.num_bcd_digits < 3 or \
                (BinaryToBCD.Limit.LARGEST_POWER_10 and self.width <= 10):
            dd = _DoubleDabble(self.width)
            m.submodules += dd
            m.d.comb += dd.inp.eq(self.inp.payload)

            m.d.comb += self.inp.ready.eq(~self.outp.valid | self.outp.ready)

            with m.If(self.outp.valid & self.outp.ready):
                m.d.sync += self.outp.valid.eq(0)

            with m.If(self.inp.valid & self.inp.ready):
                m.d.sync += [
                    self.outp.valid.eq(1),
                    self.outp.payload.eq(dd.outp)
                ]

        # Tolerate truncation
        elif (self.num_bcd_digits > 3 and self.num_bcd_digits <= 6) or \
                (BinaryToBCD.Limit.LARGEST_POWER_10 and self.width <= 20):
            b2b1000 = _B2ToB1000()
            dd0 = _DoubleDabble(10)
            dd1 = _DoubleDabble(10)

            m.submodules += dd0, dd1, b2b1000

            connect(m, flipped(self.inp), b2b1000.inp)

            m.d.comb += [
                dd0.inp.eq(b2b1000.outp.payload[0]),
                dd1.inp.eq(b2b1000.outp.payload[1])
            ]

            m.d.comb += b2b1000.outp.ready.eq(~self.outp.valid |
                                              self.outp.ready)

            with m.If(self.outp.valid & self.outp.ready):
                m.d.sync += self.outp.valid.eq(0)

            with m.If(b2b1000.outp.valid & b2b1000.outp.ready):
                m.d.sync += [
                    self.outp.valid.eq(1),
                    self.outp.payload[0].eq(dd0.outp[0]),
                    self.outp.payload[1].eq(dd0.outp[1]),
                    self.outp.payload[2].eq(dd0.outp[2]),
                ]

                for d in range(3, self.num_bcd_digits):
                    m.d.sync += self.outp.payload[d].eq(dd1.outp[d - 3])
        else:
            raise NotImplementedError

        return m
