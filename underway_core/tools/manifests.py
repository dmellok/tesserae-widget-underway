"""Write the four widgets' plugin.json and the core's from one description, so
the shared options never drift apart. Run after editing: python tools/manifests.py"""

from __future__ import annotations

# The painter imports Tesserae's ``app.artwork`` (0.463+); outside the server,
# the repo beside this one (or TESSERAE_REPO) is put on the path.
import os as _os
import sys as _sys
from pathlib import Path as _Path

_TESSERAE = _Path(_os.environ.get("TESSERAE_REPO") or _Path(__file__).resolve().parents[3] / "tesserae")
if str(_TESSERAE) not in _sys.path:
    _sys.path.insert(0, str(_TESSERAE))

import importlib.util as _ilu
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
VERSION = "0.1.2"
TESSERAE_MIN = "0.463.0"

_spec = _ilu.spec_from_file_location("_tesserae_plugins.underway_core.paint", ROOT / "underway_core" / "lib" / "paint.py")
_paint = _ilu.module_from_spec(_spec)
sys.modules[_spec.name] = _paint
_spec.loader.exec_module(_paint)
STYLES = [(k, v[0]) for k, v in _paint.STYLES.items()] + [("builder", "Build my own"), ("custom", "Your own prompt")]
BUILDER = {name: (label, default, [(v, lab) for v, lab, _p in choices]) for name, (label, default, choices) in _paint.BUILDER.items()}
PRESETS = _paint.CUSTOM_PRESETS
BACKDROPS = [(k, v[0]) for k, v in _paint.BACKDROPS.items()]
BACKDROPS = [BACKDROPS[0], BACKDROPS[-1], *BACKDROPS[1:-1]]  # none, live, then the rest
MODELS = [(k, f"{v['label']} ({v['cost']})") for k, v in _paint.MODELS.items()]


def sel(name, label, default, choices, **kw):
    return {"name": name, "type": "select", "label": label, "default": default, "choices": [{"value": v, "label": l} for v, l in choices], **kw}


def where_options():
    return [
        sel("source", "Positions from", "aisstream", [("aisstream", "aisstream.io (a free key, in the Underway Core settings)"), ("receiver", "A receiver of your own (AIS-catcher)")], help="aisstream.io streams the world's AIS from a free key; the widget listens for the sea round your place while a page asks. A receiver of your own running AIS-catcher answers at /api/ships.json and hears what it hears."),
        {"name": "receiver_url", "type": "string", "label": "Receiver address", "default": "", "help": "For example http://pi.local:8100; the widget asks for /api/ships.json.", "show_if": {"source": "receiver"}},
        {"name": "location", "type": "location_search", "label": "Place", "default": "", "help": "The point the distances and bearings are from, and the middle of the sea listened to. Falls back to the app's location."},
        sel("radius_km", "Within", "25", [(v, f"{v} km") for v in ("5", "10", "15", "25", "35", "50", "80")]),
        {"name": "include_moored", "type": "boolean", "label": "Include vessels moored or at anchor", "default": True},
        sel("order", "Order", "nearest", [("nearest", "Nearest first"), ("largest", "Largest first"), ("fastest", "Fastest first"), ("moving", "Under way first")]),
    ]


