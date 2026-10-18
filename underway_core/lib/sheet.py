"""One fetch for the four Underway widgets: the vessels near a place, their
particulars, photographs and paintings, and the words for the page. Loaded
by path from each widget's server.py."""

from __future__ import annotations

import contextlib
import hashlib
import importlib.util
import json
import logging
import random
import sys
import time
from concurrent.futures import ThreadPoolExecutor, wait
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

_HERE = Path(__file__).resolve().parent
logger = logging.getLogger("app.plugins.underway")


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
A = _sibling("ais")
P = _sibling("paint")
W = _sibling("watch")

WIDGETS = ("photo", "plate", "fleet", "scene")
SOURCES = ("aisstream", "receiver")
RADII = ("5", "10", "15", "25", "35", "50", "80")
ORDERS = ("nearest", "largest", "fastest", "moving")
PICTURES = ("photos", "paintings")
PANELS = ("colour", "gray16", "gray4", "mono")
PAPERS = ("cream", "white", "aged", "blueprint", "sea")
LABELS = (
    "type",
    "flag",
    "dest",
    "speed",
    "distance",
    "course",
    "status",
    "length",
    "imo",
    "seen",
)
PERIODS = ("now", "since")
PAINTS = ("all", "photo")
WATCH_STREAM_S = 20  # the stream is in memory: a look every so often costs nothing
WATCH_RECEIVER_S = 30
UNPAINTED = ("silhouette", "photo", "skip")
RANKINGS = ("photos", "order")
MAX_COUNT = 12
POOL = 6
PICTURE_PX = 700
HERO_PX = 1400
PHOTO_PX = 1600
LIVE_S = 6
LISTEN_S = 10  # a fresh listener: the page asks again this soon
BUDGET_S = 4.2  # the composer gives a widget six seconds; the lookups stop asking here
FONTS = ("fell", "archivo", "georgia", "page")
LOOKS = ("plate", "pass", "tiles", "poster", "split")
COLOURS = ("type", "paper")
LOOK_OPTIONS = frozenset(
    (
        "font",
        "scale",
        "fidelity",
        "visitor",
        "visitors",
        "pictures",
        "style",
        "custom_style",
        "build_medium",
        "build_period",
        "build_palette",
        "build_line",
        "build_texture",
        "build_mood",
        "build_extra",
        "model",
        "backdrop",
        "view",
        "unpainted",
        "labels",
        "text_size",
        "paper",
        "panel",
        "header",
        "footer",
        "title",
        "strip",
        "photo_fit",
        "colours",
        "look",
    )
)


def _choice(value: Any, choices: tuple[str, ...], default: str = "") -> str:
    v = str(value or "").strip()
    return v if v in choices else (default if default in choices else choices[0])


def _int(value: Any, default: int, low: int, high: int) -> int:
    with contextlib.suppress(TypeError, ValueError):
        return max(low, min(high, int(float(str(value).strip()))))
    return default


def _tz(options: dict[str, Any]) -> ZoneInfo | None:
    loc = options.get("location")
    name = loc.get("timezone") if isinstance(loc, dict) else ""
    with contextlib.suppress(Exception):
        if name:
            return ZoneInfo(str(name))
    return None


def place_of(
    options: dict[str, Any], ctx: dict[str, Any]
) -> tuple[float, float, str] | None:
    loc = options.get("location")
    label = str(loc.get("label") or "") if isinstance(loc, dict) else ""
    for lat, lon in (
        (options.get("latitude"), options.get("longitude")),
        (ctx.get("home_lat"), ctx.get("home_lon")),
    ):
        with contextlib.suppress(TypeError, ValueError):
            la, lo = float(lat), float(lon)
            if la or lo:
                return la, lo, label
    return None


def compass(deg: int) -> str:
    return ("N", "NE", "E", "SE", "S", "SW", "W", "NW")[round(deg / 45) % 8]


# ----------------------------------------------------------------------
# Words
# ----------------------------------------------------------------------
def shown_name(r: dict[str, Any]) -> str:
    return (
        r.get("name")
        or r.get("cs")
        or (f"MMSI {r['mmsi']}" if r.get("mmsi") else "Unknown vessel")
    )


