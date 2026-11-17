import unittest

from exception_chain_serializer import SerializedException, serialize_exception_chain


class SerializeExceptionChainTests(unittest.TestCase):
    def test_none_returns_empty_list(self):
        self.assertEqual(serialize_exception_chain(None), [])

    def test_single_exception_has_one_entry(self):
        exc = ValueError("boom")
        result = serialize_exception_chain(exc)
        self.assertEqual(len(result), 1)
        entry = result[0]
        self.assertIsInstance(entry, SerializedException)
        self.assertEqual(entry.type, "ValueError")
        self.assertEqual(entry.message, "boom")
        # No traceback was ever attached to a freshly constructed exception.
        self.assertIn("ValueError", entry.traceback)
        self.assertIn("boom", entry.traceback)

    def test_explicit_cause_is_followed(self):
        inner = KeyError("missing")
        outer = RuntimeError("outer failed")
        outer.__cause__ = inner
        try:
            raise outer
        except RuntimeError as caught:
            result = serialize_exception_chain(caught)
        self.assertEqual([e.type for e in result], ["RuntimeError", "KeyError"])
        self.assertEqual(result[0].message, "outer failed")
        self.assertEqual(result[1].message, "'missing'")

    def test_implicit_context_is_used_when_no_cause(self):
        caught = None
        try:
            try:
                raise ValueError("first")
            except ValueError:
                raise TypeError("second")
        except TypeError as exc:
            caught = exc
        result = serialize_exception_chain(caught)
        self.assertEqual([e.type for e in result], ["TypeError", "ValueError"])
        self.assertIsNone(caught.__cause__)
        self.assertIsNotNone(caught.__context__)

    def test_cause_wins_over_context(self):
        explicit = OSError("explicit")
        implicit = ValueError("implicit")
        outer = RuntimeError("outer")
        outer.__cause__ = explicit
        outer.__context__ = implicit
        result = serialize_exception_chain(outer)
        self.assertEqual([e.type for e in result], ["RuntimeError", "OSError"])
        self.assertEqual(result[1].message, "explicit")

    def test_three_link_chain_order(self):
        innermost = ValueError("root")
        middle = RuntimeError("middle")
        middle.__cause__ = innermost
        outer = LookupError("top")
        outer.__cause__ = middle
        result = serialize_exception_chain(outer)
        self.assertEqual(
            [e.type for e in result],
            ["LookupError", "RuntimeError", "ValueError"],
        )
        self.assertEqual([e.message for e in result], ["top", "middle", "root"])

    def test_cycle_is_broken(self):
        first = ValueError("a")
        second = RuntimeError("b")
        first.__cause__ = second
        second.__cause__ = first
        result = serialize_exception_chain(first)
        self.assertEqual([e.type for e in result], ["ValueError", "RuntimeError"])

    def test_self_referential_context_does_not_hang(self):
        exc = ValueError("self")
        exc.__context__ = exc
        result = serialize_exception_chain(exc)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].type, "ValueError")

    def test_custom_exception_type_name_is_dotted(self):
        class CustomError(Exception):
            pass

        result = serialize_exception_chain(CustomError("custom"))
        self.assertEqual(result[0].type, f"{__name__}.SerializeExceptionChainTests.test_custom_exception_type_name_is_dotted.<locals>.CustomError")

    def test_entries_are_plain_tuples(self):
        # SerializedException is a NamedTuple, so equality with a plain tuple
        # must hold. This is the property that makes the output easy to ship.
        entry = serialize_exception_chain(ValueError("x"))[0]
        self.assertEqual(entry, ("ValueError", "x", entry.traceback))
        self.assertEqual(tuple(entry), ("ValueError", "x", entry.traceback))

    def test_traceback_contains_frame_for_raised_exception(self):
        def raiser():
            raise ValueError("inside")

        try:
            raiser()
        except ValueError as caught:
            result = serialize_exception_chain(caught)
        self.assertEqual(len(result), 1)
        self.assertIn("raiser", result[0].traceback)
        self.assertIn("ValueError: inside", result[0].traceback)

    def test_message_of_exception_with_empty_str(self):
        exc = ValueError()
        result = serialize_exception_chain(exc)
        self.assertEqual(result[0].message, "")
        self.assertEqual(result[0].type, "ValueError")

    def test_str_of_exception_is_used_not_repr(self):
        exc = ValueError("quoted \"text\"")
        result = serialize_exception_chain(exc)
        self.assertEqual(result[0].message, 'quoted "text"')


if __name__ == "__main__":
    unittest.main()
