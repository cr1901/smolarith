"""Soft-core divider components."""

from amaranth import Elaboratable, Module, Signal, signed, C, unsigned
from amaranth.lib.data import StructLayout
from amaranth.lib.wiring import In, Out, Component
from amaranth.lib.enum import Enum, auto
from amaranth.lib import stream


class Sign(Enum):
    """Indicate the type of divide to be performed.

    Attributes
    ----------
    UNSIGNED : int
        Both inputs ``n`` and ``d`` are unsigned.

        The output is unsigned.

    SIGNED : int
        Both inputs ``n`` and ``d`` are signed.

        The quotient and remainder are signed. The remainder takes
        the sign of the dividend.
    """

    UNSIGNED = auto()
    SIGNED = auto()


class Inputs(StructLayout):  # noqa: DOC602,DOC603
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


class Outputs(StructLayout):  # noqa: DOC602,DOC603
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

    This function returns a :class:`~amaranth:amaranth.lib.stream.Signature`
    that's usable as a transfer initiator to a divider. A divider starts
    on the current cycle when both ``valid`` and ``rdy`` are asserted.

    Parameters
    ----------
    width : int
        Width in bits of the inputs :attr:`n` and :attr:`d`. For signed
        divides, this includes the sign bit.

    Returns
    -------
    :class:`amaranth:amaranth.lib.stream.Signature`
        :py:`Signature(Inputs)`
    """
    return stream.Signature(Inputs(width))


def divider_output_signature(width):
    """Create a parametric divider output port.

    This function returns a :class:`~amaranth:amaranth.lib.stream.Signature`
    that's usable as a transfer initiator **from** a divider.

    .. note:: For a core responding **to** a divider, which is the typical
              use case, you will want to use this Signature with the
              :data:`~amaranth:amaranth.lib.wiring.In` flow, like so:

              .. doctest::

                  >>> from smolarith.div import divider_output_signature
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
    :class:`amaranth:amaranth.lib.stream.Signature`
        :py:`Signature(Outputs)`
    """
    return stream.Signature(Outputs(width))


class _Quadrant(StructLayout):
    """Store sign information about divider inputs."""

    def __init__(self):  # noqa: DOC1
        super().__init__({
            "n": unsigned(1),
            "d": unsigned(1),
        })


class _Negate(Component):
    def __init__(self, width=8):  # noqa: DOC1
        self.width = width
        super().__init__({
            "inp": In(self.width),
            "outp": Out(self.width)
        })

    
    def elaborate(self, plat):
        m = Module()

        m.d.comb += self.outp.eq((-self.inp.as_signed())[:-1])

        return m


class Impl(Enum):
    """Indicate the division algorithm to use inside a dividing component.

    Attributes
    ----------
    RESTORING : int
        Use :ref:`restoring division <derive-res>` for the internal divider.
        *This is a good default*.

    NON_RESTORING : int
        Use :ref:`non-restoring division <derive-nr>` for the internal divider.
    """

    RESTORING = auto()
    NON_RESTORING = auto()


class MulticycleDiv(Component):  # noqa: DOC602,DOC603
    # FIXME: I can't be .. _latency label to work, even with :ref:`latency`...
    # always "undefined label"... huh?!
    r"""Restoring/Non-restoring divider soft-core.

    This divider core is a gateware implementation of 
    :ref:`restoring division <derive-res>` or
    :ref:`non-restoring division <derive-nr>`. It works for both signed and
    unsigned divides, and should be preferred to :class:`LongDivider` in almost
    all circumstances due to better resource usage.

    * A divide starts on the current cycle when both ``inp.valid`` and
      ``inp.ready`` are asserted.
    * A divide result is available when ``outp.valid`` is asserted. The
      result is read/overwritten once a downstream core asserts ``outp.ready``.

    * Latency: Divide Results for a restoring divider will be available
      ``width + 3`` clock cycles after assertion of both ``inp.valid`` and
      ``inp.ready``. For a non-restoring divider, results are available after
      ``width + 4`` clock cycles.

    * Throughput: One divide maximum is finished every ``width + 3``
      clock cycles for a restoring divider, and every ``width + 4`` for a
      non-restoring divider.

    Parameters
    ----------
    width : int
        Width in bits of both inputs ``n`` and ``d``. For signed
        multiplies, this includes the sign bit. Outputs ``q`` and ``r`` width
        will be the same width.
    impl : Impl
        Choose whether to use a restoring divider or non-restoring divider
        internally. The default of ``RESTORING`` is fine for most cases.

    Attributes
    ----------
    width : int
        Bit width of the inputs ``n`` and ``d``, and outputs ``q`` and ``r``.
    inp : In(divider_input_signature(width))
        Input interface to the divider.
    outp : Out(divider_output_signature(width))
        Output interface of the divider.

    Notes
    -----
    * This divider is implemented using either restoring or non-restoring
      division. It is basically a gateware translation of the
      :ref:`Python <resdiv-py>` :ref:`implementations <nrdiv-py>` shown in
      :ref:`impl`.

    * Unlike the multipliers, where I could eyeball approximate storage element
      usage, divider size was benchmarked using
      `yosys <https://yosyshq.net/yosys/>`_\ 's ``synth_ice40`` pass. For an
      :math:`n`-bit divide:
    
      * ``impl=Impl.RESTORING`` requires approximately :math:`O(7*n)`
        storage elements and :math:`O(12.75*n)` LUT4s.
      * ``impl=Impl.NON_RESTORING`` requires approximately :math:`O(8*n)`
        storage elements and :math:`O(14.5*n)` LUT4s.

    * Internally, the divider converts its operands from signed to unsigned
      if necessary, performs the division, and the converts back from unsigned
      to signed if necessary. I ran into some :ref:`issues <signedness>` with
      making a signed-aware non-restoring divider such that eating the
      conversion cost latency is probably justifiable for implementation
      simplicity of both a restoring and non-restoring divider.

    .. _latency:

      The combination of signed-to-unsigned conversion, using a cycle to
      latching inputs to the internal divider, and unsigned-to-signed
      conversion adds three cycles of latency beyond the expected ``width``
      number of cycles to perform a division.

      Additionally, when using a non-restoring divider, the quotient and
      remainder require a possible :ref:`final restore step <nrdiv-restore>`.
      Remainder restore is implemented as shown in the
      :ref:`Python code <nrdiv-py>`. Quotient restore is implemented by
      subtracting the ones complement of the raw quotient from the raw quotient
      itself.

    * The quotient and remainder share a backing store; new bits are shifted
      into the lower-half quotient portion as the remainder is shifted into the
      upper half. This works because each iteration of the
      restoring/non-restoring loops check the sign of the remainder, and the
      lower quotient bits won't affect the sign bit.

    * This divider is compliant with RISC-V semantics for divide-by-zero and
      overflow when ``width=32`` or ``width=64``\ [rv]_. Specifically:

      * Signed/unsigned divide-by-zero returns "all bits set" for the
        quotient and the dividend as the remainder.
      * Signed overflow (:math:`-2^{\{31,63\}}/-1`) returns
        :math:`-2^{\{31,63\}}` for the quotient and :math:`0` as the
        remainder.

    Future Directions
    -----------------

    * It may be worthwhile to make a pipelined divider?

    * Current latency is worse than the :class:`LongDivider`, which is just
      about the only advantage to ``LongDivider``. We can provide an option to
      reduce latency/resources required due to the signed/unsigned and restore
      stages at the cost of some timing closure.
    """

    def __init__(self, width=8, impl=Impl.RESTORING):
        self.width = width
        if impl == Impl.RESTORING:
            self.div_impl = _RestoringDiv(width)
        elif impl == Impl.NON_RESTORING:
            self.div_impl = _NonRestoringDiv(width)
        self.negate_nq = _Negate(width)
        self.negate_dr = _Negate(width)

        super().__init__({
            "inp": In(divider_input_signature(self.width)),
            "outp": Out(divider_output_signature(self.width))
        })

    def elaborate(self, plat):  # noqa: D102
        m = Module()

        m.submodules.div_impl = self.div_impl
        # Time-division multiplex negation units... in a multicycle div, only
        # n/d or q/r need to be negated at once.
        m.submodules.negate_nq = self.negate_nq
        m.submodules.negate_dr = self.negate_dr

        quad = Signal(_Quadrant())
        div_inputs = Signal(Inputs(self.width))

        m.d.comb += self.div_impl.inp.payload.eq(div_inputs)

        with m.FSM():
            with m.State("IDLE"):
                m.d.comb += [
                    self.inp.ready.eq(1),
                    self.negate_nq.inp.eq(self.inp.payload.n),
                    self.negate_dr.inp.eq(self.inp.payload.d)
                ]

                m.d.comb += self.inp.ready.eq(1)
                with m.If(self.inp.valid):
                    m.next = "DIVIDE_IN"
                    
                    # Re: (self.inp.payload.d != 0)
                    # For RISCV compliance when dividing by zero, we need to
                    # suppress signed-unsigned conversion. Treating the input
                    # bit pattern as-is will result in the correct behavior of
                    # "all bits set in divisor" and remainder unchanged,
                    # regardless of sign.
                    m.d.sync += [
                        quad.n.eq(self.inp.payload.n[-1] &
                                  (self.inp.payload.d != 0)),
                        quad.d.eq(self.inp.payload.d[-1]),
                        div_inputs.eq(self.inp.payload)
                    ]

                    with m.If(self.inp.payload.sign == Sign.SIGNED):
                        with m.If(self.inp.payload.n[-1] &
                                  (self.inp.payload.d != 0)):
                            m.d.sync += div_inputs.n.eq(self.negate_nq.outp)
                        with m.If(self.inp.payload.d[-1]):
                            m.d.sync += div_inputs.d.eq(self.negate_dr.outp)

            with m.State("DIVIDE_IN"):
                m.d.comb += self.div_impl.inp.valid.eq(1)

                with m.If(self.div_impl.inp.ready):
                    m.next = "DIVIDE_LOOP"

            with m.State("DIVIDE_LOOP"):
                m.d.comb += [
                    self.div_impl.outp.ready.eq(1),
                    self.negate_nq.inp.eq(self.div_impl.outp.payload.q),
                    self.negate_dr.inp.eq(self.div_impl.outp.payload.r)
                ]

                with m.If(self.div_impl.outp.valid):
                    m.next = "DIVIDE_OUT"

                    m.d.sync += [
                        self.outp.payload.eq(self.div_impl.outp.payload),
                    ]

                    with m.If((div_inputs.sign == Sign.SIGNED) &
                              quad.n & ~quad.d):
                        m.d.sync += [
                            self.outp.payload.q.eq(self.negate_nq.outp),
                            self.outp.payload.r.eq(self.negate_dr.outp)
                        ]

                    with m.If((div_inputs.sign == Sign.SIGNED) &
                              ~quad.n & quad.d):
                        m.d.sync += self.outp.payload.q.eq(self.negate_nq.outp)
                        
                    with m.If((div_inputs.sign == Sign.SIGNED) &
                              quad.n & quad.d):
                        m.d.sync += self.outp.payload.r.eq(self.negate_dr.outp)
                        
            with m.State("DIVIDE_OUT"):
                m.d.comb += self.outp.valid.eq(1)

                with m.If(self.outp.ready):
                    m.next = "IDLE"

        return m


class _RestoringDiv(Component):  # noqa: DOC602,DOC603
    """Unsigned-only restoring divider."""

    def __init__(self, width=8):  # noqa: DOC1
        self.width = width
        # sign Signals are unused- Sign.UNSIGNED is implicit.
        super().__init__({
            "inp": In(divider_input_signature(self.width)),
            "outp": Out(divider_output_signature(self.width))
        })

    def elaborate(self, platform):
        m = Module()

        # Need extra bit because we need to subtract up to 2^width, which
        # should remain negative.
        intermediate = Signal(2*self.width + 1)
        iters_left = Signal(range(self.inp.payload.n.shape().width + 1))
        in_progress = Signal()
        s_copy = Signal(Sign)
        d_copy = Signal(self.inp.payload.d.shape())

        m.d.comb += self.inp.ready.eq((self.outp.ready & self.outp.valid) |
                                      ~in_progress)
        m.d.comb += in_progress.eq(iters_left != 0)

        with m.If(self.outp.valid & self.outp.ready):
            m.d.sync += self.outp.valid.eq(0)

        with m.If(self.inp.ready & self.inp.valid):
            m.d.sync += [
                s_copy.eq(self.inp.payload.sign),
                d_copy.eq(self.inp.payload.d),
                iters_left.eq(self.inp.payload.n.shape().width),
                intermediate.eq(self.inp.payload.n)
            ]

        with m.If(in_progress):
            # State Control
            m.d.sync += iters_left.eq(iters_left - 1)

            with m.If((iters_left - 1) == 0):
                m.d.sync += self.outp.valid.eq(1)

            # Loop iter
            # S = (S << 1) - D
            with m.If(((intermediate << 1) - (d_copy << self.width)) < 0):
                # S += D
                m.d.sync += intermediate.eq((intermediate << 1))  # noqa: E501
            with m.Else():
                # q <<=1 and then q |= 1
                # (Docs do q |= 1 and then q <<= 1, requiring a >> at the end.)
                m.d.sync += intermediate.eq(((intermediate << 1) -
                                             (d_copy << self.width)) | 1)  # noqa: E501

        m.d.comb += [
            self.outp.payload.q.eq(intermediate[:self.width]),
            self.outp.payload.r.eq(intermediate[self.width:]),
            self.outp.payload.sign.eq(s_copy)
        ]

        return m


class _NonRestoringDiv(Component):
    """Unsigned-only non-restoring divider."""

    def __init__(self, width=8):  # noqa: DOC1
        self.width = width
        # sign Signals are unused- Sign.UNSIGNED is implicit.
        super().__init__({
            "inp": In(divider_input_signature(self.width)),
            "outp": Out(divider_output_signature(self.width))
        })

    def elaborate(self, platform):
        m = Module()

        # Need extra bit because we need to subtract up to 2^width, which
        # should remain negative.
        intermediate = Signal(2*self.width + 1)
        iters_left = Signal(range(self.inp.payload.n.shape().width + 1))
        in_progress = Signal()
        restore_step = Signal()
        s_copy = Signal(Sign)
        d_copy = Signal(self.inp.payload.d.shape())
        r = Signal(self.width)

        m.d.comb += self.inp.ready.eq((self.outp.ready & self.outp.valid) |
                                      ~in_progress)
        m.d.comb += in_progress.eq((iters_left != 0) | restore_step)

        with m.If(self.outp.valid & self.outp.ready):
            m.d.sync += self.outp.valid.eq(0)

        with m.If(self.inp.ready & self.inp.valid):
            m.d.sync += [
                s_copy.eq(self.inp.payload.sign),
                d_copy.eq(self.inp.payload.d),
                iters_left.eq(self.inp.payload.n.shape().width),
                intermediate.eq(self.inp.payload.n)
            ]

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
                                            (d_copy << self.width)))  # noqa: E501
            with m.Else():
                # S = (S << 1) - D, encoded in top half.
                # q = 1, encoded as 1, encoded in bottom half.
                m.d.sync += intermediate.eq(((intermediate << 1) -
                                            (d_copy << self.width)) | 1)  # noqa: E501


        with m.If(restore_step):
            m.d.sync += [
                restore_step.eq(0),
                self.outp.valid.eq(1)
            ]

            # Extract encoded negative powers of two and then subtract as if
            # they were positive powers of two (so no twos complement
            # conversion needed).
            # Better LUT usage if "r" has its own register.
            m.d.sync += [
                intermediate[:self.width].eq(
                    intermediate[:self.width] - ~intermediate[:self.width]),
                r.eq(intermediate[self.width:])
            ]

            with m.If(intermediate[-1]):
                # S += D
                # q -= 1
                m.d.sync += [
                    intermediate[:self.width].eq(
                        intermediate[:self.width] -
                        ~intermediate[:self.width] -
                        1),
                    r.eq(intermediate[self.width:] + d_copy)
                ]

        m.d.comb += [
            self.outp.payload.q.eq(intermediate[:self.width]),
            self.outp.payload.r.eq(r),
            self.outp.payload.sign.eq(s_copy)
        ]

        return m


class LongDivider(Component):  # noqa: DOC602,DOC603
    r"""Long-division soft-core, used as a reference.

    This divider core is a gateware implementation of classic long division.

    * A divide starts on the current cycle when both ``inp.valid`` and
      ``inp.ready`` are asserted.
    * A divide result is available when ``outp.valid`` is asserted. The
      result is read/overwritten once a downstream core asserts ``outp.ready``.

    .. warning::

        This core is not intended to be used in user designs due to poor
        resource usage. It is mainly kept as a known-to-work reference design
        for possible equivalence checking later. Use :class:`MulticycleDiv`
        instead.

    * Latency: Divide Results for a will be available ``width`` clock cycles
      after assertion of both ``inp.valid`` and ``inp.ready``.

    * Throughput: One divide maximum is finished every ``width``
      clock cycles.

    Parameters
    ----------
    width : int
        Width in bits of both inputs ``n`` and ``d``. For signed
        multiplies, this includes the sign bit. Outputs ``q`` and ``r`` width
        will be the same width.

    Attributes
    ----------
    width : int
        Bit width of the inputs ``n`` and ``d``, and outputs ``q`` and ``r``.
    inp : In(divider_input_signature(width))
        Input interface to the divider.
    outp : Out(divider_output_signature(width))
        Output interface of the divider.

    Notes
    -----
    * This divider is a naive long-division implementation, similar to how
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
        m.d.comb += self.inp.ready.eq((self.outp.ready & self.outp.valid) |
                                      ~in_progress)
        m.d.comb += in_progress.eq(iters_left != 0)
        m.d.comb += [
            self.outp.payload.q.eq(quotient),
            self.outp.payload.r.eq(remainder),
            self.outp.payload.sign.eq(s_copy),
        ]

        with m.If(self.outp.ready & self.outp.valid):
            m.d.sync += self.outp.valid.eq(0)

        with m.If(self.inp.ready & self.inp.valid):
            m.d.sync += [
                # We handle first cycle using shift_amt mux.
                iters_left.eq(self.width - 1),
                a_sign.eq(self.inp.payload.n[-1]),
                n_sign.eq(self.inp.payload.d[-1]),
                s_copy.eq(self.inp.payload.sign)
            ]

            # When dividing by 0, for RISCV compliance, we need the division to
            # return -1. Without redirecting quotient calculation to the
            # "both dividend/divisor positive" case, dividing a negative
            # number by 0 returns 1. Note that the sign-bit processing doesn't
            # need to be special-cased, I do it anyway in case I see some
            # patterns I can refactor out.
            with m.If((self.inp.payload.sign == Sign.SIGNED) &
                      (self.inp.payload.d == 0) &
                      self.inp.payload.n[-1]):
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
            with m.If(self.inp.payload.sign == Sign.SIGNED):
                m.d.comb += [
                    mag.divisor.eq((self.inp.payload.d.as_signed() * shift_amt).as_signed()),  # noqa: E501
                    mag.dividend.eq(self.inp.payload.n.as_signed())
                ]
            with m.Else():
                m.d.comb += [
                    mag.divisor.eq(self.inp.payload.d.as_unsigned() *
                                   shift_amt),
                    mag.dividend.eq(self.inp.payload.n.as_unsigned())
                ]

            with m.If(mag.o):
                # If dividend/divisor are positive, subtract a positive
                # shifted divisor from dividend.
                with m.If((self.inp.payload.sign == Sign.UNSIGNED) |
                          (~self.inp.payload.n[-1] & ~self.inp.payload.d[-1]) |
                          (self.inp.payload.n[-1] & self.inp.payload.d == 0)):
                    m.d.sync += quotient.eq(C(1) * shift_amt)
                    with m.If(self.inp.payload.sign == Sign.SIGNED):
                        # If high bit is set, and, a signed div,
                        # we want to sign-extend.
                        m.d.sync += remainder.eq(self.inp.payload.n.as_signed() -  # noqa: E501
                                                 (self.inp.payload.d.as_signed() * C(1) * shift_amt).as_signed())  # noqa: E501
                    with m.Else():
                        # Otherwise, zero-extend.
                        m.d.sync += remainder.eq(self.inp.payload.n.as_unsigned() -  # noqa: E501
                                                 (self.inp.payload.d.as_unsigned() * C(1) * shift_amt))  # noqa: E501
                # If dividend is negative, but divisor is positive, create a
                # negative shifted divisor and subtract from the dividend.
                with m.If((self.inp.payload.sign == Sign.SIGNED) &
                          self.inp.payload.n[-1] & ~self.inp.payload.d[-1] &
                          ~(self.inp.payload.d == 0 & self.inp.payload.n[-1])):
                    m.d.sync += quotient.eq(C(-1) * shift_amt)
                    m.d.sync += remainder.eq(self.inp.payload.n.as_signed() -
                                             (self.inp.payload.d.as_signed() * C(-1) * shift_amt).as_signed())  # noqa: E501
                # If dividend is positive, but divisor is negative, create a
                # positive shifted divisor and subtract from the dividend.
                with m.If((self.inp.payload.sign == Sign.SIGNED) &
                          ~self.inp.payload.n[-1] & self.inp.payload.d[-1]):
                    m.d.sync += quotient.eq(C(-1) * shift_amt)
                    m.d.sync += remainder.eq(self.inp.payload.n.as_signed() -
                                             (self.inp.payload.d.as_signed() * C(-1) * shift_amt).as_signed())  # noqa: E501
                # If dividend/divisor is negative, subtract a negative
                # shifted divisor and subtract from the dividend.
                with m.If((self.inp.payload.sign == Sign.SIGNED) &
                          self.inp.payload.n[-1] & self.inp.payload.d[-1]):
                    m.d.sync += quotient.eq(C(1) * shift_amt)
                    m.d.sync += remainder.eq(self.inp.payload.n.as_signed() -
                                             (self.inp.payload.d.as_signed() * C(1) * shift_amt).as_signed())  # noqa: E501
            with m.Else():
                m.d.sync += quotient.eq(0)
                with m.If(self.inp.payload.sign == Sign.SIGNED):
                    # If high bit is set, and, a signed div,
                    # we want to sign-extend.
                    m.d.sync += remainder.eq(self.inp.payload.n.as_signed())
                with m.Else():
                    # Otherwise, zero-extend.
                    m.d.sync += remainder.eq(self.inp.payload.n.as_unsigned())

        # Main division loop.
        with m.If(in_progress):
            m.d.sync += iters_left.eq(iters_left - 1)

            shift_amt = (1 << (iters_left - 1).as_unsigned())
            with m.If(self.inp.payload.sign == Sign.SIGNED):
                m.d.comb += [
                    mag.divisor.eq(self.inp.payload.d.as_signed() * shift_amt),
                    mag.dividend.eq(remainder.as_signed())
                ]
            with m.Else():
                m.d.comb += [
                    mag.divisor.eq(self.inp.payload.d.as_unsigned() * shift_amt),  # noqa: E501
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
                                                 (self.inp.payload.d.as_signed() * C(1) * shift_amt).as_signed())  # noqa: E501
                    with m.Else():
                        # Otherwise, zero-extend.
                        m.d.sync += remainder.eq(remainder -
                                                 (self.inp.payload.d.as_unsigned() * C(1) * shift_amt))  # noqa: E501
                # If dividend is negative, but divisor is positive, create a
                # negative shifted divisor and subtract from the dividend.
                with m.If((s_copy == Sign.SIGNED) & a_sign & ~n_sign): 
                    m.d.sync += quotient.eq(quotient + C(-1) * shift_amt)
                    m.d.sync += remainder.eq(remainder -
                                             (self.inp.payload.d.as_signed() * C(-1) * shift_amt).as_signed())  # noqa: E501
                # If dividend is positive, but divisor is negative, create a
                # positive shifted divisor and subtract from the dividend.
                with m.If((s_copy == Sign.SIGNED) & ~a_sign & n_sign):
                    m.d.sync += quotient.eq(quotient + C(-1) * shift_amt)
                    m.d.sync += remainder.eq(remainder -
                                             (self.inp.payload.d.as_signed() * C(-1) * shift_amt).as_signed())  # noqa: E501
                # If dividend/divisor are negative, subtract a negative
                # shifted divisor from dividend.
                with m.If((s_copy == Sign.SIGNED) & a_sign & n_sign):
                    m.d.sync += quotient.eq(quotient + C(1) * shift_amt)
                    m.d.sync += remainder.eq(remainder -
                                             (self.inp.payload.d.as_signed() * C(1) * shift_amt).as_signed())  # noqa: E501

            with m.If(iters_left - 1 == 0):
                m.d.sync += self.outp.valid.eq(1)

        return m


class _MagnitudeComparator(Elaboratable):
    """Compare the magnitude of two signed numbers."""

    def __init__(self, width=8):  # noqa: DOC1
        self.width = width
        self.dividend = Signal(signed(self.width))
        self.divisor = Signal(signed(self.width))
        self.o = Signal()

    def elaborate(self, platform):
        m = Module()

        m.d.comb += self.o.eq(abs(self.divisor) <= abs(self.dividend))

        return m
