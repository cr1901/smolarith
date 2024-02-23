"""Soft-core multiplier components."""

from amaranth import Elaboratable, Module, Signal, signed, unsigned, Mux, Cat  
from amaranth.lib.data import ArrayLayout, StructLayout, UnionLayout
from amaranth.lib.wiring import Signature, In, Out, Component

from amaranth.lib.enum import Enum, auto


class Sign(Enum):
    """Indicate the signedness of multiplier inputs.

    * ``UNSIGNED``: Both inputs ``a`` and ``b`` are unsigned.
      
      The output is unsigned.

    * ``SIGNED``: Both inputs ``a`` and ``b`` are unsigned.
      
      The output is signed.

    * ``SIGNED_UNSIGNED``: Input ``a`` is signed and input ``b`` is unsigned.
      
      The output is signed.
       
      Note that for :math:`n`-bit multiply with given bit patterns for ``a``
      and ``b``, the bottom :math:`n/2` bits will be identical in an
      ``UNSIGNED`` or ``SIGNED_UNSIGNED`` multiply.
    """

    UNSIGNED = auto()
    SIGNED = auto()
    SIGNED_UNSIGNED = auto()


class SignedOrUnsigned(UnionLayout):
    def __init__(self, width):
        super().__init__({
            "u": unsigned(width),
            "i": signed(width)
        })


class Inputs(StructLayout):
    def __init__(self, width):
        super().__init__({
            "sign": Sign,
            "a": SignedOrUnsigned(width),
            "b": SignedOrUnsigned(width),
        })


class Outputs(StructLayout):
    def __init__(self, width):
        super().__init__({
            "sign": Sign,
            "o": SignedOrUnsigned(width),
        })


def multiplier_input_signature(width):
    return Signature({
        "data": Out(Inputs(width)),
        "rdy": In(1),
        "valid": Out(1)
    })


def multiplier_output_signature(width):
    return Signature({
        "data": Out(Outputs(width)),
        "rdy": In(1),
        "valid": Out(1)
    })