def picture_options(with_backdrop: bool, many: bool, scene: bool = False):
    show = {"pictures": "paintings"}
    out = [
        sel("pictures", "Pictures", "photos", [("photos", "Photographs of the ship (Wikimedia Commons, by IMO number)"), ("paintings", "AI paintings, each from her photograph or her particulars")], help="Photographs cost nothing; a vessel without an IMO number has none. AI paintings paint each ship once, from her photograph where there is one and from her type, size and flag where there is not, in the style below, at about US$0.04 a painting; needs a fal.ai key."),
        sel("style", "Style", "poster", STYLES, show_if=show),
        {"name": "custom_style", "type": "textarea", "label": "Your own prompt", "default": "", "show_if": {"pictures": "paintings", "style": "custom"}, "presets": PRESETS, "help": "The medium and the look; the widget adds the vessel, her photograph and the paper. Pick an example above to start from."},
    ]
    for name, (label, default, choices) in BUILDER.items():
        out.append(sel(f"build_{name}", label, default, choices, show_if={"pictures": "paintings", "style": "builder"}))
    out.append({"name": "build_extra", "type": "string", "label": "Your own words", "default": "", "show_if": {"pictures": "paintings", "style": "builder"}, "help": "Added to the style: for example, with a little gold leaf on the funnel."})
    if with_backdrop:
        out.append(sel("backdrop", "Backdrop", "sea" if scene else "none", BACKDROPS if not scene else BACKDROPS[1:], show_if=show, help="None keeps the vessel alone on the page, cut out. The rest paint a whole picture that fills its frame, in the same style. The sea as it is now takes the time of day and the weather (Open-Meteo) at the place, and paints each condition once per vessel, so a changing sea costs more paintings."))
    out.append(sel("fidelity", "Faithfulness", "photo", [("photo", "As photographed: the same angle, every mark on the hull"), ("free", "Drawn afresh: the model's own composition, the view below")], show_if=show, help="As photographed translates the ship's photograph into the medium and keeps her angle, hull colours, funnel markings and name exactly. Drawn afresh lets the model compose her anew in the style, in the view chosen below. A vessel without a photograph is always drawn afresh, from her particulars."))
    out.append(sel("view", "View", "side", [("side", "Broadside, a little above"), ("profile", "Side-on: a pure profile, as a shipyard drawing"), ("quarter", "From the bow quarter"), ("stern", "From the stern quarter, her wake trailing")], show_if=show))
    out.append(sel("model", "Model", "nano_banana", MODELS, show_if=show, help="All on fal.ai. Nano Banana is faithful and cheap, and keeps the more abstract styles close to the photograph; Nano Banana Pro and FLUX follow those styles further."))
    out.append({"name": "visitor", "type": "slider", "label": "Chance of a visitor", "default": 0, "min": 0, "max": 100, "step": 5, "unit": "%", "show_if": show, "help": "Each hour, this chance that something that should not be on the water joins the page, painted in the page's style, with no AIS and a made-up distance and bearing. For fun. Each visitor in a style is one painting against the daily budget."})
    out.append({"name": "visitors", "type": "multiselect", "label": "Who visits", "default": _paint.monster_choices("myth"), "show_if": {"pictures": "paintings", "visitor": {"not": 0}}, "help": "Tick the visitors the roll may bring: creatures of myth, vessels of story (described to the painter by their look, never named) and real ships of history. With nothing ticked, the creatures of myth.", "choices": [{"value": k, "label": f"{_paint.POOL_LABELS[v[2]]}: {v[0]}"} for k, v in _paint.MONSTERS.items()]})
    if many:
        out.append(sel("unpainted", "Until a vessel is painted", "silhouette", [("silhouette", "Show a silhouette"), ("photo", "Show her photograph"), ("skip", "Only painted vessels: leave the rest off the page")], show_if=show, help="Only painted vessels shows a page of paintings alone; it says so while the first are being painted."))
    else:
        out.append(sel("unpainted", "Until the vessel is painted", "photo", [("photo", "Show her photograph"), ("silhouette", "Show a silhouette"), ("skip", "Only a painted vessel: the nearest one already painted")], show_if=show, help="Only a painted vessel looks among the nearest six for one already painted and keeps painting them, so the page has one most of the time; it says so until the first lands."))
    return out


