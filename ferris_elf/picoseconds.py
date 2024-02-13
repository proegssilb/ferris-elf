from dataclasses import dataclass
from typing import Self


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


@dataclass(slots=True, frozen=True)
class Picoseconds:
    _value: int

    def __str__(self) -> str:
        return format_picos(self.as_picos())

    def as_picos(self) -> int:
        return self._value

    def as_nanos(self) -> float:
        return self._value / 1000

    @classmethod
    def from_nanos(cls, v: float) -> Self:
        return cls(int(v * 1000))

    @classmethod
    def from_picos(cls, v: int | float) -> Self:
        return cls(int(v))

    def __int__(self) -> int:
        return self._value
