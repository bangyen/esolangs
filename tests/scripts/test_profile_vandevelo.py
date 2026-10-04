"""Profiling observes the exact fallback and checks simultaneous renaming."""

import sys

import pytest

from scripts.profile_vandevelo import (
    execute,
    frequency_names,
    measure,
    positive_control,
)


def test_exact_fallback_positive_control_restores_profiler() -> None:
    prior = sys.getprofile()
    work = positive_control()
    assert work.fallback_calls == 1
    assert sys.getprofile() is prior


@pytest.mark.medium
def test_frequency_rule_preserves_a_short_name_collision() -> None:
    source = (
        "aa ~> Inp?\nb ~> Inp?\nloop -> loop?\naa? :: aa? :: aa? :: loop?\nb? :: loop?"
    )
    renamed = frequency_names(source)
    assert len(renamed) < len(source)
    assert execute(source, "0111") == 4
    assert execute(renamed, "0111") == 4


@pytest.mark.medium
def test_profiled_generator_and_rule_execute_every_row() -> None:
    source, costs = measure("0101111000110101")
    assert costs["identifier_characters"] <= costs["characters"]
    assert execute(source, "0101111000110101") == 16
    assert execute(frequency_names(source), "0101111000110101") == 16