def page_options(labels_default):
    return [
        {"name": "labels", "type": "multiselect", "label": "Label lines", "default": labels_default, "help": "In this order, under or beside each vessel.", "choices": [{"value": v, "label": l} for v, l in [("type", "Type"), ("flag", "Flag"), ("dest", "Destination and ETA"), ("speed", "Speed"), ("distance", "Distance and bearing"), ("course", "Course"), ("status", "Navigational status"), ("length", "Length and beam"), ("imo", "IMO number")]]},
        {"name": "title", "type": "string", "label": "Title", "default": "", "help": "Blank uses the place."},
        sel("header", "Title line", "top", [("top", "Above the page"), ("bottom", "Below the page"), ("hidden", "Hidden")]),
        sel("footer", "Foot of the page", "show", [("show", "Status and credits"), ("credits", "Credits only"), ("hide", "Nothing")]),
        sel("paper", "Paper", "cream", [("cream", "Cream"), ("white", "White"), ("aged", "Aged"), ("blueprint", "Blueprint: pale ink on blue"), ("sea", "A soft sea wash")]),
        sel("panel", "Panel", "colour", [("colour", "Colour"), ("gray16", "16 greys"), ("gray4", "4 greys"), ("mono", "Black and white")], help="What the panel can show. Pictures are converted and contrast-stretched to match."),
        sel("text_size", "Text size", "100", [(v, f"{v}%") for v in ("60", "80", "100", "125", "150")]),
        sel("font", "Type", "fell", [("fell", "IM Fell English: the old plate"), ("archivo", "Archivo Narrow: clean and plain"), ("georgia", "Georgia: a modern serif"), ("page", "The dashboard's own font")], help="The face the page is set in. The dashboard's own font follows the page's font picker."),
    ]


WIDGETS = {
    "underway_photo": {
        "name": "Underway: Photo",
        "icon": "ph-boat",
        "description": "The nearest vessel to a place, right now, as a full-bleed photograph of the very ship (Wikimedia Commons) with her name, type, flag, destination, speed and distance, and the next few along a strip. Positions from aisstream.io or a receiver of your own.",
        "options": lambda: where_options() + [
            {"name": "strip", "type": "number", "label": "More vessels along the strip", "default": 5, "help": "0 to 8 after the nearest."},
            sel("photo_fit", "Photograph", "cover", [("cover", "Fills the page"), ("contain", "Fits inside the page")]),
        ] + page_options(["dest", "speed", "distance", "flag"]),
    },
    "underway_plate": {
        "name": "Underway: Plate",
        "icon": "ph-frame-corners",
        "description": "One vessel near you as a plate: painted from her own photograph in a style of your choosing, in a ruled frame, with her particulars beside her; or one of four modern looks in the colours of her trade. Her photograph until the painting lands, or without a fal.ai key.",
        "options": lambda: where_options() + picture_options(True, False) + page_options(["dest", "speed", "distance"]) + [
            sel("look", "Look", "plate", [("plate", "The plate: a ruled frame, the particulars beside it"), ("pass", "Boarding pass: the picture, a panel of particulars"), ("tiles", "Tiles: a bar, the picture, a tile for each figure"), ("poster", "Poster: the picture full-bleed, the particulars over it"), ("split", "Split: the picture framed on a dark page")], help="The plate is set in the page's type and paper. The other four are modern, in a plain sans, and take the colours below."),
            sel("colours", "Colours", "type", [("type", "Her trade's: deep blue for cargo, oxblood for tankers, green for fishing"), ("paper", "A neutral dark palette")], help="The modern looks colour the page by the vessel's trade; cargo, tanker, passenger, tug, fishing, sail, pleasure, service and naval each have a palette."),
        ],
    },
    "underway_fleet": {
        "name": "Underway: Fleet",
        "icon": "ph-anchor",
        "description": "Everything on the water near a place on one page: each vessel painted from her photograph or her particulars and cut out, sized by her length, with a caption; or, with photographs, a log of cards. Twenty-eight styles, a style builder and your own prompt.",
        "options": lambda: where_options() + [{"name": "count", "type": "number", "label": "How many", "default": 8, "help": "1 to 12."}] + picture_options(False, True) + [
            {"name": "scale", "type": "slider", "label": "Scale", "default": 100, "min": 40, "max": 100, "step": 5, "unit": "%", "help": "How far the painted fleet runs out to the margins. 100% fills the page; less packs it into the middle with more paper round it.", "show_if": {"pictures": "paintings"}},
        ] + page_options(["type", "dest", "speed", "distance"]),
    },
    "underway_scene": {
        "name": "Underway: Scene",
        "icon": "ph-waves",
        "description": "The nearest vessel as one whole painting across the page: the ship from her own photograph on a painted sea (open water, in harbour, along the coast, sunset, night, heavy weather or an ornate plate), with her particulars set over it. Her photograph without a fal.ai key.",
        "options": lambda: where_options() + picture_options(True, False, scene=True) + page_options(["dest", "speed", "distance"]),
    },
}