def where_of(r: dict[str, Any]) -> str:
    if r.get("closest_text"):
        return f"closest {r['km']:g} km {compass(r['dir'])} at {r['closest_text']}"
    return f"{r['km']:g} km {compass(r['dir'])}"


def seen_of(r: dict[str, Any]) -> str:
    """When she was within reach: the span of a watched sighting, or how long
    since a live one was heard."""
    if r.get("seen_text"):
        return r["seen_text"]
    age = int(r.get("age_s") or 0)
    return "heard just now" if age < 90 else f"heard {age // 60} min ago"


def speed_of(r: dict[str, Any]) -> str:
    if r["sog"] >= 0.5:
        return f"{r['sog']:g} kt"
    return (
        r["status"] if r["status"] in ("moored", "at anchor", "aground") else "stopped"
    )


def course_of(r: dict[str, Any]) -> str:
    c = r["cog"] if r["cog"] >= 0 else r["hdg"]
    return f"course {c:03d}°" if c >= 0 and r["moving"] else ""


def dest_of(r: dict[str, Any]) -> str:
    if r.get("dest"):
        return f"to {r['dest']}" + (f", ETA {r['eta']}" if r.get("eta") else "")
    return r["status"] if not r["moving"] else "under way"


def length_of(r: dict[str, Any]) -> str:
    if not r.get("len"):
        return ""
    return f"{r['len']} m" + (f" × {r['beam']} m" if r.get("beam") else "")


def lines_for(r: dict[str, Any], labels: list[str]) -> list[str]:
    out: list[str] = []
    for lab in labels:
        if lab == "type":
            out.append(r["typ"])
        elif lab == "flag" and r.get("flag"):
            out.append(r["flag"])
        elif lab == "dest":
            out.append(dest_of(r))
        elif lab == "speed":
            out.append(speed_of(r))
        elif lab == "distance":
            out.append(where_of(r))
        elif lab == "course" and course_of(r):
            out.append(course_of(r))
        elif lab == "status":
            out.append(r["status"])
        elif lab == "length" and length_of(r):
            out.append(length_of(r))
        elif lab == "imo" and r.get("imo"):
            out.append(f"IMO {r['imo']}")
        elif lab == "seen":
            out.append(seen_of(r))
    return [x for x in out if x]


def about_of(r: dict[str, Any]) -> str:
    kind = A.CLASS_ABOUT.get(r.get("cls") or "other", "a vessel")
    if r["typ"].lower() != kind[2:]:
        kind = f"{kind}, {r['typ'].lower()}" if r["typ"] != "Vessel" else kind
    flag = f" under the flag of {r['flag']}" if r.get("flag") else ""
    size = f", {r['len']} metres long" if r.get("len") else ""
    doing = ""
    if r["moving"]:
        doing = (
            f" She is {r['status']} at {r['sog']:g} knots"
            if r["sog"] >= 0.5
            else f" She is {r['status']}"
        )
        if r.get("dest"):
            doing += f", bound for {r['dest']}"
            if r.get("eta"):
                doing += f" with an ETA of {r['eta']}"
        doing += f", {r['km']:g} km to the {compass(r['dir'])}."
    else:
        doing = f" She is {r['status']}, {r['km']:g} km to the {compass(r['dir'])}."
    return f"The {shown_name(r)} is {kind}{flag}{size}.{doing}"


def visitor_row(
    chance: int, subject: str, now: datetime, radius: float, chosen: Any = None
) -> dict[str, Any] | None:
    """Once an hour the dice are thrown for a page: something that should not
    be on the water, or nothing. The same hour and page always throw the same."""
    if chance <= 0:
        return None
    rng = random.Random(f"{now.strftime('%Y-%m-%d %H')}|{subject}")
    if rng.random() * 100 >= chance:
        return None
    shape = rng.choice(P.visitors_of(chosen))
    km = round(rng.uniform(1.5, max(2.0, radius * 0.9)), 1)
    deg = rng.randrange(0, 360)
    return {
        "mmsi": "",
        "name": P.MONSTERS[shape][0],
        "cs": "",
        "imo": "",
        "code": 0,
        "typ": P.MONSTERS[shape][0],
        "cls": "other",
        "len": 8,
        "beam": 0,
        "draught": 0,
        "sog": rng.choice((0.0, 0.0, 2.0, 6.0, 30.0)),
        "cog": deg,
        "hdg": deg,
        "status": "no AIS",
        "moving": True,
        "dest": "",
        "eta": "",
        "flag_cc": "",
        "flag": "",
        "km": km,
        "dir": deg,
        "age_s": 0,
        "visitor": shape,
    }


