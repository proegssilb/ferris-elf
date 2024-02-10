import operator as op
from typing import Optional, Self, Callable
from warnings import warn


def format_picos(ts: float | int) -> str:
    timestamp = float(ts)

    base = "ps"
    scalar: list[tuple[str, int]] = [
        ("ns", 1000),
        ("µs", 1000),
        ("ms", 1000),
        ("s", 1000),
        ("m", 60),
        ("h", 60),
    ]

    for name, offset in scalar:
        if timestamp > offset:
            timestamp /= offset
            base = name
        else:
            break

    # remove any trailing stuff
    timestamp = round(timestamp, 2)

    # fun awesome fact, int decays to float in typeck directly,
    # but is_integer is only implemented on float so if we didn't
    # explicitly call timestamp = float(ts), this could break
    # and typeck would be ok with it :D
    if timestamp.is_integer():
        return f"{timestamp:.0f}{base}"
    else:
        return f"{timestamp:.2f}{base}"


# Base class interferes with our typing
def mk_binop(
    f: Callable[[int, int], int],
) -> Callable[["Picoseconds | int", int], "Picoseconds | int"]:
    return lambda self, other: Picoseconds.from_picos(f(int(self), other))


def mk_prefixop(f: Callable[[int], int]) -> Callable[["Picoseconds | int"], "Picoseconds | int"]:
    return lambda self: Picoseconds.from_picos(f(int(self)))


class Picoseconds(int):
    __slots__ = ()

    def __repr__(self) -> str:
        return f"Picoseconds({int(self)})"

    def __str__(self) -> str:
        return format_picos(self.as_picos())

    def as_picos(self) -> int:
        return self

    def as_nanos(self) -> float:
        return self / 1000

    @classmethod
    def from_nanos(cls, v: float) -> Self:
        return cls(int(v * 1000))

    @classmethod
    def from_picos(cls, v: int) -> Self:
        return cls(v)

    __abs__ = mk_prefixop(op.abs)
    __inv__ = mk_prefixop(op.inv)
    __invert__ = __inv__
    __neg__ = mk_prefixop(op.neg)
    __pos__ = mk_prefixop(op.pos)

    __and__ = mk_binop(op.and_)
    __or__ = mk_binop(op.or_)
    __xor__ = mk_binop(op.xor)

    __add__ = mk_binop(op.add)
    __sub__ = mk_binop(op.sub)
    __floordiv__ = mk_binop(op.floordiv)
    __lshift__ = mk_binop(op.lshift)
    __rshift__ = mk_binop(op.rshift)
    __mod__ = mk_binop(op.mod)
    __mul__ = mk_binop(op.mul)

    __iand__ = __and__
    __ior__ = __or__
    __ixor__ = __xor__

    __iadd__ = __add__
    __isub__ = __sub__
    __ifloordiv__ = __floordiv__
    __ilshift__ = __lshift__
    __irshift__ = __rshift__
    __imod__ = __mod__
    __imul__ = __mul__

    def __truediv__(self: Self, other: Self | int) -> "Picoseconds":
        # Being an int is a mess
        warn(f"Picoseconds.__truediv__() type(other) == {type(other)}. Results may be skewed.")
        return Picoseconds.from_picos(round(int(self) / other))

    # We can't return `Literal[1]` from this, so types will always be incompatible with base class.
    def __pow__(
        self: Self, other: Self | int, modulo: Optional[Self | int] = None
    ) -> "Picoseconds":  # type: ignore[override]
        # We have to do this one by hand because it takes `modulo`
        if other == 0:
            return Picoseconds.from_picos(1)
        res = pow(int(self), other, modulo)
        return Picoseconds.from_picos(int(res))

    __itruediv__ = __truediv__
    __ipow__ = __pow__
