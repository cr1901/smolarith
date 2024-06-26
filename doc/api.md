# `smolarith` API

```{eval-rst}
.. role:: py(code)
   :language: python
```

`smolarith` does not export anything from the top-level; you must import the
module you want to use, perhaps with an alias, e.g.

```{doctest}
>>> import smolarith.mul as mul

```

<!-- Pydoclint's conventions for class attributes (such as enums), Napoleon,
and autodoc interact poorly and generate spurious warnings:
https://github.com/sphinx-doc/sphinx/issues/8664#issuecomment-826910044.

exclude-members is a workaround:
https://github.com/sphinx-doc/sphinx/issues/5365#issuecomment-417027513> -->

## Multiplication

```{eval-rst}
.. automodule:: smolarith.mul
   :exclude-members: UNSIGNED, SIGNED, SIGNED_UNSIGNED
```

## Division


```{eval-rst}
.. automodule:: smolarith.div
   :exclude-members: UNSIGNED, SIGNED, RESTORING, NON_RESTORING
```
