"""Soft-core divider components."""

from amaranth import Elaboratable, Module, Signal, signed, C, unsigned
from amaranth.lib.data import StructLayout
from amaranth.lib.wiring import Signature, In, Out, Component, connect, flipped
from amaranth.lib.enum import IntEnum, auto


class Sign(IntEnum):
    """Indicate the type of divide to be performed.

    * ``UNSIGNED``: Both inputs ``n`` and ``d`` are unsigned.

      The output is unsigned.

    * ``SIGNED``: Both inputs ``n`` and ``d`` are unsigned.

      The quotient and remainder are signed. The remainder takes
      the sign of the dividend.
    """

    UNSIGNED = auto()
    SIGNED = auto()


class Inputs(StructLayout):
    r"""Tagged union representing the signedness of divider inputs.

    * When :attr:`sign` is ``UNSIGNED``, both :attr:`n` and :attr:`d` are
      treated by the divider as :class:`~amaranth:amaranth.hdl.Value`\ s
      with an :data:`~amaranth:amaranth.hdl.unsigned`
      :class:`~amaranth:amaranth.hdl.Shape`.

    * When ``sign`` is ``SIGNED``, both ``n`` and ``d`` are treated as Values
      with a :data:`~amaranth:amaranth.hdl.signed` Shape.

    Parameters
    ----------
    width : int
        Width in bits of both inputs ``n`` and ``d``. For signed divides, this
        includes the sign bit.

    Attributes
    ----------
    sign: Sign
        Controls the interpretation of the bit patterns of ``n`` and ``d``
        during division.
    n: Signal(width)
        The dividend; i.e. the ':math:`n`' in :math:`n / d`.
    d: Signal(width)
        The divisor; i.e. the ':math:`d`' in :math:`n / d`.
    """

    def __init__(self, width):
        super().__init__({
            "sign": Sign,
            "n": unsigned(width),
            "d": unsigned(width),
        })


class Outputs(StructLayout):
    r"""Tagged union representing the signedness of divider outputs.

    * When :attr:`sign` is ``UNSIGNED``, :attr:`q` and :attr:`r` should be
      treated as :class:`~amaranth:amaranth.hdl.Value`\ s with an
      :class:`~amaranth:amaranth.hdl.as_unsigned`
      :class:`~amaranth:amaranth.hdl.Shape`.

    * When ``sign`` is ``SIGNED``, ``q`` and ``r`` should be treated as Values
      with a :class:`~amaranth:amaranth.hdl.as_signed` Shape.

    Parameters
    ----------
    width : int
        Width in bits of the outputs ``q`` and ``r``. For signed dividers, this
        includes the sign bit.

    Attributes
    ----------
    sign: Sign
        Indicates whether the divider that produced this quotient/remainder
        was signed or unsigned.
    q: Signal(width)
        The quotient of :math:`n / d`.
    r: Signal(width)
        The remainder of :math:`n / d`, i.e. :math:`n \bmod d`.
    """

    def __init__(self, width):
        super().__init__({
            "sign": Sign,
            "q": unsigned(width),
            "r": unsigned(width)
        })


def divider_input_signature(width):
    """Create a parametric divider input port.

    This function returns a :class:`~amaranth:amaranth.lib.wiring.Signature`
    that's usable as a transfer initiator to a divider. A divider starts
    on the current cycle when both ``valid`` and ``rdy`` are asserted.

    Parameters
    ----------
    width : int
        Width in bits of the inputs :attr:`n` and :attr:`d`. For signed
        divides, this includes the sign bit.

    Returns
    -------
    :class:`~amaranth:amaranth.lib.wiring.Signature`
        :class:`~amaranth:amaranth.lib.wiring.Signature` containing the
        following attributes:

        .. attribute:: .data
            :type: Out(Inputs)
            :noindex:

            Data input to divider.

        .. attribute:: .rdy
            :type: In(1)
            :noindex:

            When ``1``, indicates that divider is ready.

        .. attribute:: .valid
            :type: In(1)
            :noindex:

            When ``1``, indicates that divider data input is valid.
    """
    return Signature({
        "data": Out(Inputs(width)),
        "rdy": In(1),
        "valid": Out(1)
    })


