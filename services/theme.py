"""Per-visitor light/dark switch.

Streamlit has no supported per-user theme API (the community workaround changes the theme for
*everyone*). Instead the page is flipped visually for this session only: the whole document is
colour-inverted with the hue rotated back, and elements with deliberate colours (hero banner,
icon badges, primary buttons, images) are inverted a second time to restore them.
The switch is applied only when the wanted mode differs from the device/Streamlit theme.
"""

INVERT = "invert(1) hue-rotate(180deg)"

INVERT_CSS = f"""<style>
html {{ filter: {INVERT}; }}
img, video, picture, [data-testid="stImage"], [data-testid="stLogo"], [data-testid="stIconEmoji"],
.lg-hero, .lg-brand .mark, .lg-kpi .badge, .lg-step .n,
button[data-testid="stBaseButton-primary"], button[kind="primary"] {{ filter: {INVERT}; }}
</style>"""


def invert_needed(native_theme: str, want_dark: bool) -> bool:
    """True when the page must be flipped to show the wanted mode on top of ``native_theme``."""
    return want_dark != (native_theme == "dark")
