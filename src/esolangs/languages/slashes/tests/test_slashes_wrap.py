from esolangs.generation.wrap import wrap_program


def test_unwrappable_source_is_untouched() -> None:
    assert wrap_program("iiiioddo", "slashes", 4) == "iiiioddo"
