from services.theme import INVERT_CSS, invert_needed


def test_flip_only_when_wanted_mode_differs_from_native():
    assert invert_needed("light", want_dark=True) is True      # light device, user wants dark
    assert invert_needed("light", want_dark=False) is False
    assert invert_needed("dark", want_dark=False) is True      # dark device, user wants light
    assert invert_needed("dark", want_dark=True) is False


def test_css_flips_page_and_restores_deliberate_colours():
    assert "html { filter: invert(1) hue-rotate(180deg); }" in INVERT_CSS
    for selector in (".lg-hero", ".lg-kpi .badge", "img", 'button[data-testid="stBaseButton-primary"]'):
        assert selector in INVERT_CSS