# ----------------------------------------------------------------------
# Held paintings, settling previews, the dashboards' records
# ----------------------------------------------------------------------
def watched(
    options: dict[str, Any],
    source: str,
    api_key: str,
    place: tuple[Any, ...],
    radius: float,
    data_dir: Path,
    ua: str,
    rows: list[dict[str, Any]],
    now: datetime,
    preview: bool,
    base: dict[str, Any],
    tz: Any,
) -> list[dict[str, Any]]:
    """Everything seen since this cell's last render: the watch on the place is
    started or kept, what this render saw is noted on it, and the vessels in
    the window come back at their closest approach, with when that was and
    whether they are still within reach."""
    receiver_url = str(options.get("receiver_url") or "")
    lat, lon = place[0], place[1]
    key = f"underway|{source}|{receiver_url}|{lat:.3f}|{lon:.3f}|{radius:g}"

    def poll() -> list[dict[str, Any]]:
        got, _err, _feed, _warming = A.nearby(
            source, receiver_url, api_key, lat, lon, radius, data_dir, ua
        )
        return got

    w = W.watch_for(
        key,
        poll,
        WATCH_RECEIVER_S if source == "receiver" else WATCH_STREAM_S,
        data_dir,
        lambda r: str(r.get("mmsi") or ""),
    )
    ts = now.timestamp()
    w.note(rows, ts)
    t0 = W.window(data_dir, subject_id(options), ts, advance=not preview)
    out = w.since(t0, ts)
    for r in out:
        here = ts - r["seen_last"] < A.STALE_S
        r["closest_text"] = W.clock(r["closest_at"], tz)
        r["seen_text"] = (
            f"within reach since {W.clock(r['seen_first'], tz)}"
            if here
            else f"seen {W.clock(r['seen_first'], tz)} to {W.clock(r['seen_last'], tz)}"
        )
        r["present"] = here
    since = W.clock(t0, tz)
    base["period"] = f"since {since}"
    base["since"] = t0
    base["watch"] = {
        "since": since,
        "seen": len(out),
        "polls": w.polls,
        "error": w.error,
        "present": sum(1 for r in out if r["present"]),
    }
    return out


def subject_id(options: dict[str, Any]) -> str:
    return hashlib.sha1(
        json.dumps(
            {k: v for k, v in sorted(options.items()) if k not in LOOK_OPTIONS},
            sort_keys=True,
            default=str,
        ).encode()
    ).hexdigest()[:16]


