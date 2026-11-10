"""Independent explicit first-choice/stdlib seed policies, never native outcomes."""

from random import Random

from . import full_oracle as model


class DrawPlan:
    """Fresh independent RNG, complete expected events and state checkpoints."""

    def __init__(self, profile):
        assert profile in ("first0seed0", "seed0")
        self.profile = profile
        self.first = 0 if profile == "first0seed0" else None
        self.random = Random(0)
        self.events = []
        self.states = [(self.first, self.random.getstate())]

    def __call__(self, upper):
        assert type(upper) is int
        assert upper > 0
        if self.first is None:
            value = self.random.randrange(upper)
        else:
            value = self.first % upper
            self.first = None
        self.events.append((upper, value))
        self.states.append((self.first, self.random.getstate()))
        return value


def profile_for(route):
    assert route in (
        "raw",
        "prepare",
        "vm",
        "debug",
        "bounded",
        "ordinary",
        "workers",
        "public-bounded",
        "public-ordinary",
    )
    return "first0seed0" if route in ("raw", "prepare") else "seed0"


def predict(case, profile):
    plan = DrawPlan(profile)
    grid, rows = model.predict(case, choose=plan)
    assert tuple(plan.events) == rows[-1].draws
    for row in rows:
        assert row.draws == tuple(plan.events[: len(row.draws)])
    return grid, rows, plan
