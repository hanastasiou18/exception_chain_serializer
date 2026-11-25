# exception_chain_serializer

Flattens a Python exception and everything it was chained to into a list of
`(type, message, traceback)` tuples for machine consumption.

```python
from exception_chain_serializer import serialize_exception_chain

try:
    try:
        int("not a number")
    except ValueError as inner:
        raise RuntimeError("parsing failed") from inner
except RuntimeError as exc:
    for entry in serialize_exception_chain(exc):
        print(entry.type)
        print(entry.message)
        print(entry.traceback)
```

The exported names are `serialize_exception_chain` and `SerializedException`.
`SerializedException` is a `NamedTuple` with fields `type`, `message`, and
`traceback`, so each entry compares equal to a plain tuple.

## Why this exists

When an exception crosses a process or network boundary, the traceback object
cannot travel with it: frames hold live references and are not picklable in a
useful way. The usual workaround is to call `traceback.format_exception` and
send a single blob of text, which is fine for humans but awkward to index,
filter, or store in a database column. This library makes the trade-off in the
other direction: it discards the live traceback objects and keeps the formatted
text, but splits the chain into one record per link so a consumer can look at
`result[0].type` without parsing a string.

The chain is walked outermost-first, matching the order a traceback prints:
`result[0]` is the exception that was actually raised, and the innermost cause
is last. The walker follows `__cause__` when it is set (explicit `raise X from
Y`) and falls back to `__context__` otherwise, which is the same rule CPython
uses when printing a traceback.

## The awkward edge

Exception chains can be cyclic if user code assigns `__cause__` or
`__context__` by hand, and a naive walker will loop forever. This library
tracks visited exceptions by `id()` and stops when it sees one again, so a
cycle terminates and each exception appears at most once. That means a
malformed chain is silently truncated rather than reported as an error; if you
need to detect the cycle itself, compare the length of the returned list
against your own count of the chain.

## Performance

The window keeps a bounded buffer, so `push` is constant time and memory does not
grow with the length of the stream. `peak` and `trough` are linear in the window
size, which is the trade that keeps `push` cheap.

