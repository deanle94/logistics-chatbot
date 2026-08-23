# Python Coding Rules — For Humans & Coding Agents

## Why this file exists

Python is loose by default — no compiler forces good habits. These rules close that gap,
so code stays readable and safe to change, whether written by a person or an AI agent.

Each rule: **Rule → Bad → Good → Self-check**.

---

## 1 — Type Hints Everywhere

**Rule:** Every function signature must have typed params and a return type — otherwise the
agent (or teammate) has to read the function body just to know what to pass in.

**Bad**
```python
def get_user(id):
    return db.find(id)
```

**Good**
```python
def get_user(user_id: int) -> User | None:
    return db.find(user_id)
```

**Self-check**
- [ ] `mypy` / `pyright` runs clean on this file
- [ ] No function is missing a return type (`-> None` if it returns nothing)

---

## 2 — Formatting & Linting Are Automatic, Not Manual

**Rule:** Style is enforced by tooling (`ruff check` + `ruff format`), not by eye — otherwise
every PR wastes time on spacing debates instead of logic.

**Bad**
```python
def add(a,b):
  return a+b
```

**Good**
```python
def add(a: int, b: int) -> int:
    return a + b
```

**Self-check**
- [ ] `ruff check .` and `ruff format --check .` both pass
- [ ] Line length matches the project's `pyproject.toml` setting

---

## 3 — One Exception Type, Never Bare `except`

**Rule:** Catch the specific error you expect — otherwise you silently swallow bugs that
should have crashed loudly.

**Bad**
```python
try:
    process(data)
except:
    pass
```

**Good**
```python
try:
    process(data)
except ValidationError as exc:
    logger.warning("Bad data: %s", exc)
    raise
```

**Self-check**
- [ ] No bare `except:` or `except Exception:` without re-raising or logging
- [ ] Every caught exception names a specific type

---

## 4 — Never Use a Mutable Default Argument

**Rule:** Default args are created once, at function definition — a mutable one leaks state
across every call, causing bugs that only show up randomly.

**Bad**
```python
def add_item(item, cart=[]):
    cart.append(item)
    return cart
```

**Good**
```python
def add_item(item: str, cart: list[str] | None = None) -> list[str]:
    cart = cart or []
    cart.append(item)
    return cart
```

**Self-check**
- [ ] No `def f(x=[])`, `def f(x={})`, or `def f(x=set())` anywhere

---

## 5 — Depend on Abstractions, Not Concrete Services

**Rule:** Pass dependencies in (constructor/param), don't reach out and create them inside —
otherwise the function can't be tested or swapped without editing its internals.

**Bad**
```python
class OrderService:
    def __init__(self):
        self.db = PostgresDB()  # hardcoded
```

**Good**
```python
class OrderService:
    def __init__(self, db: OrderRepository):
        self.db = db  # any repo that fits the interface
```

**Self-check**
- [ ] No class constructs its own DB/HTTP client/file handle internally
- [ ] Dependencies are passed in, so tests can swap in a fake

---

## 6 — Resources Always Go Through a Context Manager

**Rule:** Files, sockets, and DB connections must use `with` — otherwise a crash mid-function
leaks the resource forever.

**Bad**
```python
f = open("data.csv")
data = f.read()
f.close()
```

**Good**
```python
with open("data.csv") as f:
    data = f.read()
```

**Self-check**
- [ ] Every `open()`, connection, or lock uses `with`
- [ ] No manual `.close()` call outside a `finally` block

---

## 7 — Log, Never `print`, in Production Code

**Rule:** `print` has no level, timestamp, or destination control — otherwise you can't filter
noise or ship logs anywhere useful.

**Bad**
```python
print("user created:", user.id)
```

**Good**
```python
logger.info("user created", extra={"user_id": user.id})
```

**Self-check**
- [ ] No `print()` outside of CLI-facing scripts
- [ ] Every module gets its logger via `logging.getLogger(__name__)`

---

## 8 — No Dynamic Code Execution on Untrusted Input

**Rule:** `eval`, `exec`, and unsafe `pickle.load` run arbitrary code — otherwise any user
input becomes a remote-code-execution hole.

**Bad**
```python
result = eval(user_input)
```

**Good**
```python
import ast
result = ast.literal_eval(user_input)  # only literals, never code
```

**Self-check**
- [ ] No `eval`, `exec`, or `pickle.load` on data from outside the process
- [ ] `pip-audit` runs in CI and passes