def divider_output_signature(width):
    """Create a parametric divider output port.

    This function returns a :class:`~amaranth:amaranth.lib.wiring.Signature`
    that's usable as a transfer initiator **from** a divider.

    .. note:: For a core responding **to** a divider, which is the typical
              use case, you will want to use this Signature with the
              :data:`~amaranth:amaranth.lib.wiring.In` flow, like so:

              .. doctest::

                  >>> from smolarith.mul import divider_output_signature
                  >>> from amaranth.lib.wiring import Signature, In
                  >>> my_receiver_sig = Signature({
                  ...     "inp": In(divider_output_signature(width=8))
                  ... })

    Parameters
    ----------
    width : int
        Width in bits of the outputs ``q`` and ``r``. For signed divides, this
        includes the sign bit.

    Returns
    -------
    :class:`~amaranth:amaranth.lib.wiring.Signature`
        :class:`~amaranth:amaranth.lib.wiring.Signature` containing the
        following attributes:

        .. attribute:: .data
            :type: Out(Outputs)
            :noindex:

            Data output **from** divider.

        .. attribute:: .rdy
            :type: In(1)
            :noindex:

            When ``1``, indicates that responder is ready to receive results
            from divider.

        .. attribute:: .valid
            :type: Out(1)
            :noindex:

            When ``1``, indicates that divider output data input is valid.
    """
    return Signature({
        "data": Out(Outputs(width)),
        "rdy": In(1),
        "valid": Out(1)
    })


class MulticycleDiv(Component):
    """Non-restoring divider soft-core."""

    def __init__(self, width=8):
        self.width = width
        self.to_u = _SignedUnsignedConverter(width)
        self.nrdiv = _NonRestoringDiv(width)
        self.from_u = _UnsignedSignedConverter(width)

        super().__init__({
            "inp": In(divider_input_signature(self.width)),
            "outp": Out(divider_output_signature(self.width))
        })


    def elaborate(self, plat):  # noqa: D102
        m = Module()

        m.submodules.to_u = self.to_u
        m.submodules.nrdiv = self.nrdiv
        m.submodules.from_u = self.from_u

        connect(m, flipped(self.inp), self.to_u.inp)
        connect(m, self.to_u.outp, self.nrdiv.inp)
        connect(m, self.nrdiv.outp, self.from_u.inp)
        connect(m, self.from_u.outp, flipped(self.outp))
        connect(m, self.to_u.conv, self.from_u.conv)

        return m


class _Quadrant(StructLayout):
    """Store sign information about divider inputs."""

    def __init__(self):  # noqa: DOC
        super().__init__({
            "n": unsigned(1),
            "d": unsigned(1),
        })


"""Pass sign information across an unsigned-only divider."""
_ConvControl = Signature({
    "quad": Out(_Quadrant()),
    "rdy": In(1),
    "valid": Out(1)
})


class _SignedUnsignedConverter(Component):
    """Convert maybe signed data to unsigned."""

    def __init__(self, width=8):  # noqa: DOC
        self.width = width

        super().__init__({
            "inp": In(divider_input_signature(self.width)),
            "outp": Out(divider_input_signature(self.width)),
            "conv": Out(_ConvControl),
        })

    def elaborate(self, plat):
        m = Module()

        m.d.comb += self.inp.rdy.eq((~self.outp.valid |
                                    (self.outp.valid & self.outp.rdy))
                                    & (~self.conv.valid |
                                    (self.conv.valid & self.conv.rdy)))
        
        with m.If(self.outp.valid & self.outp.rdy):
            m.d.sync += self.outp.valid.eq(0)

        with m.If(self.conv.valid & self.conv.rdy):
            m.d.sync += self.conv.valid.eq(0)

        # Prempt outp.valid.eq(0) if both interfaces are ready on the same
        # cycle.
        with m.If(self.inp.valid & self.inp.rdy):
            m.d.sync += self.outp.valid.eq(1)
            m.d.sync += self.conv.valid.eq(1)

            m.d.sync += [
                self.conv.quad.n.eq(self.inp.data.n[-1]),
                self.conv.quad.d.eq(self.inp.data.d[-1]),
                self.outp.data.n.eq(self.inp.data.n),
                self.outp.data.d.eq(self.inp.data.d),
                self.outp.data.sign.eq(self.inp.data.sign)
            ]

            with m.If(self.inp.data.sign == Sign.SIGNED):
                with m.If(self.inp.data.n[-1]):
                    m.d.sync += self.outp.data.n.eq(
                        (-self.inp.data.n.as_signed())[:-1])
                with m.If(self.inp.data.d[-1]):
                    m.d.sync += self.outp.data.d.eq(
                        (-self.inp.data.d.as_signed())[:-1])
                    
        return m


