# `smolarith` API

`smolarith` does not export anything from the top-level; you must import the
module you want to use, perhaps with an alias, e.g.

```{doctest}
>>> import smolarith.mul as mul

```

## Multiplication

```{eval-rst}
.. automodule:: smolarith.mul
    :exclude-members: PipelinedMul

.. autoclass:: smolarith.mul.PipelinedMul
    :exclude-members: elaborate
```

## Division

```{eval-rst}
.. automodule:: smolarith.div
    :exclude-members: MagnitudeComparator
```
