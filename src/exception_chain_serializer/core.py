"""Core implementation of exception chain serialization.

The public API is :func:`serialize_exception_chain`, which walks an
``Exception.__cause__`` / ``Exception.__context__`` chain and returns a
list of :class:`SerializedException` tuples in *outermost-first* order.

Design decisions
----------------

* We follow ``__cause__`` when it is set (explicit chaining via ``raise X
  from Y``) and fall back to ``__context__`` otherwise (implicit chaining
  inside an ``except`` block). Python's own traceback printer uses the same
  rule; matching it means callers get the same chain they would see on
  stderr, just in a structured form.
* Cycles are broken with a ``seen`` set of ``id()`` values. A self-referential
  ``__context__`` is possible if user code mutates the attributes by hand, and
  an unbounded walk would otherwise hang.
* ``traceback`` is rendered with :mod:`traceback` and returned as a string
  rather than a ``TracebackType`` because the latter is not portable across
  processes (frames hold live references) and is not trivially serializable.
* The list is ordered outermost-first: ``result[0]`` is the exception that was
  actually raised, and the innermost cause is last. That matches how humans
  read a traceback.
"""

from __future__ import annotations

import traceback as _traceback
from typing import List, NamedTuple, Optional


class SerializedException(NamedTuple):
    """A single link in a serialized exception chain.

    Fields are deliberately plain: a dotted type name, the ``str()`` of the
    exception, and the formatted traceback. NamedTuple is used so the value
    is also a plain tuple, which keeps it cheap to pass across process
    boundaries (e.g. through ``multiprocessing`` or JSON adapters).
    """

    type: str
    message: str
    traceback: str


# ``BaseException`` is used rather than ``Exception`` so that ``SystemExit``
# and ``KeyboardInterrupt`` chains can be serialized too. Callers who want to
# filter can do so on the returned ``type`` string.
def _type_name(exc: BaseException) -> str:
    """Return a dotted, fully-qualified class name for *exc*.

    ``type(exc).__qualname__`` is preferred over ``__name__`` because it
    disambiguates nested classes (``Outer.Inner``) and is what modern
    tracebacks print.
    """
    cls = type(exc)
    module = getattr(cls, "__module__", None)
    qualname = getattr(cls, "__qualname__", None) or getattr(cls, "__name__", "Exception")
    if module and module not in ("builtins", "__main__"):
        return f"{module}.{qualname}"
    return qualname


def _next_in_chain(exc: BaseException) -> Optional[BaseException]:
    """Return the exception that *exc* was chained to, or ``None``.

    ``__cause__`` wins when present because it is the explicit, user-chosen
    link. ``__context__`` is the implicit link Python sets when an exception
    is raised inside an ``except`` block. We only fall back to ``__context__``
    when ``__cause__`` is ``None``, mirroring the interpreter's own printer.
    """
    cause = getattr(exc, "__cause__", None)
    if cause is not None:
        return cause
    context = getattr(exc, "__context__", None)
    if context is not None and context is not exc:
        return context
    return None


def serialize_exception_chain(exc: Optional[BaseException]) -> List[SerializedException]:
    """Flatten *exc* and everything it was chained to into a list of tuples.

    Parameters
    ----------
    exc:
        The exception to serialize. ``None`` is accepted and yields an empty
        list, which keeps callers from having to special-case "no exception".

    Returns
    -------
    list of SerializedException
        Outermost-first. ``result[0]`` is *exc* itself. Each entry carries a
        dotted type name, ``str(exception)``, and the traceback formatted by
        :func:`traceback.format_exception`.

    Notes
    -----
    The walk is cycle-safe: an exception whose ``__cause__`` or
    ``__context__`` points back at an earlier node terminates instead of
    looping forever. The cycle-breaking node is still included in the output
    once; it is only the *repeat* that is dropped.
    """
    if exc is None:
        return []

    result: List[SerializedException] = []
    seen: set[int] = set()
    current: Optional[BaseException] = exc

    while current is not None:
        marker = id(current)
        if marker in seen:
            break
        seen.add(marker)

        # ``format_exception`` needs the exception and its traceback. Passing
        # ``chain=False`` keeps the output to this one link; we are building
        # the chain ourselves and do not want the printer to duplicate it.
        formatted = "".join(
            _traceback.format_exception(
                type(current), current, current.__traceback__, chain=False
            )
        )
        result.append(
            SerializedException(
                type=_type_name(current),
                message=str(current),
                traceback=formatted,
            )
        )
        current = _next_in_chain(current)

    return result
