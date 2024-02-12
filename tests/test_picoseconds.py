import math

from hypothesis import given, example
import hypothesis.strategies as st

from ferris_elf.picoseconds import Picoseconds


@given(st.integers())
def test_picos_id(x: int) -> None:
    assert Picoseconds.from_picos(x).as_picos() == x


@given(
    st.floats(
        min_value=-9e300,
        max_value=9e300,
        allow_nan=False,
        allow_infinity=False,
        allow_subnormal=False,
    )
)
@example(9245793277968768.0)
@example(2.814749767114317e16)
@example(-0.53125)
def test_nanos_id(x: float) -> None:
    # Floating point math rarely produces identical/ideal results.
    # Yes, that really is how far off we can be. Don't lose more than 2 hours trying it out.
    delta = Picoseconds.from_nanos(x).as_nanos() - math.floor(x * 1000) / 1000
    assert delta <= 0.01



@given(
    st.floats(
        min_value=-9e300,
        max_value=9e300,
        allow_nan=False,
        allow_infinity=False,
        allow_subnormal=False,
    )
)
def test_nanos_to_picos(x: float) -> None:
    assert Picoseconds.from_nanos(x).as_picos() == int(x * 1000)


@given(st.integers())
def test_picos_to_nanos(x: int) -> None:
    assert Picoseconds.from_picos(x).as_nanos() == x / 1000


@given(st.integers())
def test_format_has_units(x: int) -> None:
    formatted = str(Picoseconds.from_picos(x))
    # 'ps' also ends with 's'.
    assert formatted.endswith("s") or formatted.endswith("m") or formatted.endswith("h")


@given(st.integers(min_value=0, max_value=86_400_000_000_000_000))
def test_format_ranges(val: int) -> None:
    formatted = str(Picoseconds.from_picos(val))
    match val:
        case x if 0 <= x <= 1000:
            assert formatted.endswith("ps")
        case x if 1000 < x <= 1_000_000:
            assert formatted.endswith("ns")
        case x if 1_000_000 < x <= 1_000_000_000:
            assert formatted.endswith("µs")
        case x if 1_000_000_000 < x <= 1_000_000_000_000:
            assert formatted.endswith("ms")
        case x if 1_000_000_000_000 < x <= 60_000_000_000_000:
            assert formatted.endswith("s")
        case x if 60_000_000_000_000 < x <= 3600_000_000_000_000:
            assert formatted.endswith("m")
        case x if 3600_000_000_000_000 < x <= 86_400_000_000_000_000:
            assert formatted.endswith("h")
        case True:
            raise ValueError("Test is not exhaustive.")