CORE = {
    "tesserae_compat": "1.x",
    "tesserae_min": TESSERAE_MIN,
    "name": "Underway Core",
    "version": VERSION,
    "kind": "data",
    "description": "The settings and the paintings page for the Underway widgets (underway_photo, underway_plate, underway_fleet, underway_scene): the aisstream.io key, the fal.ai key, the daily painting budget and the contact for Wikimedia Commons. No widget of its own.",
    "icon": "ph-anchor",
    "supports": {"sizes": []},
    "requires": ["network:*"],
    "settings": [
        {"name": "aisstream_key", "type": "string", "label": "aisstream.io API key", "secret": True, "default": "", "help": "Free at https://aisstream.io: sign in with GitHub and make a key. The widget keeps one stream open for the sea round each place while a page asks (aisstream allows three per key) and lets it go after twenty minutes without one. Not needed with a receiver of your own."},
        {"name": "fal_api_key", "type": "string", "label": "fal.ai API key (AI paintings)", "secret": True, "default": "", "help": "With a key the widgets can paint each vessel from her photograph, at about US$0.04 a painting, once per ship and style. Leave it blank to use the key under Settings › Generative AI. Without either the widgets show photographs."},
        {"name": "contact", "type": "string", "label": "Contact for Wikimedia Commons", "default": "", "help": "An email address or a web page, sent in the widget's User-Agent as Wikimedia asks of every application that reads its API. The widget names its own project page by default."},
        {"name": "gen_daily_usd", "type": "slider", "label": "Painting budget per day", "default": 4, "min": 0, "max": 30, "step": 1, "unit": "US$", "help": "The most the widgets may spend on new paintings in a day, at the models' listed prices (US$4 is about a hundred Nano Banana paintings). 0 is no limit, within the ceiling under Settings › Generative AI. Paintings are kept, so a ship in a style only costs once."},
        {"name": "gen_per_refresh", "type": "number", "label": "New paintings started per preview", "default": 3, "help": "How many new paintings one settled preview in the editor may start (1 to 50). A panel's own render starts what its page needs, within the daily budget."},
        {"name": "gen_parallel", "type": "number", "label": "Paintings made at once", "default": 3, "help": "How many paintings fal.ai works on side by side (1 to 8)."},
    ],
}

(ROOT / "underway_core" / "plugin.json").write_text(json.dumps(CORE, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
for wid, w in WIDGETS.items():
    manifest = {
        "tesserae_compat": "1.x",
        "name": w["name"],
        "version": VERSION,
        "kind": "widget",
        "tesserae_min": TESSERAE_MIN,
        "description": w["description"],
        "icon": w["icon"],
        "supports": {"sizes": ["sm", "md", "lg"]},
        "requires": ["network:*", "settings:plugin/underway_core", "plugin:underway_core"],
        "render": {"needs_network": True, "warm_ahead_s": 150},
        "design": {"palette": "extended"},
        "cell_options": w["options"](),
        "data_schema": {"fields": [{"name": "title", "type": "str", "label": "Title"}, {"name": "afloat", "type": "num", "label": "Vessels within reach"}, {"name": "vessels", "type": "arr", "label": "Vessels shown"}]},
    }
    names = [o["name"] for o in manifest["cell_options"]]
    assert len(names) == len(set(names)), wid
    (ROOT / wid / "plugin.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(wid, len(names), "options")
