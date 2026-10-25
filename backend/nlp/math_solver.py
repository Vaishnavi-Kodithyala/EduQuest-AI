"""
Week 10 - Grade 6 maths calculations, with working.

The textbook passages can explain what a fraction is, but no passage contains
the answer to "what is 1/3 + 1/6". Calculation questions are recognised by
pattern and solved exactly here, showing the steps the chapter teaches:

    arithmetic        "what is 1/3 + 1/6", "-4 + -3", "(+6) - (-9)", "3/4 of 20"
    simplest form     "simplify 12/16"
    comparing         "which is greater, 3/5 or 3/7"
    primes            "is 29 prime", "factors of 24", "prime factorisation of 56"
    common factors    "HCF of 12 and 18", "are 4 and 9 co-prime", "LCM of 4 and 6"
    perimeter / area  "perimeter of a rectangle 8 cm by 5 cm", "area of a square of side 6 m"

Everything uses Python's exact Fraction arithmetic, so 1/3 + 1/6 is 1/2 and
not 0.49999. Each answer names the chapter it belongs to, so the student can
go back and read the method.
"""

from __future__ import annotations

import ast
import math
import re
from dataclasses import dataclass, field
from fractions import Fraction

# Chapter for each kind of calculation.
LESSON = {
    "primes": "g6-math-5",
    "fractions": "g6-math-7",
    "integers": "g6-math-10",
    "measurement": "g6-math-6",
    "numbers": "g6-math-3",
}

LIMIT = 10**9   # keep factor searches instant


@dataclass
class MathAnswer:
    answer: str
    working: list[str] = field(default_factory=list)
    topic: str = "numbers"

    @property
    def lesson_id(self) -> str:
        return LESSON[self.topic]


# --- formatting ------------------------------------------------------------
def fmt(value: Fraction) -> str:
    """3/1 -> '3', 7/2 -> '7/2', -5 -> '-5'."""
    value = Fraction(value)
    if value.denominator == 1:
        return str(value.numerator)
    return f"{value.numerator}/{value.denominator}"


def fmt_mixed(value: Fraction) -> str:
    """7/2 -> '7/2 = 3 1/2'; proper fractions and integers unchanged."""
    value = Fraction(value)
    text = fmt(value)
    if value.denominator != 1 and abs(value) > 1:
        whole = int(abs(value)) * (1 if value > 0 else -1)
        rest = abs(value) - abs(whole)
        text += f" = {whole} {fmt(rest)}"
    return text


# --- normalising the question ---------------------------------------------
WORDS = [
    (r"\bmultiplied by\b", "*"), (r"\btimes\b", "*"), (r"\bdivided by\b", "/"),
    (r"\bplus\b", "+"), (r"\bminus\b", "-"), (r"\badded to\b", "+"),
    (r"(?<=\d)\s*[x×]\s*(?=[\d(+-])", "*"), (r"÷", "/"), (r"[−–]", "-"),
]


def normalise(text: str) -> str:
    out = text.lower().replace("’", "'")
    for pattern, repl in WORDS:
        out = re.sub(pattern, f" {repl} ", out)
    return re.sub(r"\s+", " ", out).strip()


NUM = r"[+-]?\d+(?:\s*/\s*\d+)?"


def to_fraction(token: str) -> Fraction:
    return Fraction(token.replace(" ", ""))


