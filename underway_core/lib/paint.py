"""AI paintings of vessels through fal.ai: each ship painted once, from its
own photograph where Wikimedia Commons has one or from its particulars
alone where it has none, in a style, on white paper (cut out on the page)
or as a whole picture on a painted sea. The prompts, the styles and the
cut-out are here; the budget, the queue, the files and the admin page are
Tesserae's (``app.artwork``, 0.463 and later). Loaded by path."""

from __future__ import annotations

import hashlib
import importlib.util
import io
import re
import sys
from pathlib import Path
from typing import Any

_HERE = Path(__file__).resolve().parent


def _sibling(name: str) -> Any:
    full = f"_tesserae_plugins.underway_core.{name}"
    if full in sys.modules:
        return sys.modules[full]
    spec = importlib.util.spec_from_file_location(full, _HERE / f"{name}.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[full] = mod
    spec.loader.exec_module(mod)
    return mod


N = _sibling("net")

try:
    from app import artwork  # Tesserae 0.463+: the pictures a widget makes and keeps
    from app import fal as _fal
except (
    ImportError
):  # an older Tesserae: the widgets still draw, from photographs, and say why
    artwork = None  # type: ignore[assignment]
    _fal = None  # type: ignore[assignment]

NEEDS_HOST = "AI paintings need Tesserae 0.463 or later; this server is older, so the photographs show."


class _NoArt:
    """What ART.open() hands a fetch on a Tesserae without app.artwork: every
    request answers no_host, nothing is started, the note says why."""

    key = ""
    preview = False
    settled = True
    subject = ""
    cell = ""
    cap = 0
    started = 0
    pending = 0
    busy = False
    c = None

    def __init__(self) -> None:
        self.states: dict[str, int] = {}
        self.asked: dict[str, Any] = {}
        self.data_dir = Path(".")

    def request(
        self, key: str, payload: dict[str, Any], *, title: str = "", want: bool = True
    ) -> Any:
        from types import SimpleNamespace

        self.states["no_host"] = self.states.get("no_host", 0) + 1
        return SimpleNamespace(
            key=key,
            state="no_host",
            ready=False,
            path=None,
            meta={},
            why=NEEDS_HOST,
            credit="",
        )

    def url(self, *a: Any, **k: Any) -> str:
        return ""

    def picture(self, *a: Any, **k: Any) -> None:
        return None

    def live(self) -> dict[str, int]:
        return {"live_refresh_s": 0, "live_pending": 0}

    def notes(self) -> list[str]:
        return [NEEDS_HOST] if self.states.get("no_host") else []

    def status(self) -> list[str]:
        return []

    def finish(self, *a: Any, **k: Any) -> None:
        return None


class _NoArtwork:
    """The collection on an older Tesserae: it opens to _NoArt and answers
    nothing to everything else (the paintings page does not exist there)."""

    name = "paintings"
    href = "/plugins/underway_core/"
    actions: list[Any] = []
    extra_template = None
    extra_context = None
    _DEFAULTS: dict[str, Any] = {
        "state": "none",
        "why_failed": "",
        "held": {},
        "dashboards": [],
        "listing": [],
        "errors": [],
        "versions": [],
        "budget_used": 0,
        "cap": 0,
        "adopt": False,
        "progress": {
            "running": [],
            "queued": [],
            "finished": [],
            "used": 0,
            "cap": 0,
            "used_text": "",
            "cap_text": "",
            "held": 0,
        },
    }

    def open(
        self,
        ctx: dict[str, Any],
        settings: dict[str, Any] | None,
        *,
        subject: str = "",
        cell: str = "",
    ) -> _NoArt:
        return _NoArt()

    def folder(self, data_dir: Path) -> Path:
        return Path(data_dir) / self.name

    def __getattr__(self, name: str) -> Any:
        default = self._DEFAULTS.get(name)
        return lambda *a, **k: default


MODELS: dict[str, dict[str, str]] = {
    "nano_banana": {
        "label": "Nano Banana",
        "endpoint": "fal-ai/nano-banana/edit",
        "cost": "about US$0.04",
        "cents": 4,
    },
    "nano_banana_pro": {
        "label": "Nano Banana Pro",
        "endpoint": "fal-ai/nano-banana-pro/edit",
        "cost": "about US$0.15",
        "cents": 15,
    },
    "flux_kontext": {
        "label": "FLUX.1 Kontext Pro",
        "endpoint": "fal-ai/flux-pro/kontext",
        "cost": "about US$0.04",
        "cents": 4,
    },
    "gpt_image": {
        "label": "GPT Image 2",
        "endpoint": "openai/gpt-image-2/edit",
        "cost": "about US$0.05",
        "cents": 5,
    },
    "seedream": {
        "label": "Seedream 4",
        "endpoint": "fal-ai/bytedance/seedream/v4/edit",
        "cost": "about US$0.03",
        "cents": 3,
    },
}
DEFAULT_MODEL = "nano_banana"
TYPICAL_CENTS = 4
UNLIMITED = artwork.UNLIMITED if artwork is not None else 10**9
PROMPT_VERSION = 1
CUT_VERSION = 1
NOTE_NO_KEY = "AI pictures need a fal.ai key: this widget's own, or the app's under Settings › Generative AI."

# ----------------------------------------------------------------------
# Styles: an id, a label and how the picture is made. {kind} is "vessel".
# ----------------------------------------------------------------------
STYLES: dict[str, tuple[str, str]] = {
    "poster": (
        "Vintage shipping-line poster",
        "a vintage shipping-line poster illustration in gouache, in the manner of the great ocean-liner posters: flat confident shapes, a limited palette of deep blues and warm tones, crisp edges with a little paper texture, the vessel rendered with affection and accuracy",
    ),
    "engraving_colour": (
        "Hand-coloured engraving",
        "a hand-coloured copperplate engraving from a nineteenth-century maritime atlas: fine engraved linework and stippling under delicate watercolour washes, the hull's colours kept true",
    ),
    "engraving": (
        "Black-ink engraving",
        "a black-ink copperplate engraving from a Victorian encyclopaedia of ships: fine cross-hatching and stippling, no colour at all",
    ),
    "technical": (
        "Shipyard profile drawing",
        "a precise technical ink illustration from a shipyard's general-arrangement drawing: clean ruled linework, light hatching for shadow, the deckhouses, masts and hull plating drawn, no colour",
    ),
    "watercolour": (
        "Loose watercolour",
        "a loose, airy marine watercolour with soft wet edges, a few precise details on the bow and the bridge and plenty of white space",
    ),
    "woodblock": (
        "Japanese woodblock print",
        "a Japanese woodblock print in the manner of the great wave prints: flat areas of colour with a fine dark keyline and the texture of washi paper",
    ),
    "linocut": (
        "Linocut",
        "a bold linocut print in black ink with one muted colour: strong carved lines, simple shapes, a little texture from the block",
    ),
    "deco": (
        "Art Deco liner poster",
        "an Art Deco ocean-liner poster of the 1930s: streamlined geometric shapes, the bow towering, a palette of cream, teal and vermilion, airbrushed gradients",
    ),
    "midcentury": (
        "Mid-century flat illustration",
        "a mid-century modern illustration in the manner of a 1960s cruise brochure: the vessel reduced to clean geometric shapes, flat colour in a handful of tones, no outlines",
    ),
    "pencil": (
        "Pencil study",
        "a careful graphite pencil study: soft shading, the hull's sheen suggested with a few highlights, no colour",
    ),
    "pointillism": (
        "Pointillism",
        "a pointillist painting built from thousands of small dots of pure colour, the vessel's form emerging from the dots",
    ),
    "blueprint": (
        "Blueprint",
        "a cyanotype blueprint: fine white linework on deep Prussian blue paper, waterline, frames and dimension ticks",
    ),
    "cutaway": (
        "Magazine cutaway",
        "a 1950s magazine cutaway illustration: the hull opened to show the bridge, the holds, the engine room and the cabins in neat sections, tiny figures on deck, painted in gouache with a draughtsman's precision",
    ),
    "stamp": (
        "Postage stamp",
        "a finely engraved postage stamp: the vessel in the stamp's engraved linework within an ornate perforated border, the country and value lettered in the stamp's own style, the whole stamp filling the picture",
    ),
    "tattoo": (
        "Sailor's tattoo flash",
        "an old-school sailor's tattoo flash sheet drawing: bold black outlines, a flat limited palette of red, yellow and green, simple shading, a ribbon banner curling beneath, an anchor or a swallow at the corner",
    ),
    "riso": (
        "Risograph",
        "a two-colour risograph print in fluorescent pink and blue ink only: the vessel reduced to two overprinted flat ink layers with grainy texture, slight misregistration and coarse halftone shading, no photographic detail at all",
    ),
    "pixel": (
        "Pixel art",
        "coarse pixel art as from a 16-bit video game: the vessel drawn at a tiny resolution of about 96 pixels across and scaled up so every square pixel is plainly visible, a palette of sixteen colours, stair-stepped edges, dithered shading, nothing smooth",
    ),
    "lowpoly": (
        "Low-poly render",
        "a low-polygon 3D render: the vessel built from a few hundred large flat-shaded triangles so that every facet shows as a visible flat plane with a hard edge, no smooth surfaces, soft studio lighting",
    ),
    "papercraft": (
        "Paper craft",
        "a paper model of the vessel made from cut and folded card, photographed on a table: visible folds, glued tabs and the cut edges of the card, lit from the side",
    ),
    "toybrick": (
        "Toy bricks",
        "a model of the vessel built from interlocking plastic toy bricks, rendered as a product photograph: rows of round studs along the decks, every curve stepped into blocky brick shapes, glossy moulded plastic, the hull in brick colours",
    ),
    "bottle": (
        "Ship in a bottle",
        "a model of the vessel built inside a glass bottle lying on its side, photographed on a wooden shelf: the glass catching the light, a painted plaster sea inside, the cork and the neck of the bottle in the picture",
    ),
    "charcoal": (
        "Charcoal",
        "a drawing in charcoal sticks on rough toothy paper: visibly smudged by hand, strokes and finger-rubbed shading plain to see, a few sharp lines on the bow and the bridge, nothing photographic, no colour",
    ),
    "stained_glass": (
        "Stained glass",
        "a stained-glass window design: the vessel made of flat panes of coloured glass separated by thick black lead lines, the light coming through the glass",
    ),
    "gilt": (
        "Illuminated manuscript",
        "an illuminated manuscript miniature: the vessel painted in tempera with gold leaf on the superstructure and the bow, a fine red and blue filigree border",
    ),
    "scrimshaw": (
        "Scrimshaw",
        "a scrimshaw engraving on whale ivory: fine scratched linework filled with black ink on a creamy, slightly yellowed ivory ground, in the manner of a nineteenth-century sailor's carving",
    ),
    "pulp": (
        "Pulp cover",
        "a 1950s pulp adventure magazine cover painting: airbrushed, dramatic, saturated, the vessel heroic against a lurid sky and a heaving sea",
    ),
    "synthwave": (
        "Synthwave",
        "a synthwave illustration: neon pink and cyan on a dark purple ground, a glowing grid horizon and a striped sun, the vessel in chrome on a mirror sea",
    ),
    "chalk": (
        "Chalkboard",
        "a chalk drawing on a dark blackboard: white and coloured chalk, soft smudges, the lines a little dusty",
    ),
}
STYLE_IDS = (*STYLES, "builder", "custom")
# Styles without colour: the prompt asks for black, white and grey only
MONO = {"engraving", "technical", "pencil", "charcoal", "scrimshaw"}
# Styles that make a whole picture on their own ground, never cut out
OWN_PAPER = {
    "blueprint",
    "stamp",
    "synthwave",
    "chalk",
    "gilt",
    "pulp",
    "bottle",
    "scrimshaw",
}
CUSTOM_EXAMPLE = "a chalk pastel drawing on grey paper, soft and smudgy, with the sun catching the bridge windows"
CUSTOM_PRESETS = [
    {
        "label": "Gouache poster",
        "value": "a vintage shipping-line poster in gouache: flat confident shapes, a palette of deep blues and warm tones, crisp edges",
    },
    {
        "label": "Cutaway",
        "value": "a 1950s magazine cutaway illustration: the hull opened to show the bridge, the holds and the engine room, labelled in small neat capitals",
    },
    {"label": "Chalk pastel", "value": CUSTOM_EXAMPLE},
    {
        "label": "Marine oil",
        "value": "a traditional marine oil painting in the manner of the great ship portraitists: dramatic light, a heaving sea, confident brushwork",
    },
    {
        "label": "Comic ink",
        "value": "a comic-book ink drawing with bold outlines, hatched shadows and flat halftone colour",
    },
    {
        "label": "Neon line",
        "value": "a single-weight neon line drawing on white: one continuous glowing line describing the vessel",
    },
]
_CUSTOM_RE = re.compile(r"custom[a-z]{8}")

BUILDER: dict[str, tuple[str, str, tuple[tuple[str, str, str], ...]]] = {
    "medium": (
        "Medium",
        "gouache",
        (
            ("gouache", "Gouache", "a flat gouache painting"),
            ("watercolour", "Watercolour", "a loose watercolour painting"),
            ("oil", "Oil paint", "an oil painting with visible brushwork"),
            ("pastel", "Soft pastel", "a soft pastel drawing"),
            ("coloured_pencil", "Coloured pencil", "a coloured-pencil drawing"),
            ("pencil", "Graphite pencil", "a graphite pencil drawing"),
            ("ink", "Pen and ink", "a pen-and-ink drawing"),
            ("engraving", "Engraving", "a copperplate engraving"),
            ("lithograph", "Lithograph", "a hand-coloured lithograph"),
            ("woodblock", "Woodblock", "a woodblock print"),
            ("linocut", "Linocut", "a linocut print"),
            ("screenprint", "Screen print", "a screen print with a few flat inks"),
            ("vector", "Flat vector", "a flat vector illustration"),
            ("airbrush", "Airbrush", "an airbrushed illustration"),
            ("papercut", "Paper cut", "layered cut paper"),
        ),
    ),
    "period": (
        "Period or school",
        "",
        (
            ("", "None in particular", ""),
            (
                "1900s",
                "Ocean-liner poster",
                "in the manner of a 1900s ocean-liner poster",
            ),
            ("1930s", "1930s travel poster", "in the manner of a 1930s travel poster"),
            (
                "1950s",
                "1950s cruise brochure",
                "in the manner of a 1950s cruise brochure",
            ),
            (
                "victorian",
                "Victorian technical plate",
                "in the manner of a Victorian technical plate",
            ),
            (
                "dutch",
                "Dutch Golden Age marine",
                "in the manner of a Dutch Golden Age marine painting",
            ),
            ("ukiyoe", "Ukiyo-e", "in the manner of a Japanese ukiyo-e print"),
            ("deco", "Art Deco", "in the Art Deco manner"),
            ("bauhaus", "Bauhaus", "in the Bauhaus manner"),
            ("retrofuture", "Retro-futurism", "in a retro-futurist manner"),
        ),
    ),
    "palette": (
        "Palette",
        "",
        (
            ("", "As the hull is", ""),
            ("limited", "A few warm tones", "in a limited palette of a few warm tones"),
            ("muted", "Muted", "in muted, dusty colours"),
            ("vivid", "Vivid", "in vivid saturated colour"),
            ("duotone", "Two inks", "in two inks only"),
            ("mono", "Black and white", "in black and white only"),
            ("sepia", "Sepia", "in sepia tones"),
        ),
    ),
    "line": (
        "Line",
        "",
        (
            ("", "As the medium has it", ""),
            ("fine", "Fine", "with fine delicate line"),
            ("bold", "Bold", "with bold confident outlines"),
            ("none", "No outlines", "with no outlines, shapes meeting edge to edge"),
            ("sketchy", "Sketchy", "with loose sketchy line"),
        ),
    ),
    "texture": (
        "Texture",
        "",
        (
            ("", "As the medium has it", ""),
            ("paper", "Paper grain", "with visible paper grain"),
            (
                "print",
                "Print texture",
                "with the texture of a print, slightly misregistered",
            ),
            ("smooth", "Smooth", "smooth and clean"),
            ("halftone", "Halftone", "with halftone dots in the shading"),
        ),
    ),
    "mood": (
        "Mood",
        "",
        (
            ("", "Plain", ""),
            ("heroic", "Heroic", "heroic and dramatic, the bow lifting on a swell"),
            ("calm", "Calm", "calm and serene on a flat sea"),
            ("nostalgic", "Nostalgic", "warm and nostalgic"),
            ("technical", "Precise", "precise and matter-of-fact"),
        ),
    ),
}


def build_how(options: dict[str, Any]) -> str:
    """The style builder's picks as one style description."""
    parts: list[str] = []
    for name, (_label, default, choices) in BUILDER.items():
        pick = str(options.get(f"build_{name}") or default)
        phrase = next((p for v, _l, p in choices if v == pick), "")
        if name == "medium":
            phrase = (phrase or choices[0][2]) + " of the {kind}"
        if phrase:
            parts.append(phrase)
    extra = " ".join(str(options.get("build_extra") or "").split())[:300]
    if extra:
        parts.append(extra)
    return ", ".join(parts)


# ----------------------------------------------------------------------
# Backdrops: none keeps the vessel alone on white paper for the cut-out;
# the rest make a whole picture that fills its frame.
# ----------------------------------------------------------------------
BACKDROPS: dict[str, tuple[str, str]] = {
    "none": ("None: the vessel alone, cut out on the page", ""),
    "sea": (
        "The open sea",
        "the open sea under a clear sky in the same style, the water to the horizon, the light of the time of day",
    ),
    "harbour": (
        "In harbour",
        "a working harbour in the same style, wharves and cranes behind and the still water of the basin in front",
    ),
    "coast": (
        "Along the coast",
        "a coastline in the same style, headlands and a lighthouse in the distance, a light swell",
    ),
    "sunset": (
        "Sunset",
        "a sunset over the sea in the same style, the vessel lit warmly from the side and the sky's colour on the water",
    ),
    "night": (
        "Night",
        "a night sea in the same style, the vessel's navigation lights and deck lights on and their reflections on the water",
    ),
    "storm": (
        "Heavy weather",
        "a storm at sea in the same style, grey swell, spray breaking over the bow and a shaft of light on the vessel",
    ),
    "ornate": (
        "Ornate framed plate",
        "a decorative backdrop in the same style, a patterned or foliate ground within a drawn ornamental border that fills the whole picture to its edges, the page's own art in that style and nothing modern",
    ),
    "live": ("The sea as it is now: time of day and weather", ""),
}

GEN = (
    "Draw the {typ} in the reference photo, the {name}{flag}, afresh as {style}: a new illustration of this very "
    "ship in that style, not the photo restyled. The reference photo is for identity only: its exact hull colours, "
    "funnel markings, superstructure, deck cargo, name and port of registry on the hull, shape and proportions are "
    "kept. The vessel under way, {view}{scene}. The name on the bow and the markings on the funnel are reproduced "
    "exactly as in the photograph. {page} No text or lettering beyond the ship's own, no border, no signature.{outline}"
)
GEN_FAITHFUL = (
    "Render the {typ} in the reference photo, the {name}{flag}, as {style}: a faithful translation of this very "
    "photograph into that medium. The photograph is the authority: the same ship at the same angle and attitude as "
    "photographed; every element of her as she actually appears in the photograph, her hull colours, the funnel "
    "markings, the name and port of registry on the hull, the deck cargo, cranes, masts and superstructure, "
    "reproduced exactly as they are in the photograph; only the medium changes{scene}. Where the photograph is too "
    "small to read a mark, draw the line's actual mark rather than a guess. {page} No text or lettering beyond "
    "the ship's own, no border, no signature.{outline}"
)
GEN_WORDS = (
    "Draw {about}, the {name}{flag}{size}, as {style}: a plausible, specific, well-observed {typ} of that kind "
    "and size, her hull and superstructure of the usual form for her trade, {view}{scene}. {page} No text or "
    "lettering beyond her name on the bow, no border, no signature.{outline}"
)
FIDELITIES = ("photo", "free")
PAGE_ALONE = (
    "The vessel alone on plain, pure white paper with a clear margin all round and nothing else on the page: no "
    "sea, sky, horizon, wake, waves, wharf, shadow or ornament round or behind her; the hull drawn down to the "
    "waterline and no further. The style says how the vessel is drawn and nothing else."
)
PAGE_WHOLE = "The picture complete, filling the frame edge to edge."
OUTLINE = (
    " The whole vessel is drawn with a fine, clear, unbroken dark contour line along her entire outline, hull, "
    "superstructure, masts and cargo, so that a white or pale part is never lost against the white paper."
)
VIEWS = {
    "side": "seen from the side and a little above, a full broadside view",
    "profile": "seen exactly from the side at water level, a pure profile view as in a shipyard's drawing, the whole vessel level and centred",
    "quarter": "seen from the bow quarter, a little above, the bow nearest",
    "stern": "seen from the stern quarter, her wake trailing",
}
MONO_WORDS = (
    "its exact hull colours, funnel markings, superstructure, deck cargo, name and port of registry on the hull, shape and proportions are kept",
    "its exact funnel markings, superstructure, deck cargo, name and port of registry on the hull, shape and proportions are kept, rendered without any colour: black, white and grey only",
)

# The visitors: id -> (name for the caption, how the painter is told it, pool). A famous
# vessel is described by her look alone, never named to the painter.
MONSTERS: dict[str, tuple[str, str, str]] = {
    "kraken": (
        "Kraken",
        "a colossal kraken, a giant squid of impossible size, its great mantle and eye breaking the surface and its tentacles rearing from the water",
        "myth",
    ),
    "serpent": (
        "Sea serpent",
        "a sea serpent of the old charts, a long scaled body arching out of the water in loops, a horse-like head with a mane of spray",
        "myth",
    ),
    "nessie": (
        "Loch monster",
        "a plesiosaur-like lake monster, a long neck and a small head rising from the water above a dark humped back",
        "myth",
    ),
    "leviathan": (
        "Leviathan",
        "a leviathan, a whale-like creature far larger than any whale, armoured in ridged plates, its back rising from the deep like an island",
        "myth",
    ),
    "mermaid": (
        "Mermaid",
        "a mermaid on a rock at the water's edge, a woman to the waist and a scaled fish's tail below, combing her hair",
        "myth",
    ),
    "dutchman": (
        "Ghost ship",
        "a ghost ship, a spectral three-masted sailing ship of the seventeenth century with tattered glowing sails, barnacled and weed-hung, half seen through sea mist",
        "story",
    ),
    "nautilus": (
        "Iron submarine",
        "a Victorian iron submarine of fiction, a long riveted spindle of a hull with a raised wheelhouse, a great glass salon window in the side and a serrated ram at the bow",
        "story",
    ),
    "pearl": (
        "Black pirate ship",
        "a black-hulled pirate galleon with black tattered sails and a skull flag, cannon run out, cutting through the water",
        "story",
    ),
    "whale": (
        "White whale",
        "an immense white sperm whale, scarred and barnacled, broaching the surface with a harpoon line trailing from its flank",
        "story",
    ),
    "submarine": (
        "Yellow submarine",
        "a cheerful bright yellow cartoon submarine with round portholes and a periscope, bobbing on the surface",
        "story",
    ),
    "ark": (
        "The ark",
        "an enormous wooden ark of biblical proportions, a vast pitch-sealed hull with a long roofed house upon it and animals looking out of the windows",
        "story",
    ),
    "raft": (
        "Balsa raft",
        "a balsa-log raft with a square sail bearing a bearded sun face, a small cabin of split bamboo and a steering oar, crossing the open ocean",
        "real",
    ),
    "clipper": (
        "Tea clipper",
        "a nineteenth-century tea clipper under full sail, a long slim black hull with a gilded line, three masts crowded with canvas",
        "real",
    ),
    "victory": (
        "Ship of the line",
        "an eighteenth-century ship of the line, a three-decker with a black and yellow chequered hull, three masts and gun ports open",
        "real",
    ),
    "liner": (
        "Four-funnelled liner",
        "an Edwardian ocean liner with four tall buff funnels with black tops, a long black hull with a white superstructure, steaming at speed",
        "real",
    ),
    "endurance": (
        "Polar barquentine",
        "a wooden polar expedition barquentine beset in pack ice, her masts and rigging rimed with frost, ice pressing against her hull",
        "real",
    ),
    "longship": (
        "Viking longship",
        "a Viking longship with a carved dragon prow, a single square striped sail and a row of round shields along the gunwale",
        "real",
    ),
    "trireme": (
        "Trireme",
        "an ancient Greek trireme with three banks of oars, a bronze ram at the bow and painted eyes on the prow",
        "real",
    ),
    "junk": (
        "Chinese junk",
        "a Chinese junk with high stern, battened fan-shaped sails and a hull painted red and black",
        "real",
    ),
    "galleon": (
        "Spanish galleon",
        "a sixteenth-century Spanish galleon with a high ornate stern castle, red and gold paint and square sails bearing a cross",
        "real",
    ),
}
MONSTER_POOLS = ("myth", "story", "real", "all")
POOL_LABELS = {"myth": "Myth", "story": "Story", "real": "Real"}
GEN_MONSTER = (
    "Draw {what} as {style}, seen from the side and a little above, on the water.{alien} {page} No text or "
    "lettering, no border, no signature.{outline}"
)
UNEARTHLY = " It is a creature of legend, not an animal that exists: its size is impossible, its eye ancient, and the sea round it churns."


def monster_choices(pool: str) -> list[str]:
    return [k for k, v in MONSTERS.items() if pool == "all" or v[2] == pool] or [
        k for k, v in MONSTERS.items() if v[2] == "myth"
    ]


def visitors_of(chosen: Any) -> list[str]:
    """The visitors ticked, or the myths when none of the ticks is one."""
    got = (
        [str(c) for c in chosen if str(c) in MONSTERS]
        if isinstance(chosen, list)
        else []
    )
    return got or monster_choices("myth")


def style_of(style: str | None) -> tuple[str, str]:
    if style in STYLES:
        return STYLES[style]
    if style and _CUSTOM_RE.fullmatch(style):
        return ("Your own style", _CUSTOM.get(style, ""))
    return STYLES["poster"]


def custom_tag(how: str) -> str:
    digest = hashlib.sha1(" ".join(how.split()).lower().encode()).hexdigest()
    return "custom" + "".join(
        "abcdefghijklmnopqrstuvwxyz"[int(c, 16) % 26] for c in digest[:8]
    )


_CUSTOM: dict[str, str] = {}


def register_custom(how: str) -> str:
    tag = custom_tag(how)
    _CUSTOM[tag] = how
    return tag


def monster_key(shape: str, style: str) -> str:
    return f"visitor_{N.slug(shape)}--{style}--p{PROMPT_VERSION}"


def key_for(
    who: str,
    style: str,
    backdrop: str = "none",
    view: str = "side",
    model: str = DEFAULT_MODEL,
    sea: str = "",
    fidelity: str = "photo",
    photo: bool = True,
) -> str:
    parts = [N.slug(who), style, f"p{PROMPT_VERSION}"]
    if not photo:
        parts.append("words")
    elif fidelity == "free":
        parts.append("free")
    else:
        view = "side"  # as photographed: the view is the photograph's
    if backdrop == "live":
        parts.append(f"bd_{N.slug(sea or 'midday_clear')[:24]}")
    elif backdrop != "none":
        parts.append(f"bd_{backdrop}")
    if view != "side" and (not photo or fidelity == "free"):
        parts.append(f"v_{view}")
    if model != DEFAULT_MODEL:
        parts.append(f"m_{model}")
    return "--".join(parts)


def _scene(job: dict[str, Any]) -> str:
    backdrop = str(job.get("backdrop") or "none")
    if backdrop == "live":
        return f", across {job.get('sea_words') or 'the open sea in the same style'}"
    if backdrop == "ornate":
        return (
            ", as the single subject of an ornate framed plate: the vessel large in the middle on "
            + BACKDROPS["ornate"][1]
        )
    if backdrop in BACKDROPS and backdrop != "none":
        return f", across {BACKDROPS[backdrop][1]}"
    return ""


def prompt_for(job: dict[str, Any]) -> str:
    _label, how = style_of(job.get("style"))
    how = str(job.get("how") or how).replace("{kind}", "vessel")
    style = str(job.get("style") or "")
    alone = str(job.get("backdrop") or "none") == "none" and style not in OWN_PAPER
    if job.get("monster"):
        what = MONSTERS.get(str(job["monster"]), MONSTERS["kraken"])
        text = GEN_MONSTER.format(
            what=what[1],
            style=how,
            alien=UNEARTHLY if what[2] == "myth" else "",
            page=PAGE_ALONE.replace("The vessel", "The subject")
            .replace("the vessel", "the subject")
            .replace("her", "its")
            .replace(
                "the hull drawn down to the waterline and no further",
                "drawn down to the waterline and no further",
            )
            if alone
            else PAGE_WHOLE,
            outline=OUTLINE.replace("vessel", "subject").replace(
                "her entire outline, hull, superstructure, masts and cargo",
                "its entire outline",
            )
            if alone
            else "",
        )
        if style in MONO:
            text += " Rendered without any colour: black, white and grey only."
        return text
    scene = _scene(job)
    flag = f" under the flag of {job['flag']}" if job.get("flag") else ""
    name = str(job.get("name") or "").strip() or "unnamed"
    if not job.get("photo"):
        length = job.get("len") or 0
        size = f", about {int(length)} metres long" if length else ""
        text = GEN_WORDS.format(
            about=job.get("about") or "a vessel",
            style=how,
            typ=str(job.get("typ") or "vessel").lower(),
            name=name,
            flag=flag,
            size=size,
            view=VIEWS.get(str(job.get("view") or "side"), VIEWS["side"]),
            scene=scene,
            page=PAGE_ALONE if alone else PAGE_WHOLE,
            outline=OUTLINE if alone else "",
        )
        if style in MONO:
            text += " Rendered without any colour: black, white and grey only."
        return text
    if str(job.get("fidelity") or "photo") != "free":
        text = GEN_FAITHFUL.format(
            typ=job.get("typ") or "vessel",
            name=name,
            flag=flag,
            style=how,
            scene=scene.replace(", across ", ", set across ")
            if scene and str(job.get("backdrop")) != "ornate"
            else scene,
            page=PAGE_ALONE if alone else PAGE_WHOLE,
            outline=OUTLINE if alone else "",
        )
        if style in MONO:
            text = text.replace(
                "her hull colours, the funnel markings", "the funnel markings"
            ).replace(
                "only the medium changes",
                "only the medium changes, rendered without any colour: black, white and grey only",
            )
        return text
    text = GEN.format(
        typ=job.get("typ") or "vessel",
        name=name,
        flag=flag,
        style=how,
        view=VIEWS.get(str(job.get("view") or "side"), VIEWS["side"]),
        scene=scene,
        page=PAGE_ALONE if alone else PAGE_WHOLE,
        outline=OUTLINE if alone else "",
    )
    if style in MONO:
        text = text.replace(*MONO_WORDS)
    return text


def model_of(model: str | None) -> str:
    return model if model in MODELS else DEFAULT_MODEL


# ----------------------------------------------------------------------
# Files, budget, state
# ----------------------------------------------------------------------
ART: Any = (
    artwork.Collection(
        "underway_core",
        "paintings",
        make=lambda job: make(job),
        label="Underway",
        title="Painting vessels",
        facet="style",
        facet_label=lambda s: style_of(s)[0],
    )
    if artwork is not None
    else _NoArtwork()
)


def gen_dir(data_dir: Path) -> Path:
    """The paintings' folder, the collection's, for the tools and the tests."""
    return ART.folder(Path(data_dir))


def dollars(cents: int) -> str:
    return "no limit" if cents >= UNLIMITED else f"US${cents / 100:.2f}"


def cost_cents(model: str) -> int:
    return int(MODELS.get(model, MODELS[DEFAULT_MODEL]).get("cents") or TYPICAL_CENTS)


# ----------------------------------------------------------------------
# The cut-out: a painting on white paper becomes a PNG with alpha, the
# paper's colour read from the corners and the noise of its texture allowed
# for, so a cream or grainy paper cuts as cleanly as a white one.
# ----------------------------------------------------------------------
def cut_out(raw: bytes) -> bytes | None:
    """The painting as a PNG with alpha. The paper is what is paper-coloured
    and reaches the edge of the page; everything else, a white hull inside
    its contour line included, is the vessel and stays."""
    try:
        import numpy as np
        from PIL import Image, ImageFilter
    except ImportError:  # pragma: no cover
        return None
    try:
        im = Image.open(io.BytesIO(raw)).convert("RGB")
    except Exception:  # noqa: BLE001
        return None
    a = np.asarray(im).astype(float)
    H, W = a.shape[:2]
    c = 30
    corners = np.concatenate(
        [
            a[:c, :c].reshape(-1, 3),
            a[:c, -c:].reshape(-1, 3),
            a[-c:, :c].reshape(-1, 3),
            a[-c:, -c:].reshape(-1, 3),
        ]
    )
    paper = np.median(corners, axis=0)
    spread = np.sqrt(((corners - paper) ** 2).sum(-1))
    near = spread[spread < 60]
    noise = float(near.std()) if len(near) > 50 else 0.0
    d = np.sqrt(((a - paper) ** 2).sum(-1))
    thr = max(22.0, 10 + 4 * noise)
    paperlike = d < thr
    s = 2
    small = (
        paperlike[: H // s * s, : W // s * s]
        .reshape(H // s, s, W // s, s)
        .all(axis=(1, 3))
    )
    h, w = small.shape
    keep_small = None
    for inset in (0, 0.03, 0.06, 0.1, 0.15):
        iy, ix = int(h * inset), int(w * inset)
        bg = np.zeros_like(small)
        stack = []
        for x in range(ix, w - ix):
            for y in (iy, h - 1 - iy):
                if small[y, x]:
                    stack.append((y, x))
        for y in range(iy, h - iy):
            for x in (ix, w - 1 - ix):
                if small[y, x]:
                    stack.append((y, x))
        for y, x in stack:
            bg[y, x] = True
        while stack:
            y, x = stack.pop()
            for ny, nx in ((y + 1, x), (y - 1, x), (y, x + 1), (y, x - 1)):
                if 0 <= ny < h and 0 <= nx < w and small[ny, nx] and not bg[ny, nx]:
                    bg[ny, nx] = True
                    stack.append((ny, nx))
        rim = max(1, int(round(min(h, w) * 0.012)))
        for lo in (iy, rim):
            bg[:lo, :] = True
            bg[h - lo :, :] = True
        for lo in (ix, rim):
            bg[:, :lo] = True
            bg[:, w - lo :] = True
        keep_small = ~bg
        if keep_small.mean() < 0.6:
            break
    lab = np.zeros(keep_small.shape, dtype=np.int32)
    sizes: dict[int, int] = {}
    n = 0
    for y0 in range(h):
        for x0 in range(w):
            if keep_small[y0, x0] and not lab[y0, x0]:
                n += 1
                stack = [(y0, x0)]
                lab[y0, x0] = n
                count = 0
                while stack:
                    y, x = stack.pop()
                    count += 1
                    for ny, nx in ((y + 1, x), (y - 1, x), (y, x + 1), (y, x - 1)):
                        if (
                            0 <= ny < h
                            and 0 <= nx < w
                            and keep_small[ny, nx]
                            and not lab[ny, nx]
                        ):
                            lab[ny, nx] = n
                            stack.append((ny, nx))
                sizes[n] = count
    if sizes:
        biggest = max(sizes.values())
        floor = max(40, int(0.004 * h * w), biggest // 40)
        for k, count in sizes.items():
            if count < floor:
                keep_small[lab == k] = False
    keep = np.zeros((H, W), dtype=bool)
    keep[: h * s, : w * s] = np.kron(keep_small, np.ones((s, s), dtype=bool))
    soft = np.clip((d - thr) / 35, 0, 1)
    hard = (
        Image.fromarray((keep * 255).astype("uint8"))
        .filter(ImageFilter.MinFilter(3))
        .filter(ImageFilter.MaxFilter(3))
    )
    hard_a = np.asarray(hard) > 0
    alpha = np.where(hard_a, np.maximum(soft, 0.98), 0.0)
    alpha8 = np.asarray(
        Image.fromarray((alpha * 255).astype("uint8")).filter(
            ImageFilter.GaussianBlur(0.6)
        )
    )
    share = (alpha8 > 40).mean()
    if share < 0.004 or share > 0.9:
        return None
    rgba = np.dstack([a.astype("uint8"), alpha8])
    out = Image.fromarray(rgba.astype("uint8"), "RGBA")
    bbox = Image.fromarray(alpha8).point(lambda p: 255 if p > 40 else 0).getbbox()
    if bbox:
        out = out.crop(bbox)
    buf = io.BytesIO()
    out.save(buf, "PNG", optimize=True)
    return buf.getvalue()


def picture(
    art: Any, key: str, px: int, levels: str, whole_: bool
) -> dict[str, Any] | None:
    """A kept painting for the page: the whole picture as a JPEG data URI, or
    the cut-out as a PNG with alpha, resized for the cell and the panel and
    cached by the collection."""
    c, data_dir = art.c, art.data_dir
    if c is None:
        return None
    path = c.path(key, data_dir)
    if path is None:
        return None
    meta = c.meta(key, data_dir)
    credit = str(meta.get("credit") or "")
    if whole_:
        src = art.url(key, px=px, levels=levels)
        return (
            {
                "src": src,
                "kind": "painting",
                "whole": True,
                "credit": credit,
                "aspect": N.aspect_of(src),
            }
            if src
            else None
        )
    variant = f"cut{CUT_VERSION}"
    cut = c.folder(data_dir) / f"{key}__{variant}.png"
    if not cut.exists():
        try:
            raw = path.read_bytes()
        except OSError:
            return None
        png = cut_out(raw)
        if not png:
            c.note_error(
                key,
                data_dir,
                "the painting could not be cut out",
                title=str(meta.get("title") or key),
            )
            return None
        N.write(cut, png)
    src = art.url(key, px=px, levels=levels, cut=True, variant=variant)
    return (
        {
            "src": src,
            "kind": "painting",
            "whole": False,
            "credit": credit,
            "aspect": N.aspect_of(src),
        }
        if src
        else None
    )


def make(job: Any) -> tuple[bytes, dict[str, Any]]:
    """One painting, on a worker thread: the prompt from the payload, the
    reference photograph handed over inline, the picture from fal.ai through
    the collection's budget. Raises ArtworkError with why not."""
    j = job.payload
    photo = str(j.get("photo") or "")
    model = model_of(j.get("model"))
    prompt = prompt_for(j)
    aspect = str(j.get("aspect") or "4:3")
    if photo and not photo.startswith("data:"):
        # the photograph is fetched here with the widget's own User-Agent and handed over inline
        raw_ref = N.cached_get(job.data_dir, photo, ua=str(j.get("ua") or ""))
        if not raw_ref:
            raise artwork.ArtworkError("the photograph could not be read")
        photo = _fal.data_uri(raw_ref)
    t2i = not photo
    raw = job.fal.generate(
        "nano_banana_t2i" if t2i else model,
        prompt,
        refs=[] if t2i else [photo],
        aspect=aspect,
        retries=1,
    )
    label = MODELS["nano_banana" if t2i else model]["label"]
    credit = (
        f"a visitor painted by {label}"
        if j.get("monster")
        else f"painted by {label} from her particulars"
        if t2i
        else f"painted by {label} from a photograph by {j.get('by') or 'a Commons contributor'} (Wikimedia Commons, {j.get('lic') or 'open licence'})"
    )
    meta = {
        "mmsi": j.get("mmsi"),
        "name": j.get("name"),
        "typ": j.get("typ"),
        "flag": j.get("flag"),
        "style": j.get("style"),
        "how": j.get("how") or "",
        "backdrop": j.get("backdrop") or "none",
        "model": model,
        "credit": credit,
        "monster": j.get("monster") or "",
        "by": j.get("by") or "",
        "link": j.get("link") or "",
        "prompt": prompt,
        "prompt_version": PROMPT_VERSION,
    }
    return raw, meta