class PipelinedMul(Component):
    r"""Multiplier soft-core which pipelines inputs.
     
    This multiplier core has pipeline registers that stores intermediate
    results for up to ``width`` multiplies at once. Currently there is no
    control flow to stall multiplies in flight, so the output is always valid.

    .. todo::

        Add control flow, and update to Amaranth streams when available.
    
    * Latency: Multiply Results for a given multiply will be available
      ``width`` clock cycles after the multiplier has seen those inputs.
    
    * Throughput: One multiply is finished per clock cycle.

    Parameters
    ----------
    width : int
        Width in bits of both inputs ``a`` and ``b``. For signed
        multiplies, this includes the sign bit. Output ``o`` width will
        be :math:`2*n`.
    debug : int, optional
        Enable debugging signals.

    Attributes
    ----------
    width : int
        Bit with of the inputs ``a`` and ``b``. Output ``o`` width will
        be :math:`2*n`.
    a : ~amaranth.lib.hdl.Signal
        Shape :class:`~amaranth:amaranth.hdl.signed`, in. ``a`` input to
        multiplier; i.e. the multiplicand.
    b : ~amaranth.lib.hdl.Signal
        Shape :class:`~amaranth:amaranth.hdl.signed`, in. ``b`` input to
        multiplier; i.e. the multiplier.
    o : ~amaranth.lib.hdl.Signal
        Shape :class:`~amaranth:amaranth.hdl.signed`, out. ``o`` output of
        multiplier; i.e. the product.
    sign : ~amaranth.lib.hdl.Signal
        Shape :class:`Sign`, in. Configure whether the multiplication which
        starts next clock cycle is unsigned, signed, or signed-unsigned.
    sign_out : ~amaranth.lib.hdl.Signal
        Shape :class:`Sign`, out. Indicates whether the ``o`` output of the
        multiply which finished this clock cycle should be interpreted as
        unsigned, signed, or signed-unsigned.
    debug: bool
        Flag which indicates whether internal debugging :class:`Signal`\s are
        enabled or not.

    Notes
    -----
    This multiplier is a naive shift-add implementation, similar to how
    pen-and-pad multiplication in base-2/10 works. Internally, the multiplier
    treats the multiplier ``a`` as signed and the multiplicand ``b`` as
    unsigned.
     
    ``a``'s signedness only matters for the most-negative value possible for a
    given bit-width :math:`n`, where twos-complementing would not change the
    bit-pattern. Therefore, `a` is
    :ref:`automatically <amaranth:lang-widthext>` sign-extended to
    :math:`n + 1` bits in the input stage before any further processing.
     
    If ``b`` is negative, both ``b`` and ``a`` are twos-complemented in the
    input stage; since :math:`a * b = -a * -b`, no inverse transformation on
    the output stage is needed.

    For an :math:`n`-bit multiply, this multiplier requires :math:`O(n^2)`
    storage elements (to store intermediate results).

    Future Directions
    -----------------

    It is :ref:`possible <karatsuba>` to implement a :math:`2*n`-bit
    multiply using 3 :math:`n`-bit multiplies. Since this library is about
    *smol* arithmetic, it may be worthwhile to create classes for Karatsuba
    multipliers.

    Larger multpliers using a smaller :class:`PipelinedMul` will still
    potentially be quite fast :).
    """  

    def __init__(self, width=16, debug=False):
        self.width = width
        super().__init__({
            "inp": In(multiplier_input_signature(self.width)),
            "outp": Out(multiplier_output_signature(2*self.width))
        })
        self.debug = debug

    #   Unsigned, signed-unsigned case. The actual formula is the same
    #   in both cases (aside from interpretation of the bit patterns), because
    #   adding shifted copies of "x" works the same regardless of whether "x"
    #   is positive or negative:
    #
    #   twoscomp(x) + twoscomp(y) = (2^n - x) + (2^n - y) =
    #   2^(n + 1) - (x + y) = twocomp(x + y) with an additional bit.
    #
    #                   x7x6x5x4x3x2x1x0
    #                 * y7y6y5y4y3y2y1y0
    #                   ----------------
    #                   x7x6x5x4x3x2x1x0: z0 = x7x6x5x4x3x2x1x0*y0
    #                 x7x6x5x4x3x2x1x0: z1 = (x7x6x5x4x3x2x1x0*y1 << 1) + z0
    #               x7x6x5x4x3x2x1x0: z2 = (x7x6x5x4x3x2x1x0*y2 << 2) + z1
    #             x7x6x5x4x3x2x1x0: z3 = (x7x6x5x4x3x2x1x0*y3 << 3) + z2
    #           x7x6x5x4x3x2x1x0: z4 = (x7x6x5x4x3x2x1x0*y4 << 4) + z3
    #         x7x6x5x4x3x2x1x0: z5 = (x7x6x5x4x3x2x1x0*y5 << 5) + z4
    #       x7x6x5x4x3x2x1x0: z6 = (x7x6x5x4x3x2x1x0*y6 << 6) + z5
    #   + x7x6x5x4x3x2x1x0: z7 = (x7x6x5x4x3x2x1x0*y7 << 7) + z6
    #
    #   Signed case:
    #
    #   z8z7z6z5z4z3z2z1z0 = {          x7x7x6x5x4x3x2x1x0  if y7 is 0;
    #                          twoscomp(x7x7x6x5x4x3x2x1x0) if y7 is 1;
    #                                   ^--Not a typo! Sign-extend x7 to "x8"!
    #                                   z8 == z7, except when x == 0x80
    #                        }
    #   w7w6w5w4w3w2w1w0 = {          y7y6y5y4y3y2y1y0  if y7 is 0;
    #                        twoscomp(y7y6y5y4y3y2y1y0) if y7 is 1;
    #                      }
    #
    #   x, y, and z are signed, w is unsigned (or rather, "we don't care").
    #
    #                     x7x6x5x4x3x2x1x0
    #                   * y7y6y5y4y3y2y1y0
    #                     ----------------
    #                   z8z7z6z5z4z3z2z1z0: v0 = z8z7z6z5z4z3z2z1z0*w0
    #                 z8z7z6z5z4z3z2z1z0: v1 = (z8z7z6z5z4z3z2z1z0*w1 << 1) + v0  # noqa: E501
    #               z8z7z6z5z4z3z2z1z0: v2 = (z8z7z6z5z4z3z2z1z0*w2 << 2) + v1
    #             z8z7z6z5z4z3z2z1z0: v3 = (z8z7z6z5z4z3z2z1z0*w3 << 3) + v2
    #           z8z7z6z5z4z3z2z1z0: v4 = (z8z7z6z5z4z3z2z1z0*w4 << 4) + v3
    #         z8z7z6z5z4z3z2z1z0: v5 = (z8z7z6z5z4z3z2z1z0*w5 << 5) + v4
    #       z8z7z6z5z4z3z2z1z0: v6 = (z8z7z6z5z4z3z2z1z0*w6 << 6) + v5
    #   + z8z7z6z5z4z3z2z1z0: v7 = (z8z7z6z5z4z3z2z1z0*w7 << 7) + v6

    def elaborate(self, platform):  # noqa: D102
        def probe_pipeline_stage(i):
            if i == 0:
                stage_out = Signal.like(pipeline_out[0])
                m.d.comb += stage_out.eq(pipeline_out[0])
                self.pin = pipeline_in
                self.pout = pipeline_out
            else:
                stage_ina = Signal.like(self.pin[i - 1].a)
                stage_inb = Signal.like(self.pin[i - 1].b)
                stage_ins = Signal.like(self.pin[i - 1].s)
                m.d.comb += stage_ina.eq(self.pin[i - 1].a)
                m.d.comb += stage_inb.eq(self.pin[i - 1].b)
                m.d.comb += stage_ins.eq(self.pin[i - 1].s)

                stage_out = Signal.like(self.pout[i])
                m.d.comb += stage_out.eq(self.pout[i])

        m = Module()

        # self.a.width + 1 is required for when "a" is the negative-most value
        # for the width and self.b is also negative. Note that this can only
        # happen for SIGNED multiplies. In this scenario (see below), we need
        # to twos-complement "a". Consider an 8-bit signed signal with value
        # 0x80. The twos-complement is: ~0x80 + 1 = 0x7F + 1 = 0x80.
        #
        # In other words, the same value we started with. This also applies to
        # 0, there's no negative 0 in twos complement.
        #
        # To work around this, add an extra bit to your signed signal,
        # sign-extended automatically by Amaranth:
        # ~0x180 + 1 = 0x07F + 1 = 0x080
        #
        # This allows the twos complement conversion of "a" (done when "b" is
        # negative) be treated as positive for all possible values of "a".
        pipeline_in = Signal(
            ArrayLayout(
                StructLayout({
                    "a": signed(self.inp.data.a.shape().size + 1),
                    "b": unsigned(self.inp.data.b.shape().size),
                    "s": Sign
                }),
                self.width
            )
        )

        # FIXME: Does not work as intended. It is ignored.
        # for i in range(self.width):
        #     pipeline_in[i].s.reset = Sign.UNSIGNED

        # Relies on the optimizer to realize that not all 2*self.width^2
        # bits are actually used, regardless of whether we're shift-and-adding
        # positive or negative sign-extended (or positive zero-extended)
        # numbers:
        #
        # For example, consider these 2-bit signed numbers sign-extended
        # to 3-bits and added together, resulting in 3-bit signed numbers.
        # There are three possible cases a shift-add stage can see:
        #
        #               Positive:    Negative:   Negative, next add suppressed:  # noqa: E501
        # Accumulator:  000          11?         11?
        # Incoming:   + 00?        + 11?       + 000
        #             -----        -----       -----
        # Result Acc:   0??          1??         11?
        #
        # The sign bit in the result retains it's value in all cases, and
        # so (hopefully) the optimizer knows there's no reason to calculate it
        # for certain bits and instead just propogate the sign bit from input
        # stage.
        pipeline_out = Signal(ArrayLayout(signed(self.width*2), self.width))
        probe_pipeline_stage(0)

        m.d.sync += pipeline_in[0].s.eq(self.inp.data.sign)

        # If the multiplier is negative, and both inputs are signed,
        # we need to twos-complement the inputs. Since the inputs are otherwise
        # unmodified, we only need do this in the input stage.
        with m.If((self.inp.data.sign == Sign.SIGNED) & self.inp.data.b.i[-1]):
            m.d.sync += [
                # If multiplier is negative, then we need to _subtract_ the
                # multiplicand from 0... which is the same as adding the twos
                # complement! This also works if the multiplicand is negative!
                pipeline_in[0].a.eq(-self.inp.data.a.i),
                # In twos complement, each bit doesn't directly correspond to
                # whether an add should be suppressed or not; the twos
                # complement of the value does! This also works for the
                # negative-most multiplier, since we don't care about
                # signed-ness when querying each individual bit.
                pipeline_in[0].b.eq(-self.inp.data.b.i)
            ]
            m.d.sync += pipeline_out[0].eq(-self.inp.data.a.i *
                                           (-self.inp.data.b.i)[0])

        # If multiplier is positive, then pass through the multiplicand
        # and multiplier unchanged- zero-extend if unsigned, sign-extend if
        # negative.
        # Aside from sign-extension (to accommodate the most-negative value of
        # the multiplicand in the above branch), the multiplicand's signedness
        # doesn't matter. From the multiplier's POV, either we're adding
        # positive numbers or adding negative numbers together.
        with m.Else():
            # Quash sign-extension of "a" if unsigned multiply.
            with m.If(self.inp.data.sign == Sign.UNSIGNED):
                m.d.sync += [
                    pipeline_in[0].a.eq(self.inp.data.a.u),
                    pipeline_in[0].b.eq(self.inp.data.b.u)
                ]
                m.d.sync += pipeline_out[0].eq(self.inp.data.a.u *
                                               self.inp.data.b.u[0])
            with m.Else():
                m.d.sync += [
                    pipeline_in[0].a.eq(self.inp.data.a.i),
                    pipeline_in[0].b.eq(self.inp.data.b.u)
                ]
                m.d.sync += pipeline_out[0].eq(self.inp.data.a.i *
                                               self.inp.data.b.u[0])

        # With the above out of the way, the main multiplying stages should
        # be identical regardless of signedness (because adding shift copies
        # works the same regardless of sign). Only the interpretation of
        # the bit patterns differ, depending on signedness.
        for i in range(1, self.width):
            if self.debug:
                probe_pipeline_stage(i)

            m.d.sync += pipeline_in[i].eq(pipeline_in[i - 1])
            # This relies on the optimizer realizing we're doing a mul by a
            # 1 bit number (pipeline_in[i - 1].b[i]) with leading zeros.
            m.d.sync += pipeline_out[i].eq(((pipeline_in[i - 1].a *
                                             pipeline_in[i - 1].b[i]) << i) +
                                           pipeline_out[i - 1])

        # Should be the same regardless of whether .u or .i is used. Choose
        # i for consistency with pipeline_out.
        m.d.comb += self.outp.data.o.i.eq(pipeline_out[self.width - 1])
        m.d.comb += self.outp.data.sign.eq(pipeline_in[self.width - 1].s)

        return m