# ----------------------------------------------------------------------
# The fetch
# ----------------------------------------------------------------------
def fetch(
    options: dict[str, Any], settings: dict[str, Any], ctx: dict[str, Any], widget: str
) -> dict[str, Any]:
    widget = widget if widget in WIDGETS else "fleet"
    fetch_started = time.time()
    settings = settings or {}
    data_dir = Path(ctx.get("data_dir") or ".")
    with contextlib.suppress(OSError):
        data_dir.mkdir(parents=True, exist_ok=True)
    preview = bool(ctx.get("preview"))
    ua = A.user_agent(str(settings.get("contact") or ""))
    art = P.ART.open(ctx, settings, subject=subject_id(options))
    fal_key = art.key

    source = _choice(options.get("source"), SOURCES)
    radius = float(_choice(options.get("radius_km"), RADII, "25"))
    order = _choice(options.get("order"), ORDERS)
    count = _int(options.get("count"), 8, 1, MAX_COUNT)
    if widget in ("photo", "plate", "scene"):
        count = 1 + (_int(options.get("strip"), 5, 0, 8) if widget == "photo" else 0)
    include_moored = str(options.get("include_moored", "true")).lower() not in (
        "0",
        "false",
        "no",
        "off",
    )
    pictures = (
        _choice(options.get("pictures"), PICTURES) if widget != "photo" else "photos"
    )
    panel = _choice(options.get("panel"), PANELS)
    paper = _choice(options.get("paper"), PAPERS)
    labels = (
        [
            x
            for x in (options.get("labels") or ["type", "dest", "speed", "distance"])
            if x in LABELS
        ]
        if isinstance(options.get("labels"), list)
        else ["type", "dest", "speed", "distance"]
    )
    colours = (
        _choice(options.get("colours"), COLOURS, "type")
        if widget == "plate"
        else "paper"
    )
    look = (
        _choice(options.get("look"), LOOKS, "plate") if widget == "plate" else "plate"
    )
    header = _choice(options.get("header"), ("top", "bottom", "hidden"))
    footer = _choice(options.get("footer"), ("show", "credits", "hide"))
    text_size = _int(options.get("text_size"), 100, 60, 150)
    style = str(options.get("style") or "poster")
    how = ""
    if style == "builder":
        how = P.build_how(options)
        style = P.register_custom(how)
    elif style == "custom":
        words = (
            " ".join(str(options.get("custom_style") or "").split())[:600]
            or P.CUSTOM_EXAMPLE
        )
        how = words
        style = P.register_custom(how)
    elif style not in P.STYLES:
        style = "poster"
    model = P.model_of(str(options.get("model") or P.DEFAULT_MODEL))
    backdrop = _choice(options.get("backdrop"), tuple(P.BACKDROPS))
    if widget == "fleet":
        backdrop = "none"
    if widget == "scene" and backdrop == "none":
        backdrop = "sea"
    view = _choice(options.get("view"), tuple(P.VIEWS))
    fidelity = _choice(options.get("fidelity"), P.FIDELITIES)
    sea = ""
    sea_words = ""

    tz = _tz(options)
    now = datetime.now(tz) if tz else datetime.now().astimezone()
    place = place_of(options, ctx)
    title = " ".join(str(options.get("title") or "").split()) or (
        place[2] if place and place[2] else "Underway"
    )
    base: dict[str, Any] = {
        "widget": widget,
        "state": "ok",
        "title": title,
        "area": f"within {radius:g} km",
        "period": "on the water now",
        "date": now.strftime("%a %-d %b")
        if sys.platform != "win32"
        else now.strftime("%a %d %b"),
        "time": now.strftime("%H:%M"),
        "vessels": [],
        "afloat": 0,
        "shown": 0,
        "notices": [],
        "status": [],
        "credits": [],
        "live_refresh_s": 0,
        "header": header,
        "footer": footer,
        "paper": paper,
        "panel": panel,
        "text_size": text_size,
        "labels": labels,
        "colours": colours,
        "look": look,
        "pictures": pictures,
        "style": style,
        "style_label": P.style_of(style)[0],
        "backdrop": backdrop,
        "photo_fit": _choice(options.get("photo_fit"), ("cover", "contain")),
        "font_css": N.font_css(("im_fell", "im_fell_sc", "archivo_narrow")),
        "font": _choice(options.get("font"), FONTS),
        "scale": _int(options.get("scale"), 100, 40, 100),
    }
    if not place:
        return {
            **base,
            "state": "error",
            "error": "Set a place: the cell's location, or the app's location in Settings.",
        }

    if backdrop == "live" and pictures == "paintings":
        tod, wx = A.sea_now(
            place[0], place[1], now.hour * 60 + now.minute, data_dir, ua
        )
        sea, sea_words = f"{tod}_{wx}", A.sea_words(tod, wx)
        base["sea"] = {"time": tod, "weather": wx}
    api_key = str(settings.get("aisstream_key") or "").strip()
    licences = str(settings.get("photo_licences") or "nc").strip()
    more_photos = licences != "commons"  # Openverse too, or Commons alone
    photo_nc = licences != "open"
    notes = P.parse_notes(settings.get("fleet_notes"))
    ranking = _choice(options.get("ranking"), RANKINGS, "photos")
    paint = _choice(options.get("paint"), PAINTS, "all")
    rows, err, feed, warming = A.nearby(
        source,
        str(options.get("receiver_url") or ""),
        api_key,
        place[0],
        place[1],
        radius,
        data_dir,
        ua,
    )
    if err and not rows:
        return {**base, "state": "error", "error": err}
    period = _choice(options.get("period"), PERIODS, "now")
    if period == "since" and not err:
        rows = watched(
            options,
            source,
            api_key,
            place,
            radius,
            data_dir,
            ua,
            rows,
            now,
            preview,
            base,
            tz,
        )
    afloat = len(rows)
    base["afloat"] = afloat
    moving = [r for r in rows if r["moving"]]
    if not include_moored:
        rows = moving
    if order == "largest":
        rows.sort(key=lambda r: (-(r["len"] or A.CLASS_LEN.get(r["cls"], 0)), r["km"]))
    elif order == "fastest":
        rows.sort(key=lambda r: (-r["sog"], r["km"]))
    elif order == "moving":
        rows.sort(key=lambda r: (not r["moving"], r["km"]))
    unpainted = _choice(
        options.get("unpainted"),
        UNPAINTED,
        "photo" if widget in ("plate", "scene") else "silhouette",
    )
    only_painted = pictures == "paintings" and unpainted == "skip"
    # Photographed first: twice as many are looked up, and those with a
    # photograph lead within the order chosen, so a page is not silhouettes
    # and impressions while a photographed ship sits just beyond the count.
    depth = max(count, POOL) if only_painted else count
    if ranking == "photos":
        depth = max(depth, min(2 * count, MAX_COUNT + 4))
    pool = rows[:depth]
    shown = pool
    if not shown:
        if warming:
            return {
                **base,
                "state": "listening",
                "live_refresh_s": LISTEN_S,
                "hint": "Listening to aisstream.io for the vessels near you; the first show within a minute.",
            }
        return {
            **base,
            "state": "empty",
            "hint": "Nothing on the water within reach right now. A wider radius would show more."
            if source != "receiver"
            else "Your receiver hears nothing within reach right now.",
        }

    visitor = (
        visitor_row(
            _int(options.get("visitor"), 0, 0, 100),
            subject_id(options),
            now,
            radius,
            options.get("visitors"),
        )
        if pictures == "paintings" and widget != "photo"
        else None
    )
    deadline = fetch_started + BUDGET_S
    wants_photo = not only_painted and (
        pictures == "photos"
        or unpainted == "photo"
        or not fal_key
        or widget in ("photo", "plate", "scene")
    )

    def has_lookup(r: dict[str, Any]) -> bool:
        return bool(
            r.get("imo")
            or (
                more_photos
                and A.distinctive(r.get("name") or "")
                and r.get("cls") not in A.AMBIGUOUS
            )
        )

    def enrich(r: dict[str, Any]) -> dict[str, Any]:
        got: dict[str, Any] = {
            "photo": A.photo_of(
                r["imo"],
                data_dir,
                ua,
                r.get("name") or "",
                more_photos,
                photo_nc,
                strict=r.get("cls") in A.AMBIGUOUS,
            )
            if has_lookup(r)
            else {}
        }
        if (wants_photo or pictures == "paintings") and got["photo"].get("src"):
            N.cached_get(data_dir, got["photo"]["src"], ua=ua)
        return got

    plain = [r for r in shown if not r.get("visitor") and has_lookup(r)]
    deferred = 0
    for r in shown:
        r.setdefault("photo", {})
    if plain:
        tpool = ThreadPoolExecutor(max_workers=6, thread_name_prefix="underway-lookup")
        futures = {tpool.submit(enrich, r): r for r in plain}
        done, pending = wait(futures, timeout=max(0.2, deadline - time.time()))
        tpool.shutdown(wait=False)
        for f in done:
            r = futures[f]
            try:
                r.update(f.result())
            except Exception:
                logger.exception("underway: lookups for %s failed", r.get("mmsi"))
                pending.add(f)
        deferred += len(pending)
    if ranking == "photos":
        shown.sort(
            key=lambda r: not (r.get("photo") or {}).get("src")
        )  # stable: the order holds within
        if not only_painted:
            shown = shown[:count]
    if visitor:
        shown = shown + [visitor] if widget == "fleet" else shown[:1] + [visitor]
    for r in shown:
        if r.get("visitor"):
            r["lines"] = [
                "no AIS",
                f"{r['km']:g} km {compass(r['dir'])}",
                "unexplained",
            ]
            (
                r["shown_name"],
                r["where"],
                r["dest_text"],
                r["speed_text"],
                r["course_text"],
                r["length_text"],
            ) = (
                P.MONSTERS[r["visitor"]][0],
                where_of(r),
                "no destination",
                f"{r['sog']:g} kt" if r["sog"] else "still",
                "",
                "",
            )
            r["about"] = (
                "Something on the water with no transponder, no registry and no explanation."
            )
            r["sil"] = "/plugins/underway_core/static/sil/visitor.svg"
            r["compass"] = compass(r["dir"])
            continue
        r["shown_name"] = shown_name(r)
        r["lines"] = lines_for(r, labels)
        (
            r["where"],
            r["dest_text"],
            r["speed_text"],
            r["course_text"],
            r["length_text"],
        ) = where_of(r), dest_of(r), speed_of(r), course_of(r), length_of(r)
        r["about"] = about_of(r)
        r["compass"] = compass(r["dir"])
        r["sil"] = f"/plugins/underway_core/static/sil/{r['cls']}.svg"

    credits: list[str] = []
    px = (
        PHOTO_PX
        if widget in ("photo", "scene")
        else HERO_PX
        if widget == "plate"
        else PICTURE_PX
    )
    whole_ = backdrop != "none" or style in P.OWN_PAPER
    from_words = 0
    unreferenced = 0
    for r in shown:
        photo = r.get("photo") or {}
        pic: dict[str, Any] | None = None
        if pictures == "paintings" and r.get("visitor"):
            key = P.monster_key(r["visitor"], style)
            payload = {
                "monster": r["visitor"],
                "style": style,
                "how": how,
                "backdrop": "none",
                "model": model,
                "aspect": "4:3",
            }
            got = art.request(key, payload, title=f"{r['typ']}, {P.style_of(style)[0]}")
            r["pic"] = (
                P.picture(art, key, px, panel, style in P.OWN_PAPER)
                if got.ready
                else None
            )
            continue
        if pictures == "paintings" and paint == "photo" and not photo.get("src"):
            # nothing is asked for without a photograph to paint from; she shows as the unpainted do
            unreferenced += 1
        elif pictures == "paintings":
            has_photo = bool(photo.get("src"))
            who = r["imo"] or r["mmsi"] or r["name"]
            words, trade = ("", "") if has_photo else P.words_for(r["name"], notes)
            key = P.key_for(
                who,
                style,
                backdrop,
                view,
                model,
                sea,
                fidelity,
                photo=has_photo,
                words=f"{words}|{trade}" if words or trade else "",
            )
            payload = {
                "mmsi": r["mmsi"],
                "name": r["name"],
                "typ": r["typ"],
                "cls": r["cls"],
                "about": A.CLASS_ABOUT.get(r["cls"], "a vessel"),
                "flag": r["flag"],
                "len": r["len"],
                "beam": r.get("beam") or 0,
                "draught": r.get("draught") or 0,
                "sog": r.get("sog") or 0,
                "status": r.get("status") or "",
                "dest": r.get("dest") or "",
                "words": words,
                "trade": trade,
                "source": A.source_label(photo) if has_photo else "",
                "style": style,
                "how": how,
                "backdrop": backdrop,
                "sea_words": sea_words,
                "view": view,
                "fidelity": fidelity,
                "model": model,
                "photo": photo.get("src") or "",
                "by": photo.get("by") or "",
                "lic": photo.get("lic") or "",
                "link": photo.get("link") or "",
                "ua": ua,
                "aspect": "4:3",
            }
            if not has_photo:
                from_words += 1
            got = art.request(key, payload, title=f"{shown_name(r)}, {r['typ']}")
            if got.ready:
                pic = P.picture(art, key, px, panel, whole_)
                if pic:
                    pic[
                        "impression"
                    ] = not has_photo  # painted from her particulars, not a photograph
                if pic and pic.get("credit"):
                    credits.append(pic["credit"])
            elif got.state == "failed":
                r["why"] = got.why
        if (
            pic is None
            and photo.get("src")
            and not only_painted
            and (
                pictures == "photos"
                or unpainted == "photo"
                or not fal_key
                or widget in ("photo", "plate", "scene")
            )
        ):
            src = (
                A.photo_src(photo, data_dir, ua, px, panel)
                if time.time() < deadline
                else ""
            )
            if not src and time.time() >= deadline:
                deferred += 1
            if src:
                pic = {
                    "src": src,
                    "kind": "photo",
                    "whole": True,
                    "credit": f"photo by {photo.get('by') or 'a Commons contributor'} ({A.source_label(photo)}, {photo.get('lic') or 'open licence'})",
                    "aspect": N.aspect_of(src),
                    "link": photo.get("link") or "",
                }
                credits.append(pic["credit"])
        r["pic"] = pic
        r.pop("lat", None)
        r.pop("lon", None)
        r.pop("photo", None)
    if widget != "fleet":
        contact = next((r for r in shown if r.get("visitor")), None)
        shown = [r for r in shown if not r.get("visitor")]
        if contact and contact.get("pic"):
            base["visitor"] = contact
    if only_painted:
        shown = [
            r for r in shown if r.get("pic") and r["pic"].get("kind") == "painting"
        ][:count]
    elif widget == "fleet":
        shown = [r for r in shown if not r.get("visitor") or r.get("pic")]
    base["vessels"] = shown
    base["shown"] = len(shown)

    notices, status = [], []
    if pictures == "paintings":
        status.extend(art.status())
        notices.extend(art.notes())
        if from_words:
            status.append(
                f"{from_words} painted from particulars alone, without a photograph"
            )
        if unreferenced:
            status.append(f"{unreferenced} without a photograph, left unpainted")
        art.finish(ctx, facet=style)
    if err:
        notices.append(err)
    note = A.listener_note(source, api_key, place[0], place[1], radius)
    if note:
        notices.append(note)
    if base.get("watch"):
        wv = base["watch"]
        status.insert(
            0,
            f"{wv['seen']} seen since {wv['since']}, {wv['present']} within reach now"
            if wv["seen"]
            else f"nothing seen since {wv['since']}",
        )
        if wv.get("error"):
            notices.append(f"the watch between renders: {wv['error']}")
    note = A.openverse_note(data_dir) if more_photos else ""
    if note:
        notices.append(note)
    live = art.live()
    if deferred:
        status.append(f"{deferred} picture{'' if deferred == 1 else 's'} on the way")
        live["live_refresh_s"] = max(live["live_refresh_s"], LIVE_S)
    if warming:
        live["live_refresh_s"] = max(live["live_refresh_s"], LISTEN_S)
    if only_painted and not shown:
        waiting = sum(art.states.get(k, 0) for k in ("painting", "waiting", "held"))
        base.update(
            state="painting", notices=notices, status=status, afloat=afloat, **live
        )
        base["hint"] = (
            f"Painting {waiting} of the vessels near you; the page fills as they land."
            if waiting
            else P.NOTE_NO_KEY
            if art.states.get("no_key")
            else P.NEEDS_HOST
            if art.states.get("no_host")
            else "Nothing near you is painted yet."
        )
        return base
    base.update(
        notices=notices,
        status=status,
        credits=list(dict.fromkeys(credits))[:4],
        afloat=afloat,
        moving=len(moving),
        attribution=f"positions from {feed or 'aisstream.io'}"
        if source == "aisstream"
        else "positions from your receiver",
        **live,
    )
    logger.info(
        "underway: %s %s, %d near, %d shown, painted %d, started %d, held %d, from words %d",
        "preview" if preview else "panel",
        widget,
        afloat,
        len(shown),
        art.states.get("ready", 0),
        art.started,
        art.states.get("held", 0),
        from_words,
    )
    return base