class _UnsignedSignedConverter(Component):
    """Convert maybe unsigned data to signed."""

    def __init__(self, width=8):  # noqa: DOC
        self.width = width

        super().__init__({
            "inp": In(divider_output_signature(self.width)),
            "outp": Out(divider_output_signature(self.width)),
            "conv": In(_ConvControl),
        })

    def elaborate(self, plat):
        m = Module()

        with m.If(self.outp.valid & self.outp.rdy):
            m.d.sync += self.outp.valid.eq(0)

        # Wait for both input interfaces to be valid, and then consume all
        # input data at once.
        with m.If(self.conv.valid & self.inp.valid &
                  (~self.outp.valid | (self.outp.valid & self.outp.rdy))):
            m.d.comb += [
                self.conv.rdy.eq(1),
                self.inp.rdy.eq(1)
            ]
            m.d.sync += self.outp.valid.eq(1)

            m.d.sync += [
                self.outp.data.q.eq(self.inp.data.q),
                self.outp.data.r.eq(self.inp.data.r),
                self.outp.data.sign.eq(self.inp.data.sign)
            ]

            with m.If((self.inp.data.sign == Sign.SIGNED) &
                      self.conv.quad.n &
                      ~self.conv.quad.d):
                m.d.sync += [
                    self.outp.data.q.eq((-self.inp.data.q.as_signed())[:-1]),
                    self.outp.data.r.eq((-self.inp.data.r.as_signed())[:-1])
                ]

            with m.If((self.inp.data.sign == Sign.SIGNED) &
                      ~self.conv.quad.n &
                      self.conv.quad.d):
                m.d.sync += self.outp.data.q.eq(
                    (-self.inp.data.q.as_signed())[:-1])
                
            with m.If((self.inp.data.sign == Sign.SIGNED) &
                      self.conv.quad.n &
                      self.conv.quad.d):
                m.d.sync += self.outp.data.r.eq(
                    (-self.inp.data.r.as_signed())[:-1])
                
        return m


class _NonRestoringDiv(Component):
    """Unsigned-only non-restoring divider."""

    def __init__(self, width=8):  # noqa: DOC
        self.width = width
        # sign Signals are unused- Sign.UNSIGNED is implicit.
        super().__init__({
            "inp": In(divider_input_signature(self.width)),
            "outp": Out(divider_output_signature(self.width))
        })

    def elaborate(self, platform):
        m = Module()

        intermediate = Signal(2*self.width)
        iters_left = Signal(range(self.inp.data.n.shape().width))
        in_progress = Signal()
        restore_step = Signal()
        s_copy = Signal(Sign)

        m.d.comb += self.inp.rdy.eq((self.outp.rdy & self.outp.valid) |
                                    ~in_progress)
        m.d.comb += in_progress.eq((iters_left != 0) | restore_step)

        with m.If(self.outp.valid & self.outp.rdy):
            m.d.sync += self.outp.valid.eq(0)

        with m.If(self.inp.rdy & self.inp.valid):
            m.d.sync += [
                s_copy.eq(self.inp.data.sign),
                iters_left.eq(self.inp.data.n.shape().width - 1)
            ]

            # On initial iter, we'll never be below 0.
            # S = (S << 1) - D, to be shifted into in top half, to be shifted
            # into final position.
            # q[-1] = 1, encoded as 1, encoded in bottom half, to be shifted
            # into final position.
            m.d.sync += intermediate.eq((self.inp.data.n << 1) -
                                        (self.inp.data.d << self.width) |
                                        1)

        with m.If(in_progress & ~restore_step):
            # State Control
            m.d.sync += iters_left.eq(iters_left - 1)

            with m.If((iters_left - 1) == 0):
                m.d.sync += restore_step.eq(1)

            # Loop iter
            with m.If(intermediate[-1]):
                # S = (S << 1) + D, encoded in top half.
                # q = -1, encoded as 0, encoded in bottom half.
                m.d.sync += intermediate.eq(((intermediate << 1) +
                                            (self.inp.data.d << self.width)))
            with m.Else():
                # S = (S << 1) - D, encoded in top half.
                # q = 1, encoded as 1, encoded in bottom half.
                m.d.sync += intermediate.eq(((intermediate << 1) -
                                            (self.inp.data.d << self.width)) |
                                            1)
        
        with m.If(restore_step):
            m.d.sync += [
                restore_step.eq(0),
                self.outp.valid.eq(1)
            ]

            # Extract encoded negative powers of two and then subtract as if
            # they were positive powers of two (so no twos complement
            # conversion needed).
            m.d.sync += intermediate[:self.width].eq(
                intermediate[:self.width] - ~intermediate[:self.width])

            with m.If(intermediate[-1]):
                # S += D
                # q -= 1
                m.d.sync += [
                    intermediate[:self.width].eq(
                        intermediate[:self.width] -
                        ~intermediate[:self.width] -
                        1),
                    intermediate[self.width:].eq(
                        intermediate[self.width:] + self.inp.data.d)
                ]

        m.d.comb += [
            self.outp.data.q.eq(intermediate[:self.width]),
            self.outp.data.r.eq(intermediate[self.width:]),
            self.outp.data.sign.eq(s_copy)
        ]

        return m


