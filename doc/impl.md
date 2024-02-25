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

### Deriving Restoring Division

Consider the following long division, meant to portray any "generic" divide
operation:

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

```{math}
S_0 := N \\
S_{j+1} := (S_j << 1) - q_{n - (j + 1)} * (D << n) \\
```

{math}`q_j` can only be either `0` or `1`, which makes multiplication trivial
(either subtract `0` or `D << n`). Since {math}`S_j` must be positive, we've
turned finding the quotient and remainder into the following Python code:

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

### Deriving Non-restoring Division

```{todo}
Discuss long division implementation vs non-restoring division, and why you
should use the latter in almost all cases.
```

## Footnotes

[^1]: I did this using actual pen and paper :). Sadly, trying to format a
traditional long division in MathJax didn't work as well as I'd like.

[^2]: I didn't actually prove this, I just assume the math works out for
arbitrary-widths.

[^3]: Just trust me, I did it by hand.
