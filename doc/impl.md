(impl)=
# Implementation Notes

## Multiplication

(karatsuba)=
```{todo}
Discuss Karatsuba algorithm.
```

## Division

Wikipedia [discusses](https://en.wikipedia.org/wiki/Division_algorithm#Slow_division_methods)
division algorithms, and the code works just fine. However, I found their
definition of the recurrence relation that governs "slow" (one digit per cycle)
division algorithms confusing. These are my notes for future-me.

(derive-res)=
### Deriving Restoring Division

Consider the following long division, meant to portray any "generic" divide
operation:

(sample-div)=
```{math}
1362 / 14 = 97\bmod{4} \Leftrightarrow N / D = q\bmod{R}
```

If you do this using long division[^1], you can derive the following
intermediate steps:

(derive1)=
```{math}
\begin{array}{rll}
R := 1362 && (initial) \\
R \mathrel{-}= 0 && (0 = (0 * 14) * 1000, R = 1362) \\
R \mathrel{-}= 0 && (0 = (0 * 14) * 100, R = 1362) \\
R \mathrel{-}= 1260 && (1260 = (9 * 14) * 10, R = 102) \\
R \mathrel{-}= 98 && (98 = (7 * 14) * 1, R = 4) \\
\end{array}
```

You can annotate the above to make it generic to any 4 digit base-10
multiplication.

(derive2)=
```{math}
R_0 := N \\
R_1 := R_0 - (q_3 * D * 10^3) \\
R_2 := R_1 - (q_2 * D * 10^2) \\
R_3 := R_2 - (q_1 * D * 10^1) \\
R_4 := R_3 - (q_0 * D * 10^0) \\
```

Mapping the [second](derive2) set of assignments to the [first](derive1):

* {math}`N = 1362`
* {math}`D = 14`
* {math}`q_j` is the {math}`j`th digit of the quotient, where {math}`j` ranges
  from {math}`0` up to {math}`n-1`. _{math}`q_j` must be between `0` and `9`._
  In the above example {math}`q_3 = 0`, {math}`q_2 = 0`, {math}`q_1 = 9`, and
  {math}`q_0 = 7`.
* {math}`R_n` is the remainder after each step, starting at {math}`R_0 = N`
  before division begins. {math}`R_4` is the remainder we want, after the 4th and
  final digit of the dividend. _{math}`R_n` must always be positive._

It turns out[^2] there's a generic [recurrence relation](https://en.wikipedia.org/wiki/Recurrence_relation)
for finding the {math}`j`th remainder of a division where the dividend has {math}`n`
digits:

(rr1)=
```{math}
R_0 := N \\
R_{j+1} := R_j - q_{n - (j + 1)} * 10^{n - (j + 1)} * D \\
```

This formula doesn't actually match Wikipedia's, even after accounting for
arbitrary base ({math}`10 \Rightarrow B`). Somewhere along the line, someone
realized that you can modify the [above equation](rr1) to make it friendlier
to implement on hardware, by making the following substitution:

```{math}
S_j = (10^j) * R_j
```

Note that {math}`S_0 = R_0`. If you substitute[^3] {math}`10^{-j} * S_j` for
{math}`R_j` into the [above equation](rr1), and then multiply both sides by
{math}`10^{-j - 1}` you get a new recurrence relation:

(rr2)=
```{math}
S_0 := N \\
S_{j+1} := 10 * S_j - q_{n - (j + 1)} * 10^n * D \\
```

The {math}`10^n` multipler on {math}`D` doesn't match Wikipedia's definition,
but it _does_ match the accompanying psuedocode. As alluded to earlier, these
recurrence relations work for arbitrary bases. In base-2, since multiplying
by powers of two is equivalent to left-shifting, the relation looks like:

(rr3)=
```{math}
S_0 := N \\
S_{j+1} := (S_j << 1) - q_{n - (j + 1)} * (D << n) \\
```

{math}`q_j` can only be either {math}`0` or {math}`1`, which makes multiplication trivial
(either subtract {math}`0` or {math}`D << n`). Since {math}`S_j` must be positive, we've
turned finding the quotient and remainder into the following Python code:

(resdiv-py)=
```{doctest}
>>> def restoring_div(N, D, n):
...    S = N
...    D = D << n
...    q = 0
...
...    for j in range(n):
...        S = (S << 1) - D
...        if S < 0:
...            S += D
...        else:
...            q |= 1
...        q <<=1
...
...    return (q >> 1, S >> n)
>>>
>>> restoring_div(1362, 14, 12)
(97, 4)

```

This is the core of restoring division. It's called restoring because if
`S < 0` during any step, we have to restore the `D << n` that we subtracted.
We can get rid of this step using non-restoring divison.

(derive-nr)=
### Deriving Non-restoring Division

In restoring division, {math}`q_0` through {math}`q_{n-1}` map precisely to
quotient digits in base-2[^4], where each {math}`q_j` is either {math}`0` or
{math}`1`:

```{math}
q = 2^{n - 1} * q_{n - 1} + 2^{n - 2} * q_{n - 2} + ... + 2^1 * q_1 + 2^0 * q_0
```

If we instead map each {math}`q_j` to either {math}`-1` or {math}`1`, we can
still represent odd numbers:

```{math}
{-1}{-1} = 2^1 * -1 + 2^0 * -1 = -3 \\
{-1}1 = 2^1 * -1 + 2^0 * -1 = -1 \\
1{-1} = 2^1 * -1 + 2^0 * -1 = 1 \\
11 = 2^1 * -1 + 2^0 * -1 = 3 \\
```

The quotient {math}`q` and remainder {math}`r` results one gets from dividing
{math}`N / D` aren't exactly unique. _Without additional constraints_, there
are infinite integers {math}`q` and {math}`r` that satisfy:

(diveq)=
```{math}
N = D * q + r
```

(constraint)=
Our additional constrait is that we want {math}`0 \leq r \lt D`; this [uniquely](https://en.wikipedia.org/wiki/Euclidean_division#Division_theorem) constrains {math}`q`. We can temporarily
relax this constraint however. Given {math}`N` and {math}`D`, when {math}`q`
is even, we can get a new mathematically valid result with an odd {math}`q` if
we set {math}`q := q + 1` and {math}`r := r - D`. Note that {math}`r` will be
negative, which means that for arbitrary {math}`q`, {math}`-D \leq r \lt D`:

```{math}
N = D * (q + 1) + (r - D)
```

Our equation we [used](rr3) for restoring division, reprinted below, still
works[^5] when {math}`q_j` is mapped to either {math}`-1` or {math}`1`:

(rr3-copy)=
```{math}
S_0 := N \\
S_{j+1} := (S_j << 1) - q_{n - (j + 1)} * (D << n) \\
```

For each iteration {math}`j` of the [above](rr3-copy) equation:

* If {math}`S_j` goes/remains positive, we're trying to get successive {math}`S_{j + 1}`
  closer to 0, much the same with restoring division.
* On the other hand, we will tolerate when {math}`S_j` goes/remains negative.
  When calculating {math}`S_{j + 1}` for the next iteration, we attempt to
  get closer to 0 by setting {math}`q_{n - (j + 1)} := -1` the next
  iteration and adding {math}`D`.

(nrdiv-restore)=
If the final {math}`S_n` is negative, we do a final restoring step by setting
{math}`q := q - 1` and {math}`S := S + D`. This will bring the shifted
remainder {math}`S` positive, and make our quotient {math}`q` even, satisfying
our [constraints](constraint). A working implementation looks like such:

(nrdiv-py)=
```{doctest}
>>> def nonrestoring_div(N, D, n):
...     S = N
...     D = D << n
...     q = 0
...     
...     for j in range(n):
...         if S < 0:
...             S = (S << 1) + D
...             q -= 2**(n - j - 1)
...         else:
...             S = (S << 1) - D
...             q += 2**(n - j - 1)
...     
...     if S < 0:
...         S += D
...         q -= 1
...     
...     return (q, S >> n)
>>>
>>> nonrestoring_div(1362, 14, 12)
(97, 4)

```

This technique is called non-restoring division, thanks to the lack of
restoring step to bring {math}`S_j` positive _except possibly at the final
step_.

### Benchmarking

```{note}
This section is still technically correct. However, I originally wrote it
before I made a restoring divider version of {class}`~smolarith.div.MulticycleDiv`.
For general use-cases, a restoring divider (the default as of v0.1.1) wins for
size over a non-restoring divider. Both a restoring and non-restoring
implementation are kept for future testing.

It seems that  the restoring step each iteration doesn't have a perf penalty
when done in parallel in hardware. In fact, the restoring version finishes one
cycle sooner due to the lack of a final restoring step! Additionally, the size
impact of restoring once per iteration seems negligible compared to the
calculations required per iteration of a non-restoring divider (coupled with
the possible final restore step).

At this time, I have not done any experiments on making a signed restoring
divider. There may or may not be the same complications as with a signed
non-restoring divider to satisfy RISC-V semantics.
```

Why would you ever go through all this trouble? Well, here's a benchmark...

```{prompt}
:language: powershell
:prompts: PS C:\\msys64\\home\\William\\Projects\\FPGA\\amaranth\\smolarith>,>>>,...
:modifiers: auto
PS C:\\msys64\\home\\William\\Projects\\FPGA\\amaranth\\smolarith> pdm run
No command is given, default to the Python REPL.
Python 3.11.8 (main, Feb 13 2024, 07:18:52)  [GCC 13.2.0 64 bit (AMD64)] on win32
Type "help", "copyright", "credits" or "license" for more information.
>>> from amaranth.back.verilog import convert
>>> from smolarith.div import MulticycleDiv, LongDivider
>>>
>>> nrdiv_v = convert(MulticycleDiv(32))
>>> with open("nrdiv.v", "w") as fp:  # doctest: +SKIP
...     fp.write(nrdiv_v)
...
53043
>>>
>>> longdiv_v = convert(LongDivider(32))
>>> with open("longdiv.v", "w") as fp:    # doctest: +SKIP
...     fp.write(longdiv_v)
...
76614
>>> exit()  # doctest: +SKIP
PS C:\\msys64\\home\\William\\Projects\\FPGA\\amaranth\\smolarith> yosys -QTp 'tee -q synth_ice40; stat' longdiv.v

-- Parsing `longdiv.v' using frontend ` -vlog2k' --

1. Executing Verilog-2005 frontend: longdiv.v
Parsing Verilog input from `longdiv.v' to AST representation.
Storing AST representation for module `$abstract\top'.
Storing AST representation for module `$abstract\top.mag'.
Successfully finished Verilog frontend.

-- Running command `tee -q synth_ice40; stat' --

3. Printing statistics.

=== top ===

   Number of wires:               2576
   Number of wire bits:          12802
   Number of public wire bits:   12802
   Number of memories:               0
   Number of memory bits:            0
   Number of processes:              0
   Number of cells:               4146
     $scopeinfo                      1
     SB_CARRY                      547
     SB_DFFESR                       9
     SB_DFFSR                       97
     SB_LUT4                      3492

PS C:\\msys64\\home\\William\\Projects\\FPGA\\amaranth\\smolarith> yosys -QTp 'tee -q synth_ice40; stat' nrdiv.v

-- Parsing `nrdiv.v' using frontend ` -vlog2k' --

1. Executing Verilog-2005 frontend: nrdiv.v
Parsing Verilog input from `nrdiv.v' to AST representation.
Storing AST representation for module `$abstract\top'.
Storing AST representation for module `$abstract\top.from_u'.
Storing AST representation for module `$abstract\top.nrdiv'.
Storing AST representation for module `$abstract\top.to_u'.
Successfully finished Verilog frontend.

-- Running command `tee -q synth_ice40; stat' --

3. Printing statistics.

=== top ===

   Number of wires:                894
   Number of wire bits:           2865
   Number of public wires:         894
   Number of public wire bits:    2865
   Number of memories:               0
   Number of memory bits:            0
   Number of processes:              0
   Number of cells:               1162
     $scopeinfo                      3
     SB_CARRY                      251
     SB_DFFESR                     177
     SB_DFFSR                       34
     SB_LUT4                       697

PS C:\\msys64\\home\\William\\Projects\\FPGA\\amaranth\\smolarith> yosys -V
Yosys 0.38+92 (git sha1 84116c9a3, sccache x86_64-w64-mingw32-g++ 13.2.0 -Os)
PS C:\\msys64\\home\\William\\Projects\\FPGA\\amaranth\\smolarith>
```

While I haven't spent much effort optimizing either {class}`~smolarith.div.LongDivider`
or {class}`~smolarith.div.MulticycleDiv`, it's clear that the latter non-restoring
implementation wins on LUT usage alone, with a modest increase in storage
elements (FFs). The extra storage elements should also help with timing
closure. So _without further testing_ for now, I'd recommend using
{class}`~smolarith.div.MulticycleDiv` for your division needs until I can
investigate.

(signedness)=
### Truncating Division And Signedness

You can implement [various types](https://en.wikipedia.org/wiki/Modulo#Variants_of_the_definition)
of division by choosing to constrain {math}`r` in the equation [above](diveq)
relating {math}`N`, {math}`D`, {math}`q`, and {math}`r`.

I initially wrote the long divider implementation with RISC-V in mind. Page
44 of the [RISC-V Unprivileged ISA, V20191213](https://github.com/riscv/riscv-isa-manual/releases/tag/Ratified-IMAFDQC),
states:

> For REM, the sign of the result equals the sign of the dividend.

Wikipedia [calls this](https://en.wikipedia.org/wiki/Modulo#Variants_of_the_definition)
truncating division, and in my experience it is the "natural" version of
division to implement when doing a signed long divider because regardless of
the sign of {math}`N`, you converge toward 0 remainder by subtracting or adding
shifted copies of `D`.

_While the above sections are focused on division with positive numbers_, with
a bit of effort to deal with the restoring step, you can also make
non-restoring division work with signed numbers and just like truncating
division:

```
if ((S < 0) and (N >= 0) and (D > 0)):
    q -= 1
    S += D
elif (S > 0) and (N < 0) and (D > 0):
    q += 1
    S -= D
elif (S > 0) and (N < 0) and (D < 0):
    q -= 1
    S += D
elif (S < 0) and (N >= 0) and (D < 0):
    q += 1
    S -= D
```

However, RISC-V has specific semantics for edge case divisons, list on page 45
of the 2019 manual:

* Division by 0 for arbitrary {math}`x` should return all bits set for the
  quotient, and {math}`x` for the remainder, regardless of signed or unsigned
  division.
* Division of the most negative value by {math}`-1` should return the dividend
  unchanged.

The former of these is easy enough to implement for free in a signed divider,
but the latter is a provision meant for common signed divider implementations:

> Signed division is often implemented using an unsigned division circuit and
> specifying the same overflow result simplifies the hardware.

I started with a signed divider under the assumption that I could spread out
the cost of signed/unsigned conversion. But the poor resource usage of my
long divider, coupled with signed division _indeed_ [commonly](https://www.righto.com/2023/04/)
being implemented using an unsigned division circuit, are making me rethink my
strategy for a non-restoring divider.

## Footnotes

[^1]: I did this using actual pen and paper :). Sadly, trying to format a
traditional long division in MathJax didn't work as well as I'd like.

[^2]: I didn't actually prove this, I just assume the math works out for
arbitrary-widths.

[^3]: Just trust me, I did it by hand.

[^4]: This applies for arbitrary base {math}`B`, but let's stick with base-2.

[^5]: I didn't actually prove this, but I can visualize why the math would
work out if I did a base {math}`-1`/{math}`1` division by hand analogous to
the [one](#deriving-restoring-division) in the restoring section.
   
    I believe non-restoring division in fact works for base 10 as well, where 
{math}`-9 \leq q \lt 10, q \neq 0`. However, I didn't work out the details on paper
about how close to {math}`0` each successive {math}`S_{j+1}` should be.