---

## 9 — One Function, One Job

**Rule:** A function should do exactly what its name says, nothing more — otherwise you can't
reuse or test one piece of logic without dragging the rest along.

**Bad**
```python
def process_order(order):
    validate(order)
    total = sum(i.price for i in order.items)
    db.save(order)
    send_email(order.customer, total)
    return total
```

**Good**
```python
def calculate_total(order: Order) -> float:
    return sum(item.price for item in order.items)

def process_order(order: Order) -> float:
    validate(order)
    total = calculate_total(order)
    order_repo.save(order)
    notifier.send_confirmation(order.customer, total)
    return total
```

**Self-check**
- [ ] Function name describes the one thing it does — no "and" needed to describe it
- [ ] Function fits on one screen (~30 lines); if not, split it

---

## 10 — Docstrings Say *Why*, Not *What*

**Rule:** Every public function/class needs a docstring explaining intent and edge cases —
the code already shows *what* it does; only the docstring can explain *why*.

**Bad**
```python
def retry(fn, times):
    # loops and calls fn
    for _ in range(times):
        try:
            return fn()
        except Exception:
            continue
```

**Good**
```python
def retry(fn: Callable[[], T], times: int = 3) -> T:
    """Retry a flaky call up to `times` before giving up.

    Used for network calls that fail transiently (DNS blips, timeouts).
    Raises the last exception if all attempts fail.
    """
    last_exc: Exception | None = None
    for _ in range(times):
        try:
            return fn()
        except Exception as exc:
            last_exc = exc
    raise last_exc
```

**Self-check**
- [ ] Every public function/class has a docstring
- [ ] Docstring explains intent/edge cases, not a line-by-line narration

---

## 11 — No God Modules

**Rule:** Split code by responsibility into separate modules — otherwise one file becomes a
dumping ground nobody dares touch or fully understands.

**Bad**
```python
# utils.py — 2000 lines: db helpers, email, auth, date parsing, PDF export...
```

**Good**
```python
# db.py       — database access
# email.py    — sending emails
# auth.py     — authentication
# dates.py    — date parsing/formatting
```

**Self-check**
- [ ] Each module's name tells you exactly what's inside, with no surprises
- [ ] No module mixes unrelated concerns (e.g. DB code + email code)

---

## 12 — Favor Composition Over Inheritance

**Rule:** Build behavior by combining small objects, not by growing a deep class hierarchy —
otherwise a change three levels up breaks classes you've never seen.

**Bad**
```python
class Animal:
    def make_sound(self): ...

class Dog(Animal):
    def make_sound(self): return "Woof"

class RobotDog(Dog):  # inherits bark it shouldn't have
    def make_sound(self): return "Beep"
```

**Good**
```python
class SoundMaker(Protocol):
    def make_sound(self) -> str: ...

class Dog:
    def __init__(self, sound: SoundMaker):
        self._sound = sound

    def make_sound(self) -> str:
        return self._sound.make_sound()
```

**Self-check**
- [ ] No inheritance chain deeper than 2 levels
- [ ] Shared behavior is a composed object/function, not a shared base class

---

## 13 — Prefer Immutable Data

**Rule:** Data objects should be frozen/read-only by default — otherwise any function anywhere
can mutate shared state, and bugs become impossible to trace back.

**Bad**
```python
class Config:
    def __init__(self):
        self.debug = False

config = Config()
config.debug = True  # any code, anywhere, can flip this
```

**Good**
```python
@dataclass(frozen=True)
class Config:
    debug: bool = False

config = Config(debug=True)
new_config = replace(config, debug=False)  # explicit, traceable change
```

**Self-check**
- [ ] Data classes use `@dataclass(frozen=True)` unless mutation is required
- [ ] No shared mutable object passed around and edited in multiple places

---

## 14 — Keep the Package Layout Standard

**Rule:** Use the `src/` layout with `pyproject.toml` — otherwise imports, packaging, and
tests behave differently on every machine that runs the project.

**Bad**
```
myproject/
  myproject.py
  helpers.py
  setup.py
```

**Good**
```
myproject/
  pyproject.toml
  src/
    myproject/
      __init__.py
      core.py
  tests/
    test_core.py
```

**Self-check**
- [ ] Project has `pyproject.toml`, not a bare `setup.py`
- [ ] Source lives under `src/<package_name>/`, tests live under `tests/`