class LongDivider(Component):
    r"""Long-division soft-core, used as a reference.

    This divider core is a gateware implementation of classic long division.

    * A divide starts on the current cycle when both ``inp.valid`` and
      ``inp.rdy`` are asserted.
    * A divide result is available when ``outp.valid`` is asserted. The
      result is read/overwritten once a downstream core asserts ``outp.rdy``.

    .. warning::

        This core is not intended to be used in user designs due to poor
        resource usage. It is mainly kept as a known-to-work reference design
        for possible equivalence checking later.

    .. todo::

        Update to Amaranth streams when available.

    * Latency: Divide Results for a will be available ``width`` clock cycles
      after assertion of both ``inp.valid`` and ``inp.rdy``.

    * Throughput: One divide maximum is finished every ``width``
      clock cycles.

    Parameters
    ----------
    width : int
        Width in bits of both inputs ``n`` and ``d``. For signed
        multiplies, this includes the sign bit. Outputs ``q`` and ``r`` width
        will be :math:`2*n`.

    Attributes
    ----------
    width : int
        Bit width of the inputs ``n`` and ``d``. Outputs ``q`` and ``r`` width
        will be :math:`2*n`.
    inp : In(divider_input_signature(width))
        Input interface to the divider.
    outp : Out(divider_output_signature(width))
        Output interface of the divider.

    Notes
    -----
    * This multiplier is a naive long-division implementation, similar to how
      pen-and-pad division is done in base-2/10.

    * Internally, the divider is aware of the sign of its inputs as well as
      the sign of the divide operation.

      The divider will dispatch to one of the 4 possible combinations of signs
      during the division loop. The four combinations are:

        * Add shifted copies of **positive**/**negative** powers of two
          together to form the quotient.
        * **Add**/**subtract** shifted copies of the divisor from the dividend
          **towards zero** to form the remainder.

    * This divider is compliant with RISC-V semantics for divide-by-zero and
      overflow when ``width=32`` or ``width=64``\ [rv]_. Specifically:

        * Signed/unsigned divide-by-zero returns "all bits set" for the
          quotient and the dividend as the remainder.
        * Signed overflow (:math:`-2^{\{31,63\}}/-1`) returns
          :math:`-2^{\{31,63\}}` for the quotient and :math:`0` as the
          remainder.

    .. [rv] https://github.com/riscv/riscv-isa-manual/releases/tag/Ratified-IMAFDQC
    """

    def __init__(self, width=8):
        self.width = width
        super().__init__({
            "inp": In(divider_input_signature(self.width)),
            "outp": Out(divider_output_signature(self.width))
        })

    def elaborate(self, platform):  # noqa: D102
        m = Module()

        m.submodules.mag = mag = _MagnitudeComparator(2*self.width)

        quotient = Signal(2*self.width)
        remainder = Signal(2*self.width)
        iters_left = Signal(range(self.width))
        in_progress = Signal()
        s_copy = Signal(Sign)
        a_sign = Signal()
        n_sign = Signal()

        # Reduce latency by 1 cycle by preempting output being read.
        m.d.comb += self.inp.rdy.eq((self.outp.rdy & self.outp.valid) |
                                    ~in_progress)
        m.d.comb += in_progress.eq(iters_left != 0)
        m.d.comb += [
            self.outp.data.q.eq(quotient),
            self.outp.data.r.eq(remainder),
            self.outp.data.sign.eq(s_copy),
        ]

        with m.If(self.outp.rdy & self.outp.valid):
            m.d.sync += self.outp.valid.eq(0)

        with m.If(self.inp.rdy & self.inp.valid):
            m.d.sync += [
                # We handle first cycle using shift_amt mux.
                iters_left.eq(self.width - 1),
                a_sign.eq(self.inp.data.n[-1]),
                n_sign.eq(self.inp.data.d[-1]),
                s_copy.eq(self.inp.data.sign)
            ]

            # When dividing by 0, for RISCV compliance, we need the division to
            # return -1. Without redirecting quotient calculation to the
            # "both dividend/divisor positive" case, dividing a negative
            # number by 0 returns 1. Note that the sign-bit processing doesn't
            # need to be special-cased, I do it anyway in case I see some
            # patterns I can refactor out.
            with m.If((self.inp.data.sign == Sign.SIGNED) &
                      (self.inp.data.d == 0) &
                      self.inp.data.n[-1]):
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
            with m.If(self.inp.data.sign == Sign.SIGNED):
                m.d.comb += [
                    mag.divisor.eq((self.inp.data.d.as_signed() * shift_amt).as_signed()),  # noqa: E501
                    mag.dividend.eq(self.inp.data.n.as_signed())
                ]
            with m.Else():
                m.d.comb += [
                    mag.divisor.eq(self.inp.data.d.as_unsigned() * shift_amt),
                    mag.dividend.eq(self.inp.data.n.as_unsigned())
                ]

            with m.If(mag.o):
                # If dividend/divisor are positive, subtract a positive
                # shifted divisor from dividend.
                with m.If((self.inp.data.sign == Sign.UNSIGNED) |
                          (~self.inp.data.n[-1] & ~self.inp.data.d[-1]) |
                          (self.inp.data.n[-1] & self.inp.data.d == 0)):
                    m.d.sync += quotient.eq(C(1) * shift_amt)
                    with m.If(self.inp.data.sign == Sign.SIGNED):
                        # If high bit is set, and, a signed div,
                        # we want to sign-extend.
                        m.d.sync += remainder.eq(self.inp.data.n.as_signed() -
                                                 (self.inp.data.d.as_signed() * C(1) * shift_amt).as_signed())  # noqa: E501
                    with m.Else():
                        # Otherwise, zero-extend.
                        m.d.sync += remainder.eq(self.inp.data.n.as_unsigned() -  # noqa: E501
                                                 (self.inp.data.d.as_unsigned() * C(1) * shift_amt))  # noqa: E501
                # If dividend is negative, but divisor is positive, create a
                # negative shifted divisor and subtract from the dividend.
                with m.If((self.inp.data.sign == Sign.SIGNED) &
                          self.inp.data.n[-1] & ~self.inp.data.d[-1] &
                          ~(self.inp.data.d == 0 & self.inp.data.n[-1])):
                    m.d.sync += quotient.eq(C(-1) * shift_amt)
                    m.d.sync += remainder.eq(self.inp.data.n.as_signed() -
                                             (self.inp.data.d.as_signed() * C(-1) * shift_amt).as_signed())  # noqa: E501
                # If dividend is positive, but divisor is negative, create a
                # positive shifted divisor and subtract from the dividend.
                with m.If((self.inp.data.sign == Sign.SIGNED) &
                          ~self.inp.data.n[-1] & self.inp.data.d[-1]):
                    m.d.sync += quotient.eq(C(-1) * shift_amt)
                    m.d.sync += remainder.eq(self.inp.data.n.as_signed() -
                                             (self.inp.data.d.as_signed() * C(-1) * shift_amt).as_signed())  # noqa: E501
                # If dividend/divisor is negative, subtract a negative
                # shifted divisor and subtract from the dividend.
                with m.If((self.inp.data.sign == Sign.SIGNED) &
                          self.inp.data.n[-1] & self.inp.data.d[-1]):
                    m.d.sync += quotient.eq(C(1) * shift_amt)
                    m.d.sync += remainder.eq(self.inp.data.n.as_signed() -
                                             (self.inp.data.d.as_signed() * C(1) * shift_amt).as_signed())  # noqa: E501
            with m.Else():
                m.d.sync += quotient.eq(0)
                with m.If(self.inp.data.sign == Sign.SIGNED):
                    # If high bit is set, and, a signed div,
                    # we want to sign-extend.
                    m.d.sync += remainder.eq(self.inp.data.n.as_signed())
                with m.Else():
                    # Otherwise, zero-extend.
                    m.d.sync += remainder.eq(self.inp.data.n.as_unsigned())

        # Main division loop.
        with m.If(in_progress):
            m.d.sync += iters_left.eq(iters_left - 1)

            shift_amt = (1 << (iters_left - 1).as_unsigned())
            with m.If(self.inp.data.sign == Sign.SIGNED):
                m.d.comb += [
                    mag.divisor.eq(self.inp.data.d.as_signed() * shift_amt),
                    mag.dividend.eq(remainder.as_signed())
                ]
            with m.Else():
                m.d.comb += [
                    mag.divisor.eq(self.inp.data.d.as_unsigned() * shift_amt),
                    mag.dividend.eq(remainder)
                ]

            with m.If(mag.o):
                # If dividend/divisor are positive, subtract a positive
                # shifted divisor from dividend.
                with m.If((s_copy == Sign.UNSIGNED) | (~a_sign & ~n_sign)):
                    m.d.sync += quotient.eq(quotient + C(1) * shift_amt)
                    with m.If(s_copy == Sign.SIGNED):
                        # If high bit is set, and, a signed div,
                        # we want to sign-extend.
                        m.d.sync += remainder.eq(remainder -
                                                 (self.inp.data.d.as_signed() * C(1) * shift_amt).as_signed())  # noqa: E501
                    with m.Else():
                        # Otherwise, zero-extend.
                        m.d.sync += remainder.eq(remainder -
                                                 (self.inp.data.d.as_unsigned() * C(1) * shift_amt))  # noqa: E501
                # If dividend is negative, but divisor is positive, create a
                # negative shifted divisor and subtract from the dividend.
                with m.If((s_copy == Sign.SIGNED) & a_sign & ~n_sign): 
                    m.d.sync += quotient.eq(quotient + C(-1) * shift_amt)
                    m.d.sync += remainder.eq(remainder -
                                             (self.inp.data.d.as_signed() * C(-1) * shift_amt).as_signed())  # noqa: E501
                # If dividend is positive, but divisor is negative, create a
                # positive shifted divisor and subtract from the dividend.
                with m.If((s_copy == Sign.SIGNED) & ~a_sign & n_sign):
                    m.d.sync += quotient.eq(quotient + C(-1) * shift_amt)
                    m.d.sync += remainder.eq(remainder -
                                             (self.inp.data.d.as_signed() * C(-1) * shift_amt).as_signed())  # noqa: E501
                # If dividend/divisor are negative, subtract a negative
                # shifted divisor from dividend.
                with m.If((s_copy == Sign.SIGNED) & a_sign & n_sign):
                    m.d.sync += quotient.eq(quotient + C(1) * shift_amt)
                    m.d.sync += remainder.eq(remainder -
                                             (self.inp.data.d.as_signed() * C(1) * shift_amt).as_signed())  # noqa: E501

            with m.If(iters_left - 1 == 0):
                m.d.sync += self.outp.valid.eq(1)

        return m


class _MagnitudeComparator(Elaboratable):
    """Compare the magnitude of two signed numbers."""

    def __init__(self, width=8):  # noqa: DOC
        self.width = width
        self.dividend = Signal(signed(self.width))
        self.divisor = Signal(signed(self.width))
        self.o = Signal()

    def elaborate(self, platform):
        m = Module()

        m.d.comb += self.o.eq(abs(self.divisor) <= abs(self.dividend))

        return m


if __name__ == "__main__":
    from amaranth.back.verilog import convert

    print(convert(MulticycleDiv(32)))