# --- number theory ---------------------------------------------------------
def factors(n: int) -> list[int]:
    small, large = [], []
    for d in range(1, math.isqrt(n) + 1):
        if n % d == 0:
            small.append(d)
            if d != n // d:
                large.append(n // d)
    return small + large[::-1]


def prime_factors(n: int) -> list[int]:
    out, d = [], 2
    while d * d <= n:
        while n % d == 0:
            out.append(d)
            n //= d
        d += 1
    if n > 1:
        out.append(n)
    return out


def _numbers(text: str) -> list[int]:
    return [int(x) for x in re.findall(r"\d+", text)]


def solve_primes(q: str) -> MathAnswer | None:
    m = re.search(r"\bis (\d+) (?:a )?prime\b", q)
    if m:
        n = int(m.group(1))
        if n < 2:
            reason = "1 has only one factor, itself." if n == 1 else "0 is not prime."
            return MathAnswer(f"No, {n} is not prime.",
                              [f"A prime number has exactly two factors. {reason}"], "primes")
        if n > LIMIT:
            return None
        fs = factors(n)
        if len(fs) == 2:
            return MathAnswer(f"Yes, {n} is a prime number.",
                              [f"Its only factors are 1 and {n}."], "primes")
        return MathAnswer(f"No, {n} is not prime - it is composite.",
                          [f"Factors of {n}: {', '.join(map(str, fs))}.",
                           f"For example, {n} = {fs[1]} x {n // fs[1]}."], "primes")

    m = re.search(r"\bprime factori[sz]ation of (\d+)|\bprime factors of (\d+)", q)
    if m:
        n = int(m.group(1) or m.group(2))
        if n < 2 or n > LIMIT:
            return None
        pf = prime_factors(n)
        steps, rest = [], n
        for p in pf:
            steps.append(f"{rest} / {p} = {rest // p}")
            rest //= p
        return MathAnswer(f"{n} = {' x '.join(map(str, pf))}",
                          ["Keep dividing by the smallest prime that divides the number:", *steps],
                          "primes")

    m = re.search(r"\bare (\d+) and (\d+) co-?prime\b", q)
    if m:
        a, b = int(m.group(1)), int(m.group(2))
        g = math.gcd(a, b)
        common = factors(g)
        if g == 1:
            return MathAnswer(f"Yes, {a} and {b} are co-prime.",
                              ["Their only common factor is 1."], "primes")
        return MathAnswer(f"No, {a} and {b} are not co-prime.",
                          [f"They share the common factor{'s' if len(common) > 2 else ''} {', '.join(map(str, common[1:]))}."],
                          "primes")

    m = re.search(r"\b(hcf|gcd|highest common factor|greatest common (?:factor|divisor)|common factors)\b(?: of)? ([\d ,and]+)", q)
    if m:
        nums = _numbers(m.group(2))
        if len(nums) >= 2 and max(nums) <= LIMIT and min(nums) > 0:
            g = nums[0]
            for x in nums[1:]:
                g = math.gcd(g, x)
            common = factors(g)
            label = " and ".join(map(str, nums))
            return MathAnswer(f"The highest common factor of {label} is {g}.",
                              [*(f"Factors of {x}: {', '.join(map(str, factors(x)))}" for x in nums),
                               f"Common factors: {', '.join(map(str, common))}"],
                              "primes")

    m = re.search(r"\b(lcm|lowest common multiple|least common multiple|common multiples)\b(?: of)? ([\d ,and]+)", q)
    if m:
        nums = _numbers(m.group(2))
        if len(nums) >= 2 and max(nums) <= 10**6 and min(nums) > 0:
            lcm = nums[0]
            for x in nums[1:]:
                lcm = lcm * x // math.gcd(lcm, x)
            label = " and ".join(map(str, nums))
            first = [lcm * k for k in range(1, 4)]
            return MathAnswer(f"The lowest common multiple of {label} is {lcm}.",
                              [*(f"Multiples of {x}: {', '.join(str(x * k) for k in range(1, 7))}, ..." for x in nums),
                               f"Common multiples: {', '.join(map(str, first))}, ..."],
                              "primes")

    m = re.search(r"\b(?:what are the |list the |find the )?factors of (\d+)\b", q)
    if m and "prime" not in q and "common" not in q:
        n = int(m.group(1))
        if 0 < n <= LIMIT:
            fs = factors(n)
            pairs = [f"{d} x {n // d}" for d in fs if d <= n // d]
            return MathAnswer(f"Factors of {n}: {', '.join(map(str, fs))}",
                              [f"Factor pairs: {', '.join(pairs)}."], "primes")
    return None


def solve_measurement(q: str) -> MathAnswer | None:
    unit_match = re.search(r"\b(mm|cm|m|km)\b", q)
    unit = unit_match.group(1) if unit_match else "units"
    sq = f"sq {unit}" if unit != "units" else "square units"

    m = re.search(r"\b(perimeter|area) of (?:a |the )?rectangle\b", q)
    if m:
        nums = [Fraction(x) for x in re.findall(r"\d+(?:\.\d+)?", q[m.end():])]
        if len(nums) >= 2:
            length, breadth = nums[0], nums[1]
            if m.group(1) == "perimeter":
                p = 2 * (length + breadth)
                return MathAnswer(f"Perimeter = {fmt_float(p)} {unit}",
                                  ["Perimeter of a rectangle = 2 x (length + breadth)",
                                   f"= 2 x ({fmt_float(length)} + {fmt_float(breadth)}) = {fmt_float(p)} {unit}"],
                                  "measurement")
            a = length * breadth
            return MathAnswer(f"Area = {fmt_float(a)} {sq}",
                              ["Area of a rectangle = length x breadth",
                               f"= {fmt_float(length)} x {fmt_float(breadth)} = {fmt_float(a)} {sq}"],
                              "measurement")

    m = re.search(r"\b(perimeter|area) of (?:a |the )?square\b", q)
    if m:
        nums = [Fraction(x) for x in re.findall(r"\d+(?:\.\d+)?", q[m.end():])]
        if nums:
            side = nums[0]
            if m.group(1) == "perimeter":
                return MathAnswer(f"Perimeter = {fmt_float(4 * side)} {unit}",
                                  ["Perimeter of a square = 4 x side",
                                   f"= 4 x {fmt_float(side)} = {fmt_float(4 * side)} {unit}"],
                                  "measurement")
            return MathAnswer(f"Area = {fmt_float(side * side)} {sq}",
                              ["Area of a square = side x side",
                               f"= {fmt_float(side)} x {fmt_float(side)} = {fmt_float(side * side)} {sq}"],
                              "measurement")
    return None


def fmt_float(value: Fraction) -> str:
    value = Fraction(value)
    if value.denominator == 1:
        return str(value.numerator)
    return f"{float(value):g}"


def solve_fraction_tasks(q: str) -> MathAnswer | None:
    m = re.search(rf"\b(?:simplify|simplest form of|lowest terms of|reduce)\s+({NUM})", q)
    if m and "/" in m.group(1):
        num, den = [int(x) for x in m.group(1).replace(" ", "").split("/")]
        if den == 0:
            return None
        g = math.gcd(num, den)
        simple = Fraction(num, den)
        return MathAnswer(f"{num}/{den} in simplest form is {fmt(simple)}",
                          [f"The highest common factor of {num} and {den} is {g}.",
                           f"Divide both by {g}: {num} / {g} = {num // g}, {den} / {g} = {den // g}."],
                          "fractions")

    m = re.search(rf"\b(greater|bigger|larger|smaller|less)\b[ ,:]*(?:is )?(?:between )?({NUM}) (?:or|and) ({NUM})", q) \
        or re.search(rf"\bcompare ({NUM}) (?:and|with|to) ({NUM})", q)
    if m:
        groups = m.groups()
        word = groups[0] if len(groups) == 3 else "greater"
        a_text, b_text = groups[-2], groups[-1]
        a, b = to_fraction(a_text), to_fraction(b_text)
        topic = "fractions" if "/" in a_text + b_text else "integers"
        if a == b:
            return MathAnswer(f"{fmt(a)} and {fmt(b)} are equal.", [], topic)
        big, small = (a, b) if a > b else (b, a)
        want_small = word in ("smaller", "less")
        pick = small if want_small else big
        working = []
        if topic == "fractions":
            working.append(f"As decimals: {fmt(a)} = {float(a):.3f}, {fmt(b)} = {float(b):.3f}.")
        else:
            working.append(f"On the number line, {fmt(big)} is to the right of {fmt(small)}.")
        return MathAnswer(f"{fmt(pick)} is {'smaller' if want_small else 'greater'}.", working, topic)
    return None


ALLOWED = (ast.Expression, ast.BinOp, ast.UnaryOp, ast.Constant, ast.Add, ast.Sub,
           ast.Mult, ast.Div, ast.USub, ast.UAdd)


def evaluate(expr: str) -> Fraction:
    tree = ast.parse(expr, mode="eval")
    for node in ast.walk(tree):
        if not isinstance(node, ALLOWED):
            raise ValueError("not plain arithmetic")
        if isinstance(node, ast.Constant) and not isinstance(node.value, int):
            raise ValueError("only whole numbers and fractions")

    def ev(node):
        if isinstance(node, ast.Expression):
            return ev(node.body)
        if isinstance(node, ast.Constant):
            return Fraction(node.value)
        if isinstance(node, ast.UnaryOp):
            v = ev(node.operand)
            return -v if isinstance(node.op, ast.USub) else v
        left, right = ev(node.left), ev(node.right)
        if isinstance(node.op, ast.Add):
            return left + right
        if isinstance(node.op, ast.Sub):
            return left - right
        if isinstance(node.op, ast.Mult):
            return left * right
        if right == 0:
            raise ZeroDivisionError
        return left / right

    return ev(tree)


def solve_arithmetic(q: str) -> MathAnswer | None:
    # "3/4 of 20"
    m = re.search(rf"({NUM}) of (\d+)\b", q)
    if m and "/" in m.group(1):
        part, whole = to_fraction(m.group(1)), int(m.group(2))
        value = part * whole
        return MathAnswer(f"{fmt(part)} of {whole} = {fmt_mixed(value)}",
                          [f"{fmt(part)} of {whole} means {fmt(part)} x {whole}",
                           f"= {part.numerator} x {whole} / {part.denominator} = {fmt_mixed(value)}"],
                          "fractions")

    candidate = re.sub(r"^(what is|what's|whats|calculate|find|solve|work out|evaluate|compute|add|subtract)\s+", "", q)
    candidate = candidate.rstrip("?.! =").strip()
    if not re.fullmatch(r"[\d\s+\-*/().]+", candidate):
        return None
    if not re.search(r"\d\s*\)?\s*[+\-*/]\s*\(?\s*[+-]?\d", candidate):
        return None  # a single number is not a calculation
    try:
        value = evaluate(candidate)
    except ZeroDivisionError:
        # Answer it rather than fall through to the textbook search.
        return MathAnswer(f"{candidate} has no answer: we cannot divide by zero.",
                          ["Division asks which number times the divisor gives the dividend.",
                           "No number multiplied by 0 gives anything except 0, so there is no answer."],
                          "numbers")
    except (SyntaxError, ValueError):
        return None

    has_fraction = "/" in candidate
    has_negative = bool(re.search(r"(^|[(*/+\-]\s*)-\s*\d", candidate)) or value < 0
    topic = "fractions" if has_fraction else "integers" if has_negative else "numbers"
    if has_fraction:
        working = _fraction_working(candidate)
    else:
        working = _integer_working(candidate, value) if has_negative else []
    steps = _operation_steps(candidate)
    if len(steps) > 1 and not (has_fraction and working):
        working = [_order_rule(candidate), *steps, *working]
    return MathAnswer(f"{candidate} = {fmt_mixed(value)}", working, topic)


OPERATORS = {ast.Add: "+", ast.Sub: "-", ast.Mult: "×", ast.Div: "÷"}


def _order_rule(expr: str) -> str:
    if "(" in expr:
        return "Work out the brackets first, then × and ÷, then + and -."
    ops = [n for n in ast.walk(ast.parse(expr, mode="eval")) if isinstance(n, ast.BinOp)]
    fraction = lambda n: (isinstance(n.op, ast.Div) and isinstance(n.left, ast.Constant)
                          and isinstance(n.right, ast.Constant))
    times_or_divide = any(isinstance(n.op, (ast.Mult, ast.Div)) and not fraction(n) for n in ops)
    plus_or_minus = any(isinstance(n.op, (ast.Add, ast.Sub)) for n in ops)
    if times_or_divide and plus_or_minus:
        return "Multiply and divide before you add and subtract."
    return "Work from left to right."


def _operation_steps(expr: str) -> list[str]:
    """One line per operation, in the order it is worked out: 2 + 3 × 4 -> 3 × 4 = 12, 2 + 12 = 14."""
    steps: list[str] = []

    def show(v: Fraction) -> str:
        return f"({fmt(v)})" if v < 0 else fmt(v)

    def walk(node) -> Fraction:
        if isinstance(node, ast.Expression):
            return walk(node.body)
        if isinstance(node, ast.Constant):
            return Fraction(node.value)
        if isinstance(node, ast.UnaryOp):
            v = walk(node.operand)
            return -v if isinstance(node.op, ast.USub) else v
        if (isinstance(node.op, ast.Div) and isinstance(node.left, ast.Constant)
                and isinstance(node.right, ast.Constant) and node.right.value):
            return Fraction(node.left.value, node.right.value)   # a fraction like 1/3, not a step
        left, right = walk(node.left), walk(node.right)
        value = {ast.Add: left + right, ast.Sub: left - right, ast.Mult: left * right}.get(
            type(node.op), left / right if right else None)
        if value is None:
            raise ZeroDivisionError
        steps.append(f"{fmt(left)} {OPERATORS[type(node.op)]} {show(right)} = {fmt(value)}")
        return value

    try:
        walk(ast.parse(expr, mode="eval"))
    except (SyntaxError, ZeroDivisionError):
        return []
    return steps


def _fraction_working(expr: str) -> list[str]:
    """Common-denominator working for 'a/b + c/d' and 'a/b - c/d'."""
    m = re.fullmatch(r"\s*(\d+)\s*/\s*(\d+)\s*([+-])\s*(\d+)\s*/\s*(\d+)\s*", expr)
    if not m:
        return []
    a, b, op, c, d = int(m.group(1)), int(m.group(2)), m.group(3), int(m.group(4)), int(m.group(5))
    if b == 0 or d == 0:
        return []
    common = b * d // math.gcd(b, d)
    a2, c2 = a * (common // b), c * (common // d)
    total = a2 + c2 if op == "+" else a2 - c2
    steps = [f"Use a common denominator: the LCM of {b} and {d} is {common}."]
    if common != b or common != d:
        steps.append(f"{a}/{b} = {a2}/{common} and {c}/{d} = {c2}/{common}")
    steps.append(f"{a2}/{common} {op} {c2}/{common} = {total}/{common}")
    if total and math.gcd(abs(total), common) > 1:
        steps.append(f"Simplify: {total}/{common} = {fmt(Fraction(total, common))}")
    return steps


def _integer_working(expr: str, value: Fraction) -> list[str]:
    if re.search(r"-\s*\(?\s*-", expr):
        return ["Subtracting a negative number is the same as adding the positive number."]
    if "-" in expr and value != 0:
        return ["Think of positive and negative tokens: each + and - pair cancels to zero."]
    return []


SOLVERS = (solve_primes, solve_measurement, solve_fraction_tasks, solve_arithmetic)


def solve(text: str) -> MathAnswer | None:
    """Solve a Grade 6 calculation question, or return None if it is not one."""
    if not text or not re.search(r"\d", text):
        return None
    q = normalise(text)
    for solver in SOLVERS:
        try:
            result = solver(q)
        except (ValueError, ZeroDivisionError, OverflowError):
            result = None
        if result is not None:
            # Display multiplication the way the textbook writes it.
            result.answer = _times(result.answer)
            result.working = [_times(line) for line in result.working]
            return result
    return None


def _times(text: str) -> str:
    return re.sub(r"\s*\*\s*|(?<=[\d)])\s+x\s+(?=[\d(])", " × ", text)
