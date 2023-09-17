from amaranth import Elaboratable, Module, Signal, signed, unsigned, C
from amaranth.lib.wiring import Signature, In, Out, Component

amsigned = signed


def divider_input_signature(width, signed=False):
    shape_cls = amsigned if signed else unsigned

    return Signature({
        "a": Out(shape_cls(width)),  # Dividend
        "n": Out(shape_cls(width)),  # Divisor
        "rdy": In(1),
        "valid": Out(1)
    })


def divider_output_signature(width, signed=False):
    shape_cls = amsigned if signed else unsigned

    return Signature({
        "q": Out(shape_cls(width)),
        "r": Out(shape_cls(width)),
        "rdy": In(1),
        "valid": Out(1)
    })


class SignedDivider(Component):
    @property
    def signature(self):
        return Signature({
            "inp": In(divider_input_signature(self.width, signed=True)),
            "outp": Out(divider_output_signature(self.width, signed=True))
        })

    def __init__(self, width=8):
        self.width = width
        super().__init__()

    def elaborate(self, platform):
        m = Module()

        m.submodules.mag = mag = MagnitudeComparator(2*self.width)

        quotient = Signal(2*self.width)
        remainder = Signal(2*self.width)
        iters_left = Signal(range(self.width))
        in_progress = Signal()
        a_sign = Signal()
        n_sign = Signal()

        # Reduce latency by 1 cycle by preempting output being read.
        m.d.comb += self.inp.rdy.eq((self.outp.rdy & self.outp.valid) |
                                    ~in_progress)
        m.d.comb += in_progress.eq(iters_left != 0)
        m.d.comb += [
            self.outp.q.eq(quotient),
            self.outp.r.eq(remainder),
        ]

        with m.If(self.outp.rdy & self.outp.valid):
            m.d.sync += self.outp.valid.eq(0)

        with m.If(self.inp.rdy & self.inp.valid):
            m.d.sync += [
                # We handle first cycle using shift_amt mux.
                iters_left.eq(self.width - 1),
                a_sign.eq(self.inp.a[-1]),
                n_sign.eq(self.inp.n[-1]),
            ]

            # When dividing by 0, for RISCV compliance, we need the division to
            # return -1. Without redirecting quotient calculation to the
            # "both dividend/divisor positive" case, dividing a negative
            # number by 0 returns 1. Note that the sign-bit
            # processing doesn't need to be special-cased.
            with m.If(self.inp.n == 0 & self.inp.a[-1]):
                m.d.sync += a_sign.eq(0)
                m.d.sync += n_sign.eq(0)

            # We are committed to do a calc at this point, so might as well
            # start it now.
            #
            # Division quick refresh:
            #
            # Dividend / Divisor = Quotient
            # Dividend % Divisor = Remainder (takes the sign of the Dividend)
            #
            #         Quotient
            # Divisor)Dividend
            #         Remainder
            #
            # We're doing binary long division in hardware.
            # If starting with a positive dividend, we want to subtract
            # positive numbers from the dividend until we get as close to 0
            # without going below.
            # If '' negative dividend '' subtract negative numbers ''  as close
            # to 0 without going above. This becomes the remainder.
            #
            # We create the numbers to subtract from the dividend by
            # multiplying the divisor by either positive or negative powers
            # of two (shifting), depending on the sign of both the dividend
            # and divisor. When we add powers all of these two together, we
            # get the quotient.
            #
            # Either way, we can only subtract a shifted divisor from the
            # dividend if:
            #
            # * divisor*2**n <= dividend if dividend is positive.
            # * -divisor*2**n >= dividend if dividend is negative.
            #
            # We can use a magnitude comparator for this.

            shift_amt = 2**(self.width - 1)
            m.d.comb += [
                mag.divisor.eq(self.inp.n * shift_amt),
                mag.dividend.eq(self.inp.a)
            ]

            with m.If(mag.o):
                # If dividend/divisor are positive, subtract a positive
                # shifted divisor from dividend.
                with m.If(~self.inp.a[-1] & ~self.inp.n[-1] |
                          (self.inp.n == 0 & self.inp.a[-1])):
                    m.d.sync += quotient.eq(C(1) * shift_amt)
                    m.d.sync += remainder.eq(self.inp.a -
                                             (self.inp.n * C(1) * shift_amt))  # noqa: E501
                # If dividend is negative, but divisor is positive, create a
                # negative shifted divisor and subtract from the dividend.
                with m.If(self.inp.a[-1] & ~self.inp.n[-1] &
                          ~(self.inp.n == 0 & self.inp.a[-1])):
                    m.d.sync += quotient.eq(C(-1) * shift_amt)
                    m.d.sync += remainder.eq(self.inp.a -
                                             (self.inp.n * C(-1) * shift_amt))  # noqa: E501
                # If dividend is positive, but divisor is negative, create a
                # positive shifted divisor and subtract from the dividend.
                with m.If(~self.inp.a[-1] & self.inp.n[-1]):
                    m.d.sync += quotient.eq(C(-1) * shift_amt)
                    m.d.sync += remainder.eq(self.inp.a -
                                             (self.inp.n * C(-1) * shift_amt))  # noqa: E501
                # If dividend/divisor is negative, subtract a negative
                # shifted divisor and subtract from the dividend.
                with m.If(self.inp.a[-1] & self.inp.n[-1]):
                    m.d.sync += quotient.eq(C(1) * shift_amt)
                    m.d.sync += remainder.eq(self.inp.a -
                                             (self.inp.n * C(1) * shift_amt))  # noqa: E501
            with m.Else():
                m.d.sync += quotient.eq(0)
                m.d.sync += remainder.eq(self.inp.a)

        # Main division loop.
        with m.If(in_progress):
            m.d.sync += iters_left.eq(iters_left - 1)

            shift_amt = (1 << (iters_left - 1).as_unsigned())
            m.d.comb += [
                mag.divisor.eq(self.inp.n * shift_amt),
                mag.dividend.eq(remainder)
            ]

            with m.If(mag.o):
                # If dividend/divisor are positive, subtract a positive
                # shifted divisor from dividend.
                with m.If(~a_sign & ~n_sign):
                    m.d.sync += quotient.eq(quotient + C(1) * shift_amt)
                    m.d.sync += remainder.eq(remainder -
                                             (self.inp.n * C(1) * shift_amt))  # noqa: E501
                # If dividend is negative, but divisor is positive, create a
                # negative shifted divisor and subtract from the dividend.
                with m.If(a_sign & ~n_sign):
                    m.d.sync += quotient.eq(quotient + C(-1) * shift_amt)
                    m.d.sync += remainder.eq(remainder -
                                             (self.inp.n * C(-1) * shift_amt))  # noqa: E501
                # If dividend is positive, but divisor is negative, create a
                # positive shifted divisor and subtract from the dividend.
                with m.If(~a_sign & n_sign):
                    m.d.sync += quotient.eq(quotient + C(-1) * shift_amt)
                    m.d.sync += remainder.eq(remainder -
                                             (self.inp.n * C(-1) * shift_amt))  # noqa: E501
                # If dividend/divisor are negative, subtract a negative
                # shifted divisor from dividend.
                with m.If(a_sign & n_sign):
                    m.d.sync += quotient.eq(quotient + C(1) * shift_amt)
                    m.d.sync += remainder.eq(remainder -
                                             (self.inp.n * C(1) * shift_amt))  # noqa: E501

            with m.If(iters_left - 1 == 0):
                m.d.sync += self.outp.valid.eq(1)

        return m


class MagnitudeComparator(Elaboratable):
    def __init__(self, width=8):
        self.width = width
        self.dividend = Signal(signed(self.width))
        self.divisor = Signal(signed(self.width))
        self.o = Signal()

    def elaborate(self, platform):
        m = Module()

        m.d.comb += self.o.eq(abs(self.divisor) <= abs(self.dividend))

        return m
