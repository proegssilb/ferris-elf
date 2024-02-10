from functools import partialmethod
import operator as op

from hypothesis.stateful import RuleBasedStateMachine, invariant, rule, precondition
import hypothesis.strategies as st

from ferris_elf.picoseconds import Picoseconds


def mk_binop_test(f, min_operand=0, max_operand=999_999):
    def binop_test(self, x: int):
        self.uut = f(self.uut, x)
        self.model = f(self.model, x)

    strat = st.integers(min_value=min_operand, max_value=max_operand)

    # Hypothesis uses __name__ for failed test printing. This helps readability.
    binop_test.__name__ = f.__name__

    # Manually apply the decorator
    return rule(x=strat)(binop_test)


def mk_incr_op_test(f, min_operand=0, max_operand=999_999):
    def incr_op_test(self, x: int):
        self.uut = f(self.uut, x)
        self.model = f(self.model, x)

    strat = st.integers(min_value=min_operand, max_value=max_operand)

    # Hypothesis uses __name__ for failed test printing. This helps readability.
    incr_op_test.__name__ = f.__name__

    # Manually apply the decorator
    return rule(x=strat)(incr_op_test)


def mk_prefix_op_test(f):
    def prefix_op_test(self):
        self.uut = f(self.uut)
        self.model = f(self.model)

    # Hypothesis uses __name__ for failed test printing. This helps readability.
    prefix_op_test.__name__ = f.__name__

    # Manually apply the decorator
    return rule()(prefix_op_test)


class PicosecondsMath(RuleBasedStateMachine):
    uut = Picoseconds.from_picos(0)
    model = 0

    @rule(x=st.integers(min_value=0, max_value=999_999_999))
    def set_picos(self, x: int):
        self.uut = Picoseconds.from_picos(x)
        self.model = x

    @rule(x=st.integers(min_value=0, max_value=999_999_999))
    def set_nanos(self, x: int):
        self.uut = Picoseconds.from_nanos(x)
        self.model = x * 1000

    and_ = mk_binop_test(op.and_)
    or_ = mk_binop_test(op.or_)
    xor = mk_binop_test(op.xor)

    add = mk_binop_test(op.add)
    sub = mk_binop_test(op.sub)
    floordiv = mk_binop_test(op.floordiv, min_operand=1)
    lshift = mk_binop_test(op.lshift, max_operand=20)  # Don't burn many GiB of RAM
    rshift = mk_binop_test(op.rshift)
    mod = mk_binop_test(op.mod, min_operand=1)
    mul = mk_binop_test(op.mul)
    pow = mk_binop_test(op.pow, min_operand=1, max_operand=20)

    iand = mk_incr_op_test(op.iand)
    ior = mk_incr_op_test(op.ior)
    ixor = mk_incr_op_test(op.ixor)

    iadd = mk_incr_op_test(op.iadd)
    isub = mk_incr_op_test(op.isub)
    ifloordiv = mk_incr_op_test(op.ifloordiv, min_operand=1)
    ilshift = mk_incr_op_test(op.ilshift, min_operand=1, max_operand=20)  # Don't burn hordes of RAM
    irshift = mk_incr_op_test(op.irshift, min_operand=1)
    imod = mk_incr_op_test(op.imod, min_operand=1)
    imul = mk_incr_op_test(op.imul)
    ipow = mk_incr_op_test(op.ipow, min_operand=1, max_operand=20)

    abs = mk_prefix_op_test(op.abs)
    invert = mk_prefix_op_test(op.invert)
    inv = mk_prefix_op_test(op.inv)
    neg = mk_prefix_op_test(op.neg)
    pos = mk_prefix_op_test(op.pos)

    @precondition(lambda self: self.uut < 1.5e150)
    @rule(x=st.integers(min_value=1))
    def truediv(self, x):
        self.uut = self.uut / x
        self.model = round(self.model / x)

    @precondition(lambda self: self.uut < 1.5e150)
    @rule(x=st.integers(min_value=1))
    def itruediv(self, x):
        self.uut /= x
        self.model /= x
        self.model = round(self.model)

    @invariant()
    def check_drift(self):
        assert isinstance(self.uut, Picoseconds)
        assert isinstance(self.model, int)
        assert self.uut == Picoseconds.from_picos(self.model)

        # It's impossible to stop hypothesis from generating overflows with __pow__,
        # but they're kinda out of scope of our testing.
        while self.model > 9e9:
            self.uut //= 1000
            self.model //= 1000


TestPicosecondsMath = PicosecondsMath.TestCase


ignored_ops = (
    op.lt,
    op.le,
    op.eq,
    op.ne,
    op.ge,
    op.gt,
    op.and_,
    op.or_,
    op.not_,
    op.truth,
    op.is_,
    op.is_not,
    op.matmul,
    op.concat,
    op.contains,
    op.concat,
    op.countOf,
    op.delitem,
    op.setitem,
    op.getitem,
    op.index,
    op.indexOf,
    op.length_hint,
    op.call,
    op.attrgetter,
    op.itemgetter,
    op.methodcaller,
    op.iconcat,
    op.imatmul,
)


def test_all_operators_tested() -> None:
    ignored_names = [i.__name__ for i in ignored_ops]
    for func_name in dir(op):
        if func_name.startswith("_") or func_name in ignored_names:
            continue
        assert hasattr(PicosecondsMath, func_name)
