"""Offline tests for the Underway bundle: the stream, the receiver, the
photographs, the paintings and the four pages, with every call on the
network answered here."""

from __future__ import annotations

import importlib.util
import io
import json
import os
import struct
import subprocess
import sys
import time
import urllib.parse
from pathlib import Path

import pytest

# The widget paints through Tesserae's ``app.artwork`` (0.463+): the server's
# repo must be importable. A checkout beside this one, or TESSERAE_REPO.
_TESSERAE = Path(
    os.environ.get("TESSERAE_REPO") or Path(__file__).resolve().parents[3] / "tesserae"
)
if str(_TESSERAE) not in sys.path:
    sys.path.insert(0, str(_TESSERAE))
from app import fal as fal_mod  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


fleet = _load(ROOT / "underway_fleet" / "server.py", "underway_fleet_server")
photo = _load(ROOT / "underway_photo" / "server.py", "underway_photo_server")
plate = _load(ROOT / "underway_plate" / "server.py", "underway_plate_server")
scene = _load(ROOT / "underway_scene" / "server.py", "underway_scene_server")
core = _load(ROOT / "underway_core" / "server.py", "underway_core_server")
S = fleet._lib("sheet")
A = S.A
P = S.P
N = S.N
W = S.W
WS = A.WS

PORT_MELBOURNE = {
    # The fixtures fake the aisstream listener; Open Waters is the default now.
    "source": "aisstream",
    "latitude": -37.84,
    "longitude": 144.92,
    "location": {"label": "Port Melbourne", "timezone": "Australia/Melbourne"},
}
SETTINGS = {
    "fal_api_key": "k",
    "aisstream_key": "ais-key",
    "contact": "tester@example.com",
    "gen_daily_usd": "1",
    "photo_licences": "commons",
}
# What a receiver (AIS-catcher) answers: a container ship, a tanker at anchor, a tug, a yacht, one far away, one without a position
SHIPS = [
    {
        "mmsi": 219018271,
        "shipname": "MAERSK ELBA@@@",
        "callsign": "OWJH2",
        "imo": 9458054,
        "shiptype": 71,
        "lat": -37.86,
        "lon": 144.93,
        "speed": 12.4,
        "cog": 215,
        "heading": 214,
        "status": 0,
        "destination": "AU MEL",
        "eta_month": 10,
        "eta_day": 20,
        "eta_hour": 6,
        "eta_minute": 0,
        "to_bow": 250,
        "to_stern": 116,
        "to_port": 20,
        "to_starboard": 25,
        "draught": 13.2,
        "country": "DK",
        "last_signal": 12,
    },
    {
        "mmsi": 538005432,
        "shipname": "NORDIC AURORA",
        "imo": 9312345,
        "shiptype": 84,
        "lat": -37.9,
        "lon": 144.88,
        "speed": 0.1,
        "cog": 90,
        "heading": 180,
        "status": 1,
        "destination": "GEELONG",
        "to_bow": 180,
        "to_stern": 64,
        "to_port": 16,
        "to_starboard": 16,
        "country": "MH",
        "last_signal": 40,
    },
    {
        "mmsi": 503012345,
        "shipname": "SVITZER EUREKA",
        "shiptype": 52,
        "lat": -37.845,
        "lon": 144.925,
        "speed": 6.0,
        "cog": 30,
        "heading": 32,
        "status": 0,
        "to_bow": 20,
        "to_stern": 12,
        "to_port": 6,
        "to_starboard": 6,
        "country": "AU",
        "last_signal": 3,
    },
    {
        "mmsi": 503999999,
        "shipname": "LADY ANNE",
        "shiptype": 36,
        "lat": -37.85,
        "lon": 144.95,
        "speed": 4.2,
        "cog": 120,
        "status": 8,
        "last_signal": 60,
    },
    {
        "mmsi": 636019876,
        "shipname": "FAR AWAY",
        "imo": 9000001,
        "shiptype": 70,
        "lat": -38.9,
        "lon": 146.5,
        "speed": 14,
        "cog": 90,
        "status": 0,
        "last_signal": 5,
    },
    {"mmsi": 503000000, "shipname": "NOPOS", "shiptype": 30, "lat": None, "lon": None},
]


def _jpeg(w=600, h=400, blob=True, paper=(255, 255, 255)) -> bytes:
    from PIL import Image, ImageDraw

    im = Image.new("RGB", (w, h), paper)
    if blob:
        d = ImageDraw.Draw(im)
        d.rectangle((120, 190, 480, 250), fill=(40, 60, 120))
        d.rectangle((300, 120, 380, 190), fill=(220, 220, 225))
    out = io.BytesIO()
    im.save(out, "JPEG", quality=85)
    return out.getvalue()


class _Prompts:
    """The prompts fal.ai got (live, by reference) and the Openverse searches made."""

    def __init__(self, prompts, flickr):
        self._p, self.flickr = prompts, flickr

    def __len__(self):
        return len(self._p)

    def __iter__(self):
        return iter(self._p)

    def __getitem__(self, i):
        return self._p[i]


@pytest.fixture
def offline(monkeypatch):
    """Every call on the network, answered here; the prompts fal.ai got."""
    prompts: list[dict] = []
    uas: list[str] = []
    flickr_calls: list[dict] = []

    def fake_http(
        url,
        token="",
        accept="application/json",
        *,
        auth_scheme="Bearer",
        body=None,
        timeout=10,
        detail=False,
        ua="",
    ):
        uas.append(ua)
        if "ships.json" in url:
            return json.dumps({"count": len(SHIPS), "ships": SHIPS}).encode(), None
        if "commons.wikimedia.org" in url:
            assert "tesserae-underway" in ua
            if "categorymembers" in url:
                if "IMO%209000001" in url or "IMO+9000001" in url:
                    return json.dumps({"query": {"categorymembers": []}}).encode(), None
                if (
                    "IMO" in url
                ):  # the IMO category holds the ship's category, as on Commons
                    return json.dumps(
                        {
                            "query": {
                                "categorymembers": [
                                    {"title": "Category:Maersk Elba (ship, 2011)"}
                                ]
                            }
                        }
                    ).encode(), None
                return json.dumps(
                    {
                        "query": {
                            "categorymembers": [
                                {"title": "File:Maersk Elba 2019.jpg"},
                                {"title": "File:Maersk Elba bow.jpg"},
                                {"title": "File:Elba plan.svg"},
                                {"title": "Category:Maersk Elba in Rotterdam"},
                            ]
                        }
                    }
                ).encode(), None
            return json.dumps(
                {
                    "query": {
                        "pages": {
                            "1": {
                                "imageinfo": [
                                    {
                                        "thumburl": "https://upload.wikimedia.org/elba_wide.jpg",
                                        "width": 1800,
                                        "height": 1200,
                                        "descriptionurl": "https://commons.wikimedia.org/wiki/File:Maersk_Elba_2019.jpg",
                                        "extmetadata": {
                                            "Artist": {
                                                "value": '<a href="x">A. Spotter</a>'
                                            },
                                            "LicenseShortName": {
                                                "value": "CC BY-SA 4.0"
                                            },
                                        },
                                    }
                                ]
                            },
                            "2": {
                                "imageinfo": [
                                    {
                                        "thumburl": "https://upload.wikimedia.org/elba_tall.jpg",
                                        "width": 800,
                                        "height": 1600,
                                        "descriptionurl": "",
                                        "extmetadata": {},
                                    }
                                ]
                            },
                            "3": {
                                "title": "File:Maersk Elba builder's plaque.jpg",
                                "imageinfo": [
                                    {
                                        "thumburl": "https://upload.wikimedia.org/elba_plaque.jpg",
                                        "width": 2400,
                                        "height": 1600,
                                        "descriptionurl": "",
                                        "extmetadata": {},
                                    }
                                ],
                            },
                        }
                    }
                }
            ).encode(), None
        if "upload.wikimedia.org" in url or "staticflickr.com" in url:
            return _jpeg(), None
        if "api.openverse.org" in url:
            q = dict(urllib.parse.parse_qsl(urllib.parse.urlsplit(url).query))
            flickr_calls.append(q)
            lic = set(q["license"].split(","))
            text = q["q"].upper()
            found = []
            if text == '"SVITZER EUREKA"':
                found = [
                    {
                        "id": "501",
                        "title": "Svitzer Eureka",
                        "creator": "Port Spotter",
                        "license": "by-nc",
                        "license_version": "2.0",
                        "source": "flickr",
                        "tags": [{"name": "tug"}, {"name": "melbourne"}],
                        "url": "https://live.staticflickr.com/501_b.jpg",
                        "width": 1024,
                        "height": 683,
                        "foreign_landing_url": "https://www.flickr.com/photos/11@N02/501/",
                    },
                    {
                        "id": "502",
                        "title": "Eureka Tower at dusk",
                        "creator": "Tower Fan",
                        "license": "by",
                        "license_version": "2.0",
                        "source": "flickr",
                        "tags": [{"name": "skyline"}],
                        "url": "https://live.staticflickr.com/502_b.jpg",
                        "width": 1024,
                        "height": 768,
                        "foreign_landing_url": "https://www.flickr.com/photos/12@N02/502/",
                    },
                ]
            elif text == '"LADY ANNE"':
                found = [
                    {
                        "id": "503",
                        "title": "Lady Anne",
                        "creator": "A. Painter",
                        "license": "by",
                        "license_version": "2.0",
                        "source": "flickr",
                        "tags": [{"name": "portrait"}, {"name": "oil"}],
                        "url": "https://live.staticflickr.com/503_b.jpg",
                        "width": 1024,
                        "height": 1400,
                        "foreign_landing_url": "https://www.flickr.com/photos/13@N02/503/",
                    }
                ]
            elif text == "IMO 9312345":
                found = [
                    {
                        "id": "504",
                        "title": "NORDIC AURORA - IMO 9312345",
                        "creator": "Tanker Watch",
                        "license": "by-sa",
                        "license_version": "4.0",
                        "source": "wikimedia",
                        "tags": [],
                        "url": "https://upload.wikimedia.org/aurora.jpg",
                        "width": 1024,
                        "height": 600,
                        "foreign_landing_url": "https://commons.wikimedia.org/wiki/File:Aurora.jpg",
                    }
                ]
            found = [f for f in found if f["license"] in lic]
            return json.dumps(
                {"result_count": len(found), "results": found}
            ).encode(), None
        if "open-meteo" in url:
            return json.dumps(
                {
                    "current": {
                        "weather_code": 61,
                        "cloud_cover": 90,
                        "is_day": 1,
                        "wind_speed_10m": 20,
                    },
                    "daily": {
                        "sunrise": ["2026-10-17T06:30"],
                        "sunset": ["2026-10-17T19:40"],
                    },
                }
            ).encode(), None
        return None, "unreachable"

    monkeypatch.setattr(N, "http", fake_http)
    monkeypatch.setattr(A, "OPENVERSE_GAP_S", 0.0)
    monkeypatch.setattr(
        A, "commons", None
    )  # the widget's own lookup; the host's has its own test below

    def fake_fal(url, body, key, timeout):
        prompts.append({**body, "_url": url})
        assert key == "k"
        return {"images": [{"url": "https://fal.example/out.jpg"}]}

    monkeypatch.setattr(fal_mod, "_http_json", fake_fal)
    monkeypatch.setattr(
        fal_mod, "_download", lambda url, timeout=60.0: _jpeg(paper=(252, 250, 246))
    )
    prompts_seen = _Prompts(prompts, flickr_calls)
    yield prompts_seen, uas
    P.ART.stop_all(Path("."))
    A.stop_listeners()
    W.stop_watches()


class FakeListener:
    """What listener_for hands a fetch, with the receiver's ships as if heard."""

    def __init__(self, records=None, warming=False, error=""):
        self.records = (
            records if records is not None else A._receiver_rows({"ships": SHIPS})
        )
        self.warming = warming
        self.error = error
        self.connected = not error
        self.asked = time.time()

    def snapshot(self):
        return [dict(v) for v in self.records if v.get("lat") is not None]


@pytest.fixture
def stream(monkeypatch):
    """aisstream, as a listener that has already heard the ships."""
    lst = FakeListener()
    monkeypatch.setattr(A, "listener_for", lambda key, box, data_dir, ua: lst)
    return lst


def _busy() -> bool:
    pr = P.ART.progress(Path("."), {})
    return bool(pr["running"] or pr["queued"])


def _settle(timeout=10.0):
    end = time.time() + timeout
    while _busy() and time.time() < end:
        time.sleep(0.02)
    assert not _busy()


def _ctx(tmp_path, **kw):
    ctx = {"data_dir": str(tmp_path), "cell_w": 800, "cell_h": 480, **kw}
    ctx.setdefault("settled", not ctx.get("preview"))
    return ctx


RECEIVER = {
    **PORT_MELBOURNE,
    "source": "receiver",
    "receiver_url": "http://pi.local:8100",
}


# ----------------------------------------------------------------------
def test_manifests_and_client_files():
    for wid in (
        "underway_core",
        "underway_photo",
        "underway_plate",
        "underway_fleet",
        "underway_scene",
    ):
        m = json.loads((ROOT / wid / "plugin.json").read_text(encoding="utf-8"))
        assert (
            m["version"] == "0.7.0"
            and m["tesserae_compat"] == "1.x"
            and m["tesserae_min"] == "0.463.0"
        )
        if m["kind"] == "widget":
            assert m["render"]["warm_ahead_s"] == 150
            assert (ROOT / wid / "client.js").exists()
            names = [o["name"] for o in m["cell_options"]]
            assert len(names) == len(set(names))
    for cls in A.CLASSES + ("visitor",):
        assert (ROOT / "underway_core" / "static" / "sil" / f"{cls}.svg").exists(), cls


RELEASED = "v0.6.0"  # the saved cells to keep working: no option, choice value or default may change
UP_FRONT = {
    "underway_photo": ["source", "location", "radius_km", "strip", "paper"],
    "underway_plate": ["source", "location", "radius_km", "pictures", "look"],
    "underway_fleet": ["source", "location", "radius_km", "count", "pictures", "paper"],
    "underway_scene": ["source", "location", "radius_km", "pictures", "paper"],
}
ADVANCED = [
    "include_moored",
    "order",
    "period",
    "labels",
    "title",
    "header",
    "footer",
    "panel",
    "text_size",
    "font",
]
PAINTING_ADVANCED = [
    "paint",
    "fidelity",
    "view",
    "model",
    "visitor",
    "visitors",
    "unpainted",
]


DEFAULT_MOVED = {"source"}  # 0.7.0: Open Waters AIS became the default


def test_options_panel_is_short_and_keeps_saved_cells():
    for wid, up_front in UP_FRONT.items():
        opts = json.loads((ROOT / wid / "plugin.json").read_text(encoding="utf-8"))[
            "cell_options"
        ]
        by = {o["name"]: o for o in opts}
        assert [
            o["name"] for o in opts if not o.get("show_if") and not o.get("advanced")
        ] == up_front, wid
        assert by["receiver_url"]["show_if"] == {"source": "receiver"} and not by[
            "receiver_url"
        ].get("advanced")
        for o in opts:
            for key, want in (o.get("show_if") or {}).items():
                assert key in by, (wid, o["name"], key)
                values = {c["value"] for c in by[key].get("choices", [])}
                for w in (
                    want
                    if isinstance(want, list)
                    else [want.get("not") if isinstance(want, dict) else want]
                ):
                    assert not values or w in values, (wid, o["name"], key, w)
            assert o["label"] != "Type" and "\u2014" not in o["label"] + o.get(
                "help", ""
            ), (wid, o["name"])
        for name in ADVANCED + (
            PAINTING_ADVANCED + ["ranking"] if "pictures" in by else ["photo_fit"]
        ):
            assert by[name].get("advanced") is True, (wid, name)
        if "pictures" in by:
            for name in ["style", "custom_style", "build_medium", *PAINTING_ADVANCED]:
                assert by[name]["show_if"]["pictures"] == "paintings", (wid, name)
            for name in ("style", "custom_style", "build_medium"):
                assert not by[name].get("advanced"), (wid, name)
        try:
            old = json.loads(
                subprocess.run(
                    ["git", "-C", str(ROOT), "show", f"{RELEASED}:{wid}/plugin.json"],
                    capture_output=True,
                    check=True,
                ).stdout
            )
        except (OSError, subprocess.CalledProcessError):
            continue  # a copy without the history
        old = {o["name"]: o for o in old["cell_options"]}
        assert set(old) == set(by), wid
        for name, o in old.items():
            n = by[name]
            # A saved cell keeps its meaning when the type is the same and every
            # value it could hold is still offered. A choice may be added, and a
            # default may move only where a release did so on purpose: 0.7.0 made
            # Open Waters, which needs no key, the source.
            assert n["type"] == o["type"], (wid, name)
            old_values = [c["value"] for c in o.get("choices", [])]
            new_values = [c["value"] for c in n.get("choices", [])]
            assert set(old_values) <= set(new_values), (wid, name)
            if name not in DEFAULT_MOVED:
                assert n.get("default") == o.get("default"), (wid, name)
    fl = {
        o["name"]: o
        for o in json.loads(
            (ROOT / "underway_fleet" / "plugin.json").read_text(encoding="utf-8")
        )["cell_options"]
    }
    for name in ("scale", "when_spent"):
        assert (
            fl[name]["show_if"] == {"pictures": "paintings"}
            and fl[name]["advanced"] is True
        )
    pl = {
        o["name"]: o
        for o in json.loads(
            (ROOT / "underway_plate" / "plugin.json").read_text(encoding="utf-8")
        )["cell_options"]
    }
    assert (
        pl["paper"]["show_if"] == {"look": "plate"}
        and pl["colours"]["advanced"] is True
    )


# ----------------------------------------------------------------------
# Decoding
# ----------------------------------------------------------------------
def test_types_flags_names_and_etas():
    assert A.type_of(71) == ("Cargo ship", "cargo", 71)
    assert (
        A.type_of(84)[1] == "tanker"
        and A.type_of(52) == ("Tug", "tug", 52)
        and A.type_of(0)[1] == "other"
        and A.type_of("x")[1] == "other"
    )
    assert A.flag_of("219018271") == ("DK", "Denmark") and A.flag_of("503012345") == (
        "AU",
        "Australia",
    )
    assert A.flag_of("123", "MH") == ("MH", "Marshall Islands") and A.flag_of(
        "000000000"
    ) == ("", "")
    assert A.flag_of("002310000") == ("FO", "Faroe Islands"), (
        "a coast station's MID sits after two zeros"
    )
    assert (
        A.ship_name("MAERSK ELBA@@@@") == "Maersk Elba"
        and A.ship_name("MSC LORETO") == "MSC Loreto"
        and A.ship_name("LADY ANNE") == "Lady Anne"
        and A.ship_name("PB 24") == "PB 24"
    )
    assert (
        A.ship_name("SPIRIT OF TASMANIA I") == "Spirit of Tasmania I"
        and A.ship_name("") == ""
    )
    assert (
        A.destination_name("AU MEL") == "AU MEL"
        and A.destination_name("PORT KEMBLA") == "Port Kembla"
    )
    assert A.destination_name("MELBOURNE>SYDNEY") == "Melbourne to Sydney"
    assert (
        A.eta_text(10, 20, 14, 30).endswith("14:30")
        and A.eta_text(0, 0, 24, 60) == ""
        and A.eta_text("x", 1, 1, 1) == ""
    )
    assert A.status_of(1, 0.0) == ("at anchor", False) and A.status_of(0, 12.0) == (
        "under way using engine",
        True,
    )
    assert (
        A.status_of(5, 3.0) == ("moored", False)
        and A.status_of(15, 2.0) == ("under way", True)
        and A.status_of(15, 0.0) == ("stopped", False)
    )
    assert A.status_of(0, -1) == ("under way using engine", True), (
        "no speed reading, but the status says under way"
    )
    box = A.bbox_of(-37.84, 144.92, 25)
    assert box[0][0] < -37.84 < box[1][0] and box[0][1] < 144.92 < box[1][1]


def test_rows_from_a_receiver(tmp_path, offline):
    rows, err, feed, warming = A.nearby(
        "receiver", "pi.local:8100", "", -37.84, 144.92, 35, tmp_path, "ua"
    )
    assert err is None and feed == "your receiver" and not warming
    assert [r["name"] for r in rows] == [
        "Svitzer Eureka",
        "Maersk Elba",
        "Lady Anne",
        "Nordic Aurora",
    ], "nearest first, the far one and the one without a position left out"
    elba = next(r for r in rows if r["imo"] == "9458054")
    assert (
        elba["typ"] == "Cargo ship"
        and elba["cls"] == "cargo"
        and elba["flag"] == "Denmark"
        and elba["len"] == 366
        and elba["beam"] == 45
    )
    assert (
        elba["dest"] == "AU MEL"
        and elba["eta"].endswith("06:00")
        and elba["moving"]
        and elba["sog"] == 12.4
        and elba["cs"] == "OWJH2"
    )
    aurora = next(r for r in rows if r["name"] == "Nordic Aurora")
    assert (
        aurora["status"] == "at anchor"
        and not aurora["moving"]
        and aurora["flag"] == "Marshall Islands"
        and aurora["imo"] == "9312345"
    )
    anne = next(r for r in rows if r["name"] == "Lady Anne")
    assert (
        anne["cls"] == "sail"
        and anne["imo"] == ""
        and anne["status"] == "under way sailing"
        and anne["flag"] == "Australia"
    )
    # the receiver's answer is kept LIVE_S so the editor's refreshes share one
    rows2, *_ = A.nearby(
        "receiver", "http://pi.local:8100", "", -37.84, 144.92, 35, tmp_path, "ua"
    )
    assert len(rows2) == len(rows)
    assert A.nearby("receiver", "", "", -37.84, 144.92, 35, tmp_path, "ua")[
        1
    ].startswith("Give the receiver")
    assert A.nearby("aisstream", "", "", -37.84, 144.92, 35, tmp_path, "ua")[
        1
    ].startswith("Give an aisstream.io key")


def test_the_listener_hears_the_stream(tmp_path):
    """aisstream's messages, as documented: a position report with the name in
    the metadata, the static data with the rest, a class B report, and a part
    24 static report; the vessels kept on disk and read back."""
    lst = A.Listener.__new__(A.Listener)
    lst.key, lst.box, lst.path, lst.ua = (
        "k",
        [[0, 0], [1, 1]],
        tmp_path / "live" / "x.json",
        "ua",
    )
    lst.vessels, lst.heard, lst.error, lst.connected, lst.started, lst.asked = (
        {},
        0,
        "",
        True,
        time.time(),
        time.time(),
    )
    import threading

    lst.lock, lst.stop, lst._dirty = threading.Lock(), threading.Event(), False
    lst._hear(
        json.dumps(
            {
                "MessageType": "PositionReport",
                "MetaData": {
                    "MMSI": 219018271,
                    "ShipName": "MAERSK ELBA",
                    "latitude": -37.86,
                    "longitude": 144.93,
                },
                "Message": {
                    "PositionReport": {
                        "UserID": 219018271,
                        "Latitude": -37.86,
                        "Longitude": 144.93,
                        "Sog": 12.4,
                        "Cog": 215.3,
                        "TrueHeading": 214,
                        "NavigationalStatus": 0,
                    }
                },
            }
        ).encode()
    )
    lst._hear(
        json.dumps(
            {
                "MessageType": "ShipStaticData",
                "MetaData": {"MMSI": 219018271},
                "Message": {
                    "ShipStaticData": {
                        "UserID": 219018271,
                        "Name": "MAERSK ELBA",
                        "Type": 71,
                        "CallSign": "OWJH2",
                        "ImoNumber": 9458054,
                        "Destination": "AU MEL",
                        "Eta": {"Month": 10, "Day": 20, "Hour": 6, "Minute": 0},
                        "Dimension": {"A": 250, "B": 116, "C": 20, "D": 25},
                        "MaximumStaticDraught": 13.2,
                    }
                },
            }
        ).encode()
    )
    lst._hear(
        json.dumps(
            {
                "MessageType": "StandardClassBPositionReport",
                "MetaData": {"MMSI": 503999999, "ShipName": ""},
                "Message": {
                    "StandardClassBPositionReport": {
                        "UserID": 503999999,
                        "Latitude": -37.85,
                        "Longitude": 144.95,
                        "Sog": 4.2,
                        "Cog": 120,
                        "TrueHeading": 511,
                    }
                },
            }
        ).encode()
    )
    lst._hear(
        json.dumps(
            {
                "MessageType": "StaticDataReport",
                "MetaData": {"MMSI": 503999999},
                "Message": {
                    "StaticDataReport": {
                        "UserID": 503999999,
                        "PartNumber": True,
                        "ReportA": {"Name": "LADY ANNE"},
                        "ReportB": {
                            "ShipType": 36,
                            "CallSign": "VJN1234",
                            "Dimension": {"A": 8, "B": 7, "C": 2, "D": 3},
                        },
                    }
                },
            }
        ).encode()
    )
    lst._hear(b"not json")
    lst._hear(
        json.dumps(
            {"MessageType": "PositionReport", "MetaData": {}, "Message": {}}
        ).encode()
    )
    assert lst.heard == 4
    rows = [A.make_row(v, -37.84, 144.92, time.time()) for v in lst.snapshot()]
    elba = next(r for r in rows if r["mmsi"] == "219018271")
    assert (
        elba["name"] == "Maersk Elba"
        and elba["imo"] == "9458054"
        and elba["dest"] == "AU MEL"
        and elba["len"] == 366
        and elba["cog"] == 215
        and elba["eta"]
    )
    anne = next(r for r in rows if r["mmsi"] == "503999999")
    assert (
        anne["name"] == "Lady Anne"
        and anne["cls"] == "sail"
        and anne["len"] == 15
        and anne["hdg"] == -1
    )
    lst._save()
    again = A.Listener.__new__(A.Listener)
    got = N.read_json(lst.path, {})
    assert set(got["vessels"]) == {"219018271", "503999999"}
    with pytest.raises(WS.WebSocketError):
        lst._hear(json.dumps({"error": "Api Key Is Not Valid"}).encode())
    del again


def test_the_websocket_frames(monkeypatch):
    """The client's framing against a server that answers by hand: a short text
    frame, a 16-bit length, a ping answered with a pong, fragments joined, and
    what the client sends out is masked."""

    class Sock:
        def __init__(self, inbound: bytes):
            self.inbound, self.sent = inbound, b""

        def recv(self, n):
            out, self.inbound = self.inbound[:n], self.inbound[n:]
            return out

        def sendall(self, data):
            self.sent += data

        def settimeout(self, t):
            pass

        def close(self):
            pass

    def frame(op, payload, fin=True):
        head = bytes([(0x80 if fin else 0) | op])
        n = len(payload)
        if n < 126:
            head += bytes([n])
        elif n < 65536:
            head += bytes([126]) + struct.pack("!H", n)
        else:
            head += bytes([127]) + struct.pack("!Q", n)
        return head + payload

    inbound = b"".join(
        [
            frame(WS.OP_TEXT, b'{"a":1}'),
            frame(WS.OP_PING, b"hi"),
            frame(WS.OP_TEXT, b"x" * 300),
            frame(WS.OP_TEXT, b"part one ", fin=False),
            frame(WS.OP_CONT, b"part two"),
            frame(WS.OP_CLOSE, struct.pack("!H", 1000)),
        ]
    )
    ws = WS.WebSocket.__new__(WS.WebSocket)
    ws.sock, ws._buf, ws._partial, ws._partial_op, ws.closed = (
        Sock(inbound),
        b"",
        [],
        0,
        False,
    )
    assert ws.recv() == (WS.OP_TEXT, b'{"a":1}')
    assert ws.recv() == (WS.OP_TEXT, b"x" * 300), (
        "the ping in between was answered, not handed over"
    )
    assert ws.sock.sent[0] == 0x80 | WS.OP_PONG and ws.sock.sent[1] & 0x80, (
        "the pong went out masked"
    )
    assert ws.recv() == (WS.OP_TEXT, b"part one part two")
    assert ws.recv() is None and ws.closed
    ws.sock.sent = b""
    ws.closed = False
    ws.send_text("hello")
    sent = ws.sock.sent
    assert sent[0] == 0x80 | WS.OP_TEXT and sent[1] == 0x80 | 5
    mask, body = sent[2:6], sent[6:]
    assert bytes(b ^ mask[i % 4] for i, b in enumerate(body)) == b"hello"


def test_commons_photo_by_imo(tmp_path, offline):
    p = A.photo_of(
        "9458054", tmp_path, A.user_agent("tester@example.com"), "Maersk Elba"
    )
    assert (
        p["src"].endswith("elba_wide.jpg")
        and p["by"] == "A. Spotter"
        and p["lic"] == "CC BY-SA 4.0"
    ), "the landscape one, not the plaque, the artist's HTML stripped"
    ua = A.user_agent("")
    assert (
        A.photo_of("9000001", tmp_path, ua) == {} and A.photo_of("", tmp_path, ua) == {}
    )
    assert (tmp_path / "photos" / "imo_9458054.json").exists()
    src = A.photo_src(p, tmp_path, ua, 400, "colour")
    assert src.startswith("data:image/jpeg;base64,")


def test_sea_now_and_words(tmp_path, offline):
    tod, wx = A.sea_now(-37.84, 144.92, 9 * 60, tmp_path, "ua")
    assert tod == "morning" and wx == "rain"
    assert A.weather_bucket(0, 0, 60) == "gale" and A.weather_bucket(95, 0) == "storm"
    assert "in the same style" in A.sea_words(tod, wx) and "rain" in A.sea_words(
        tod, wx
    )


# ----------------------------------------------------------------------
# The pages
# ----------------------------------------------------------------------
def test_fleet_with_photographs_from_a_receiver(tmp_path, offline):
    r = fleet.fetch(
        {
            **RECEIVER,
            "pictures": "photos",
            "labels": [
                "type",
                "flag",
                "dest",
                "speed",
                "distance",
                "course",
                "length",
                "imo",
            ],
        },
        SETTINGS,
        ctx=_ctx(tmp_path),
    )
    assert (
        r["state"] == "ok"
        and r["widget"] == "fleet"
        and r["afloat"] == 4
        and r["shown"] == 4
    )
    assert (
        r["attribution"] == "positions from your receiver"
        and r["title"] == "Port Melbourne"
    )
    elba = next(v for v in r["vessels"] if v["imo"] == "9458054")
    assert (
        elba["pic"]["kind"] == "photo"
        and "A. Spotter" in elba["pic"]["credit"]
        and "Wikimedia Commons" in elba["pic"]["credit"]
    )
    assert elba["lines"][:3] == [
        "Cargo ship",
        "Denmark",
        "to AU MEL, ETA " + elba["eta"],
    ]
    assert (
        "366 m × 45 m" in elba["lines"]
        and "IMO 9458054" in elba["lines"]
        and "course 215°" in elba["lines"]
    )
    assert elba["about"].startswith(
        "The Maersk Elba is a cargo ship under the flag of Denmark, 366 metres long. She is under way using engine at 12.4 knots, bound for AU MEL"
    )
    anne = next(v for v in r["vessels"] if v["name"] == "Lady Anne")
    assert anne["pic"] is None and anne["sil"].endswith("sail.svg"), (
        "no IMO, no photograph, a silhouette"
    )
    aurora = next(v for v in r["vessels"] if v["name"] == "Nordic Aurora")
    assert aurora["lines"][2] == "to Geelong" and aurora["speed_text"] == "at anchor", (
        "a ship at anchor still has her destination"
    )
    assert any("A. Spotter" in c for c in r["credits"])
    assert "lat" not in elba and "photo" not in elba


def test_the_stream_warms_then_fills(tmp_path, offline, monkeypatch):
    cold = FakeListener(records=[], warming=True)
    monkeypatch.setattr(A, "listener_for", lambda key, box, data_dir, ua: cold)
    r = fleet.fetch(
        {**PORT_MELBOURNE, "pictures": "photos"}, SETTINGS, ctx=_ctx(tmp_path)
    )
    assert (
        r["state"] == "listening"
        and r["live_refresh_s"] == S.LISTEN_S
        and "Listening" in r["hint"]
    )
    # A cold listener asks the server to render again once a report cycle
    # has passed, so a panel does not sit on "listening" for its whole cadence.
    from datetime import datetime

    retry = datetime.fromisoformat(r["next_change_at"]).timestamp()
    assert 0 < retry - datetime.now().astimezone().timestamp() <= A.LISTEN_WARM_S + 15
    empty = FakeListener(records=[], warming=False)
    monkeypatch.setattr(A, "listener_for", lambda key, box, data_dir, ua: empty)
    r = fleet.fetch(
        {**PORT_MELBOURNE, "pictures": "photos"}, SETTINGS, ctx=_ctx(tmp_path)
    )
    assert r["state"] == "empty"
    down = FakeListener(records=[], warming=False, error="aisstream.io refused the key")
    monkeypatch.setattr(A, "listener_for", lambda key, box, data_dir, ua: down)
    r = fleet.fetch(
        {**PORT_MELBOURNE, "pictures": "photos"}, SETTINGS, ctx=_ctx(tmp_path)
    )
    assert r["state"] == "error" and "refused the key" in r["error"]
    r = fleet.fetch(
        {**PORT_MELBOURNE, "pictures": "photos"},
        {**SETTINGS, "aisstream_key": ""},
        ctx=_ctx(tmp_path),
    )
    assert r["state"] == "error" and "aisstream.io key" in r["error"]


def test_fleet_from_the_stream_with_filters(tmp_path, offline, stream):
    r = fleet.fetch(
        {
            **PORT_MELBOURNE,
            "pictures": "photos",
            "include_moored": False,
            "order": "largest",
        },
        SETTINGS,
        ctx=_ctx(tmp_path),
    )
    assert r["state"] == "ok" and r["attribution"] == "positions from aisstream.io"
    assert [v["name"] for v in r["vessels"]] == [
        "Maersk Elba",
        "Svitzer Eureka",
        "Lady Anne",
    ], "the anchored tanker left out, largest first"
    r = fleet.fetch(
        {**PORT_MELBOURNE, "pictures": "photos", "order": "fastest", "count": 2},
        SETTINGS,
        ctx=_ctx(tmp_path),
    )
    assert [v["name"] for v in r["vessels"]] == ["Maersk Elba", "Nordic Aurora"] and r[
        "afloat"
    ] == 4, (
        "photographed first: the anchored tanker with a photograph beats the tug without one"
    )
    r = fleet.fetch(
        {
            **PORT_MELBOURNE,
            "pictures": "photos",
            "order": "fastest",
            "count": 2,
            "ranking": "order",
        },
        SETTINGS,
        ctx=_ctx(tmp_path),
    )
    assert [v["name"] for v in r["vessels"]] == ["Maersk Elba", "Svitzer Eureka"], (
        "the order alone when asked"
    )
    r = fleet.fetch(
        {**PORT_MELBOURNE, "pictures": "photos", "radius_km": "5"},
        SETTINGS,
        ctx=_ctx(tmp_path),
    )
    assert [v["name"] for v in r["vessels"]] == [
        "Maersk Elba",
        "Svitzer Eureka",
        "Lady Anne",
    ], "photographed first, then the order"
    r = fleet.fetch(
        {**RECEIVER, "pictures": "photos", "ranking": "order"},
        SETTINGS,
        ctx=_ctx(tmp_path),
    )
    assert [v["name"] for v in r["vessels"]][:2] == ["Svitzer Eureka", "Maersk Elba"], (
        "the order alone when asked"
    )


def test_photo_plate_and_scene_pages(tmp_path, offline, stream):
    r = photo.fetch({**PORT_MELBOURNE, "strip": "2"}, SETTINGS, ctx=_ctx(tmp_path))
    assert r["state"] == "ok" and r["widget"] == "photo" and len(r["vessels"]) == 3
    assert r["vessels"][0]["shown_name"] == "Maersk Elba", (
        "the nearest photographed vessel leads the photo page"
    )
    r = photo.fetch(
        {**PORT_MELBOURNE, "strip": "2", "ranking": "order"},
        SETTINGS,
        ctx=_ctx(tmp_path),
    )
    assert r["vessels"][0]["shown_name"] == "Svitzer Eureka"
    r = plate.fetch(
        {
            **PORT_MELBOURNE,
            "pictures": "photos",
            "order": "largest",
            "look": "tiles",
            "colours": "type",
        },
        SETTINGS,
        ctx=_ctx(tmp_path),
    )
    assert (
        r["widget"] == "plate"
        and r["look"] == "tiles"
        and r["colours"] == "type"
        and len(r["vessels"]) == 1
    )
    v = r["vessels"][0]
    assert (
        v["shown_name"] == "Maersk Elba"
        and v["pic"]["kind"] == "photo"
        and v["dest_text"].startswith("to AU MEL, ETA")
    )
    r = scene.fetch(
        {**PORT_MELBOURNE, "pictures": "photos", "ranking": "order"},
        SETTINGS,
        ctx=_ctx(tmp_path),
    )
    assert (
        r["widget"] == "scene"
        and r["backdrop"] == "sea"
        and r["vessels"][0]["shown_name"] == "Svitzer Eureka"
    )
    r = fleet.fetch({}, SETTINGS, ctx=_ctx(tmp_path))
    assert r["state"] == "error" and "Set a place" in r["error"]


def test_paintings_from_photographs_and_from_particulars(tmp_path, offline, stream):
    prompts, _uas = offline
    r = fleet.fetch(
        {**PORT_MELBOURNE, "pictures": "paintings", "style": "linocut", "count": "4"},
        SETTINGS,
        ctx=_ctx(tmp_path),
    )
    assert r["state"] == "ok"
    _settle()
    assert len(prompts) == 4, "two from photographs, two from particulars"
    by_url = {p["_url"]: p for p in prompts}
    assert any("nano-banana/edit" in u for u in by_url) and any(
        u.rstrip("/").endswith("nano-banana") for u in by_url
    ), "an edit from the photograph, a picture from words for the rest"
    words = [p for p in prompts if not p.get("image_urls")]
    assert len(words) == 2 and all(
        "Lady Anne" in p["prompt"] or "Svitzer Eureka" in p["prompt"] for p in words
    )
    assert all(
        "linocut" in p["prompt"] and "pure white paper" in p["prompt"] for p in prompts
    )
    photographed = [p for p in prompts if p.get("image_urls")]
    assert all(p["image_urls"][0].startswith("data:image/") for p in photographed), (
        "the photograph is handed over inline"
    )
    assert any(
        "Maersk Elba" in p["prompt"] and "flag of Denmark" in p["prompt"]
        for p in photographed
    )
    r = fleet.fetch(
        {**PORT_MELBOURNE, "pictures": "paintings", "style": "linocut", "count": "4"},
        SETTINGS,
        ctx=_ctx(tmp_path),
    )
    assert all(v["pic"] and v["pic"]["kind"] == "painting" for v in r["vessels"])
    assert all(not v["pic"]["whole"] for v in r["vessels"]), "cut out"
    assert all(v["pic"]["impression"] == (not v["imo"]) for v in r["vessels"]), (
        "a vessel without a photograph is marked an impression"
    )
    assert any(
        "from her particulars" in v["pic"]["credit"] for v in r["vessels"]
    ) and any("Wikimedia Commons" in v["pic"]["credit"] for v in r["vessels"])
    assert len(prompts) == 4, "painted once; nothing asked again"
    keys = sorted(p.stem for p in P.gen_dir(tmp_path).glob("*.jpg"))
    assert any(k.startswith("9458054--linocut") for k in keys) and any(
        "--words" in k for k in keys
    )


def test_scene_live_backdrop_and_a_visitor(tmp_path, offline, stream):
    prompts, _uas = offline
    r = scene.fetch(
        {
            **PORT_MELBOURNE,
            "pictures": "paintings",
            "style": "poster",
            "backdrop": "live",
            "order": "largest",
            "visitor": 100,
            "visitors": ["kraken"],
        },
        SETTINGS,
        ctx=_ctx(tmp_path),
    )
    assert r["state"] == "ok" and r["sea"] == {
        "time": r["sea"]["time"],
        "weather": "rain",
    }
    _settle()
    assert len(prompts) == 2
    sea = next(p for p in prompts if "Maersk" in p["prompt"])
    assert "rain on the water" in sea["prompt"] and "filling the frame" in sea["prompt"]
    kraken = next(p for p in prompts if "kraken" in p["prompt"])
    assert (
        "creature of legend" in kraken["prompt"]
        and "pure white paper" in kraken["prompt"]
        and not kraken.get("image_urls")
    )
    r = scene.fetch(
        {
            **PORT_MELBOURNE,
            "pictures": "paintings",
            "style": "poster",
            "backdrop": "live",
            "order": "largest",
            "visitor": 100,
            "visitors": ["kraken"],
        },
        SETTINGS,
        ctx=_ctx(tmp_path),
    )
    assert (
        r["vessels"][0]["pic"]["whole"]
        and r["visitor"]["typ"] == "Kraken"
        and r["visitor"]["pic"]
    )
    keys = [p.stem for p in P.gen_dir(tmp_path).glob("*.jpg")]
    assert any("--bd_" in k for k in keys) and any(
        k.startswith("visitor_kraken--poster") for k in keys
    )


def test_only_painted_and_no_key(tmp_path, offline, stream):
    r = plate.fetch(
        {**PORT_MELBOURNE, "pictures": "paintings", "unpainted": "skip"},
        SETTINGS,
        ctx=_ctx(tmp_path),
    )
    assert r["state"] == "painting" and "Painting" in r["hint"]
    _settle()
    r = plate.fetch(
        {**PORT_MELBOURNE, "pictures": "paintings", "unpainted": "skip"},
        SETTINGS,
        ctx=_ctx(tmp_path),
    )
    assert r["state"] == "ok" and r["vessels"][0]["pic"]["kind"] == "painting"
    r = plate.fetch(
        {
            **PORT_MELBOURNE,
            "pictures": "paintings",
            "style": "pencil",
            "order": "largest",
        },
        {**SETTINGS, "fal_api_key": ""},
        ctx=_ctx(tmp_path, home_lat=-37.84, home_lon=144.92),
    )
    assert r["state"] == "ok" and r["vessels"][0]["pic"]["kind"] == "photo", (
        "without a key the photograph shows"
    )
    assert any("fal.ai key" in n for n in r["notices"])


def test_a_slow_lookup_keeps_to_the_budget(tmp_path, offline, stream, monkeypatch):
    real = N.http

    def slow(url, token="", accept="application/json", **kw):
        if "commons.wikimedia.org" in url:
            time.sleep(1.5)
        return real(url, token, accept, **kw)

    monkeypatch.setattr(N, "http", slow)
    monkeypatch.setattr(S, "BUDGET_S", 0.8)
    t0 = time.time()
    r = fleet.fetch(
        {**PORT_MELBOURNE, "pictures": "photos"}, SETTINGS, ctx=_ctx(tmp_path)
    )
    assert (
        time.time() - t0 < 3.0
        and r["state"] == "ok"
        and any("on the way" in s for s in r["status"])
        and r["live_refresh_s"] > 0
    )
    time.sleep(4.0)  # both Commons calls, slow, finish in the background and are cached
    r = fleet.fetch(
        {**PORT_MELBOURNE, "pictures": "photos"}, SETTINGS, ctx=_ctx(tmp_path)
    )
    assert not any("on the way" in s for s in r["status"])


def test_core_and_prompt_pieces(tmp_path):
    assert core.settings_of(None) == {}
    assert P.key_for("9458054", "poster") == "9458054--poster--p1"
    assert (
        P.key_for(
            "9458054", "poster", "sunset", "quarter", "flux_kontext", fidelity="free"
        )
        == "9458054--poster--p1--free--bd_sunset--v_quarter--m_flux_kontext"
    )
    assert (
        P.key_for("503999999", "poster", photo=False, view="stern")
        == "503999999--poster--p1--words2--v_stern"
    )
    how = P.build_how(
        {
            "build_medium": "woodblock",
            "build_period": "dutch",
            "build_mood": "heroic",
            "build_extra": "a gull overhead",
        }
    )
    assert how.startswith(
        "a woodblock print of the {kind}, in the manner of a Dutch Golden Age marine painting"
    ) and how.endswith("a gull overhead")
    text = P.prompt_for(
        {
            "style": "engraving",
            "typ": "Tanker",
            "name": "Nordic Aurora",
            "flag": "Marshall Islands",
            "photo": "https://x/y.jpg",
            "fidelity": "free",
            "view": "stern",
        }
    )
    assert (
        "black, white and grey only" in text
        and "stern quarter" in text
        and "flag of Marshall Islands" in text
    )
    text = P.prompt_for(
        {
            "style": "bottle",
            "typ": "Tug",
            "about": "a tug",
            "name": "Svitzer Eureka",
            "flag": "Australia",
            "len": 32,
        }
    )
    assert (
        "filling the frame" in text
        and "about 32 metres long" in text
        and "pure white paper" not in text
    ), "a style with its own ground is never cut out"
    assert P.monster_choices("story") and P.visitors_of(["nope"]) == P.monster_choices(
        "myth"
    )


def test_the_hosts_commons_lookup_is_used_when_there(tmp_path, offline, monkeypatch):
    """On a host with app.commons the photograph comes from it, in the widget's shape."""
    from app import commons as host_commons

    monkeypatch.setattr(A, "commons", host_commons)
    asked = []

    def fake_portrait(cat, *, name="", ident="", **kw):
        asked.append((cat, name, ident, kw.get("descend")))
        return {
            "title": "File:Maersk Elba IMO 9458054.jpg",
            "src": "https://upload.wikimedia.org/elba_wide.jpg",
            "link": "https://commons.wikimedia.org/wiki/File:X.jpg",
            "by": "A. Spotter",
            "lic": "CC BY-SA 4.0",
            "w": 1800,
            "h": 1200,
        }

    monkeypatch.setattr(host_commons, "portrait", fake_portrait)
    p = A.photo_of("9458054", tmp_path, "ua", "Maersk Elba")
    assert (
        asked == [("IMO 9458054", "Maersk Elba", "9458054", "(ship")]
        and p["by"] == "A. Spotter"
        and p["w"] == "1800"
    )
    assert not (tmp_path / "photos").exists(), (
        "nothing kept by the widget; the host keeps it"
    )


# ----------------------------------------------------------------------
# Openverse, the ranking and the words a vessel is painted from
# ----------------------------------------------------------------------
MORE_SETTINGS = {
    **SETTINGS,
    "photo_licences": "nc",
    "fleet_notes": "# my regulars\nSvitzer *: dark blue hull, white wheelhouse, a red band on the funnel\nLADY ANNE: a white ketch with tan sails\n",
}


def test_openverse_photographs_for_the_vessels_commons_lacks(tmp_path, offline, stream):
    prompts, _uas = offline
    r = fleet.fetch(
        {**PORT_MELBOURNE, "pictures": "photos", "include_moored": "true"},
        MORE_SETTINGS,
        ctx=_ctx(tmp_path),
    )
    by = {v["name"]: v for v in r["vessels"]}
    assert by["Maersk Elba"]["pic"]["credit"].endswith(
        "(Wikimedia Commons, CC BY-SA 4.0)"
    ), "Commons first"
    tug = by["Svitzer Eureka"]["pic"]
    assert (
        tug
        and tug["kind"] == "photo"
        and tug["credit"] == "photo by Port Spotter (Flickr, CC BY-NC 2.0)"
        and tug["link"] == "https://www.flickr.com/photos/11@N02/501/"
    )
    tanker = A.openverse_photo("9312345", "Nordic Aurora", tmp_path / "f", "ua")
    assert (
        tanker["by"] == "Tanker Watch"
        and tanker["lic"] == "CC BY-SA 4.0"
        and tanker["site"] == "Wikimedia Commons"
    ), "by IMO number, for a ship Commons has no category for"
    assert by["Lady Anne"]["pic"] is None and not any(
        q["q"] == '"Lady Anne"' for q in prompts.flickr
    ), "a yacht is never looked up by name: another Lady Anne is the likelier find"
    assert (
        A.openverse_photo("", "Lady Anne", tmp_path / "la", "ua", strict=False)["by"]
        == "A. Painter"
    ), "a commercial vessel's name is taken at its word"
    assert all(
        q["license_type"] == "modification" and "by-nd" not in q["license"]
        for q in prompts.flickr
    ), "never the ND licences"
    assert any(q["q"] == "IMO 9312345" for q in prompts.flickr) and any(
        q["q"] == '"Svitzer Eureka"' for q in prompts.flickr
    )
    n = len(prompts.flickr)
    fleet.fetch(
        {**PORT_MELBOURNE, "pictures": "photos"}, MORE_SETTINGS, ctx=_ctx(tmp_path)
    )
    assert len(prompts.flickr) == n, "kept on disk; asked once"
    assert A.openverse_photo("", "SVITZER EUREKA", tmp_path, "ua", nc=False) == {}, (
        "open licences only: the BY-NC photo is passed over"
    )
    assert A.openverse_photo("", "Tug", tmp_path, "ua") == {} and not A.distinctive(
        "Tug"
    ), "a short, plain name is never searched"
    N.write(
        A._openverse_wait_file(tmp_path / "w"),
        json.dumps({"until": time.time() + 60}).encode(),
    )
    assert A.openverse_photo("", "Svitzer Eureka", tmp_path / "w", "ua") == {}
    r = fleet.fetch(
        {**PORT_MELBOURNE, "pictures": "photos"},
        MORE_SETTINGS,
        ctx=_ctx(tmp_path / "w"),
    )
    assert any("Openverse" in x for x in r["notices"]), (
        "the allowance used up is said on the page"
    )
    r = fleet.fetch(
        {**PORT_MELBOURNE, "pictures": "photos"}, SETTINGS, ctx=_ctx(tmp_path / "c")
    )
    assert {v["name"] for v in r["vessels"] if v["pic"]} == {
        "Maersk Elba",
        "Nordic Aurora",
    }, "Commons alone when the setting says so"


def test_photographed_first_and_the_words_she_is_painted_from(
    tmp_path, offline, stream
):
    prompts, _uas = offline
    r = plate.fetch(
        {**PORT_MELBOURNE, "pictures": "paintings", "style": "linocut"},
        SETTINGS,
        ctx=_ctx(tmp_path),
    )
    assert r["vessels"][0]["shown_name"] == "Maersk Elba", (
        "the nearest photographed vessel, not the nearest tug"
    )
    r = fleet.fetch(
        {
            **PORT_MELBOURNE,
            "pictures": "paintings",
            "style": "linocut",
            "count": "4",
            "include_moored": "false",
        },
        MORE_SETTINGS | {"photo_licences": "commons"},
        ctx=_ctx(tmp_path),
    )
    _settle()
    tug = next(p for p in prompts if "Svitzer Eureka" in p["prompt"])
    assert (
        "harbour tug" in tug["prompt"]
        and "dark blue hull, white wheelhouse, a red band on the funnel"
        in tug["prompt"]
    ), "the fleet note, over the livery table"
    assert (
        "She is about 32 metres long and 12 across, under way at 6 knots with a wake behind her."
        in tug["prompt"]
    )
    assert (
        "a white ketch with tan sails"
        in next(p for p in prompts if "Lady Anne" in p["prompt"])["prompt"]
    )
    assert not any("staticflickr" in str(p.get("image_urls")) for p in prompts)
    keys = sorted(p.stem for p in P.gen_dir(tmp_path).glob("*.jpg"))
    assert any("--words2--d_" in k for k in keys), (
        "the words are in the key: a changed note repaints"
    )
    assert P.livery_for("MAERSK ELBA") == (
        "in Maersk's livery: a light blue hull, white superstructure, a light blue funnel with a white seven-pointed star",
        "container ship",
    )
    assert P.livery_for("SPIRIT OF TASMANIA IV")[
        1
    ] == "passenger and vehicle ferry" and P.livery_for("Unknown Boat") == ("", "")
    notes = P.parse_notes("Svitzer *: blue\nqueenscliff: the pilot launch\nbad line\n")
    assert (
        P.note_for("SVITZER MARYSVILLE", notes) == "blue"
        and P.note_for("Queenscliff", notes) == "the pilot launch"
        and P.note_for("Queenscliffe Two", notes) == ""
    )
    words = P.prompt_for(
        {
            "name": "ANL WARRNAMBOOL",
            "typ": "Cargo ship",
            "cls": "cargo",
            "len": 294,
            "beam": 32,
            "draught": 12.5,
            "status": "at anchor",
            "dest": "AU MEL",
            "flag": "Liberia",
            "style": "poster",
            "trade": "container ship",
            "words": "in ANL's livery",
        }
    )
    assert (
        words.startswith(
            "Draw a container ship, the ANL WARRNAMBOOL under the flag of Liberia, a large, Panamax-sized one, as"
        )
        and "in ANL's livery" in words
        and "lying at anchor, still, bound for AU MEL" in words
    )


def test_the_watch_keeps_each_vessel_at_her_closest(tmp_path):
    w = W.Watch("k", lambda: [], 9999, tmp_path / "w.json", lambda r: r["mmsi"])
    t = time.time() - 600
    try:
        w.note(
            [
                {"mmsi": "A", "km": 5.0, "dir": 10, "name": ""},
                {"mmsi": "B", "km": 3.0, "dir": 90, "name": "B"},
            ],
            t + 10,
        )
        w.note([{"mmsi": "A", "km": 2.0, "dir": 40, "name": "Anna"}], t + 20)
        w.note([{"mmsi": "B", "km": 4.0, "dir": 95, "name": "B", "imo": "123"}], t + 30)
        got = {r["mmsi"]: r for r in w.since(t + 15, t + 40)}
        assert set(got) == {"A", "B"}, "both seen since 15: B's last sighting is at 30"
        assert (
            got["A"]["km"] == 2.0
            and got["A"]["dir"] == 40
            and got["A"]["closest_at"] == t + 20
            and got["A"]["name"] == "Anna"
        ), "kept at her closest, as she then was"
        assert (
            got["B"]["km"] == 3.0
            and got["B"]["closest_at"] == t + 10
            and got["B"]["seen_last"] == t + 30
            and got["B"]["imo"] == "123"
        ), "a farther sighting keeps the closest row and fills in what she said since"
        assert [r["mmsi"] for r in w.since(t + 25, t + 40)] == ["B"]
        assert w.since(t + 31, t + 40) == []
        w.save()
    finally:
        w.stop.set()
    again = W.Watch("k", lambda: [], 9999, tmp_path / "w.json", lambda r: r["mmsi"])
    try:
        assert {r["mmsi"] for r in again.since(0)} == {"A", "B"}, (
            "remembered across a restart"
        )
    finally:
        again.stop.set()


def test_the_windows_chain_and_previews_do_not_move_them(tmp_path):
    assert W.window(tmp_path, "c", 10000, True) == 10000 - W.FIRST_WINDOW_S, (
        "a first render shows the last hour"
    )
    assert W.window(tmp_path, "c", 10100, False) == 10000 - W.FIRST_WINDOW_S, (
        "a preview shows the same window"
    )
    assert W.window(tmp_path, "c", 10100, True) == 10000 - W.FIRST_WINDOW_S, (
        "a render close on the last shares its window"
    )
    assert W.window(tmp_path, "c", 10000 + W.MIN_WINDOW_S, True) == 10000, (
        "the next window starts where the last advance was made"
    )
    assert W.window(tmp_path, "c", 10000 + W.MIN_WINDOW_S + 60, True) == 10000
    assert (
        W.window(tmp_path, "c", 10000 + 2 * W.MIN_WINDOW_S, True)
        == 10000 + W.MIN_WINDOW_S
    )
    assert W.window(tmp_path, "other", 10000, False) == 10000 - W.FIRST_WINDOW_S, (
        "cells have windows of their own"
    )


def test_everything_since_the_last_render(tmp_path, offline, stream, monkeypatch):
    opts = {
        **PORT_MELBOURNE,
        "pictures": "photos",
        "period": "since",
        "ranking": "order",
        "labels": ["type", "distance", "seen"],
    }
    r = fleet.fetch(opts, SETTINGS, ctx=_ctx(tmp_path))
    assert r["state"] == "ok" and r["period"].startswith("since ") and r["afloat"] == 4
    assert r["status"][0].startswith("4 seen since ") and r["status"][0].endswith(
        ", 4 within reach now"
    )
    assert [v["name"] for v in r["vessels"]] == [
        "Svitzer Eureka",
        "Maersk Elba",
        "Lady Anne",
        "Nordic Aurora",
    ]
    tug = r["vessels"][0]
    assert (
        tug["lines"][1].startswith("closest 0.")
        and " at " in tug["lines"][1]
        and tug["lines"][2].startswith("within reach since ")
    )
    assert tug["present"] is True
    # the tug sails out of reach: gone from the stream, she stays on the page at her closest approach
    stream.records = [v for v in stream.records if v["mmsi"] != "503012345"]
    r = fleet.fetch(opts, SETTINGS, ctx=_ctx(tmp_path))
    assert (
        r["afloat"] == 4 and [v["name"] for v in r["vessels"]][0] == "Svitzer Eureka"
    ), "seen since the window began, still on the page"
    # a page of the moment does not see her
    r = fleet.fetch({**opts, "period": "now"}, SETTINGS, ctx=_ctx(tmp_path))
    assert (
        "Svitzer Eureka" not in [v["name"] for v in r["vessels"]]
        and r["period"] == "on the water now"
    )
    # once the mark moves on past her last sighting, she is off the next page
    monkeypatch.setattr(W, "MIN_WINDOW_S", 0)
    w = next(iter(W._WATCHES.values()))
    with w.lock:
        w.seen["503012345"]["last"] -= 120
    marks = N.read_json(tmp_path / "watch" / "marks.json", {})
    for m in marks.values():
        m["marked"] = time.time() - 60
    N.write(tmp_path / "watch" / "marks.json", json.dumps(marks).encode())
    r = fleet.fetch(opts, SETTINGS, ctx=_ctx(tmp_path))
    assert (
        "Svitzer Eureka" not in [v["name"] for v in r["vessels"]] and r["afloat"] == 3
    )


def test_only_vessels_with_a_photograph_are_painted(tmp_path, offline, stream):
    prompts, _uas = offline
    opts = {
        **PORT_MELBOURNE,
        "pictures": "paintings",
        "style": "linocut",
        "count": "4",
        "paint": "photo",
    }
    r = fleet.fetch(opts, SETTINGS, ctx=_ctx(tmp_path))
    _settle()
    assert len(prompts) == 2 and all(p.get("image_urls") for p in prompts), (
        "the two with a photograph, nothing from particulars"
    )
    assert "2 without a photograph, left unpainted" in r["status"]
    r = fleet.fetch(opts, SETTINGS, ctx=_ctx(tmp_path))
    assert [bool(v["pic"]) for v in r["vessels"]] == [True, True, False, False], (
        "photographed first and painted; the rest silhouettes"
    )
    assert len(prompts) == 2


def test_a_style_nano_banana_cannot_make_paints_with_gpt_image(
    tmp_path, offline, stream
):
    prompts, _uas = offline
    style = next(iter(P.STYLE_MODEL))
    opts = {
        **PORT_MELBOURNE,
        "pictures": "paintings",
        "style": style,
        "count": "4",
        "paint": "photo",
    }
    fleet.fetch(opts, SETTINGS, ctx=_ctx(tmp_path))
    _settle()
    assert prompts and all("gpt-image" in p["_url"] for p in prompts), [
        p["_url"] for p in prompts
    ]
    # keyed by the cell's own model, so a painting kept from before still shows
    keys = [f.stem for f in P.gen_dir(tmp_path).glob("*.jpg")]
    assert any(k == f"9458054--{style}--p{P.PROMPT_VERSION}" for k in keys), keys
    assert not any("m_gpt_image" in k for k in keys)


def test_the_catalogue_counts_passes(tmp_path, offline):
    SG = S.SG
    a, b = (
        {
            "imo": "9458054",
            "mmsi": "219018271",
            "name": "Maersk Elba",
            "typ": "Cargo ship",
        },
        {"imo": "", "mmsi": "503012345", "name": "Svitzer Eureka", "typ": "Tug"},
    )
    led = SG.ledger(tmp_path / "unit")
    led.note([a, b], S.SIGHT_ID, S.SIGHT_NAME, now=1000)
    led.note([a], S.SIGHT_ID, S.SIGHT_NAME, now=1600)
    assert led.seen[S.SIGHT_ID(a)]["v"] == 1, (
        "seen again within half an hour is the same pass"
    )
    led.note([a], S.SIGHT_ID, S.SIGHT_NAME, now=4000)
    st = SG.stats(tmp_path / "unit", lambda rid: rid == S.SIGHT_ID(a), now=4000)
    assert (st["airframes"], st["passes"], st["once"], st["twice"], st["painted"]) == (
        2,
        3,
        1,
        1,
        1,
    )
    assert (
        st["painted_passes_share"] == round(2 / 3, 3)
        and st["coverage"] == round(1 - 1 / 3, 3)
        and st["estimate"] == 2
    )
    assert st["top"][0]["passes"] == 2 and st["top"][0]["painted"] is True
    led.save(now=4000)
    again = SG.Ledger(tmp_path / "unit" / SG.FILE)
    assert again.seen[S.SIGHT_ID(a)]["v"] == 2, "kept across a restart"
    # a render counts what it saw, and the paintings page reads it
    fleet.fetch({**RECEIVER, "pictures": "photos"}, SETTINGS, ctx=_ctx(tmp_path))
    st = core.sightings_context(tmp_path)["s"]
    assert st["airframes"] >= 1 and st["passes"] >= 1 and st["painted"] == 0


def test_a_spent_budget_fills_the_fleet_from_the_collection(tmp_path, offline):
    prompts = offline[0]
    kept = {"9000101": 5, "9000102": 1, "9000103": 2}
    for imo in kept:
        P.ART.keep(
            P.key_for(imo, "poster"),
            tmp_path,
            _jpeg(paper=(252, 250, 246)),
            {
                "imo": imo,
                "mmsi": f"5030{imo[-3:]}",
                "name": f"Kept {imo[-1]}",
                "typ": "Cargo ship",
                "flag": "Australia",
                "len": 180,
                "style": "poster",
                "backdrop": "none",
                "credit": f"painted from IMO {imo}",
            },
        )
    P.ART.keep(  # another style is not this page's
        P.key_for("9000104", "linocut"),
        tmp_path,
        _jpeg(paper=(252, 250, 246)),
        {"imo": "9000104", "typ": "Tug", "style": "linocut", "backdrop": "none"},
    )
    P.ART.keep(  # nor is a whole picture on a backdrop: the fleet cuts out
        P.key_for("9000105", "poster", "sea"),
        tmp_path,
        _jpeg(paper=(252, 250, 246)),
        {"imo": "9000105", "typ": "Tug", "style": "poster", "backdrop": "sea"},
    )
    led = S.SG.ledger(tmp_path)
    for imo, passes in kept.items():
        for i in range(passes):
            led.note(
                [{"imo": imo, "name": f"Kept {imo[-1]}", "typ": "Cargo ship"}],
                S.SIGHT_ID,
                S.SIGHT_NAME,
                now=1000 + i * 4000,
            )
    P.ART.spend(tmp_path, 100)
    options = {
        **RECEIVER,
        "pictures": "paintings",
        "style": "poster",
        "count": "4",
        "labels": ["type", "length", "imo"],
        "when_spent": "rare",
    }
    r = fleet.fetch(options, SETTINGS, ctx=_ctx(tmp_path))
    assert not prompts, "nothing is painted once the budget is spent"
    vs = r["vessels"]
    assert [v["imo"] for v in vs[:3]] == ["9000102", "9000103", "9000101"], (
        "the rarest first, every one cut out"
    )
    assert all(v["pic"]["kind"] == "painting" and not v["pic"]["whole"] for v in vs[:3])
    assert all(
        v["kept"] and v["cls"] == "cargo" and v["len"] == 180 and v["shown_name"]
        for v in vs[:3]
    ), "everything the fleet page reads"
    assert len({v["mmsi"] for v in vs[:3]}) == 3
    assert vs[0]["lines"][:3] == ["Cargo ship", "180 m", "IMO 9000102"]
    assert vs[0]["lines"][-1].startswith("seen once") and vs[2]["lines"][-1].startswith(
        "seen 5 times"
    )
    assert len(vs) == 4 and vs[3]["pic"] is None and not vs[3].get("kept"), (
        "a gap the collection could not fill stays"
    )
    assert (
        r["period"] == "from the collection"
        and "painted from IMO 9000102" in (r["credits"])
    )
    assert any("from the collection" in s for s in r["status"])
    # at random: the same three for the hour, in an order of their own
    a = fleet.fetch({**options, "when_spent": "random"}, SETTINGS, ctx=_ctx(tmp_path))
    b = fleet.fetch({**options, "when_spent": "random"}, SETTINGS, ctx=_ctx(tmp_path))
    assert [x["shown_name"] for x in a["vessels"]] == [
        x["shown_name"] for x in b["vessels"]
    ]
    assert sorted(x["imo"] for x in a["vessels"][:3]) == sorted(kept)
    # left alone, the page is as it was: what is passing, unpainted
    r = fleet.fetch({**options, "when_spent": "keep"}, SETTINGS, ctx=_ctx(tmp_path))
    assert (
        not any(v.get("kept") for v in r["vessels"])
        and r["period"] == "on the water now"
    )


def test_listener_outlives_a_slow_panel(tmp_path, monkeypatch):
    """A panel waking every half hour used to find the stream gone (20 min
    idle) and start a cold one every time, so a quiet port never showed a
    ship. The idle limit now stretches to twice the longest gap between asks."""
    monkeypatch.setattr(A.Listener, "_run", lambda self: None)
    lst = A.Listener("key", [[0, 0], [1, 1]], tmp_path / "l.json", "ua")
    assert lst.idle_limit_s == A.LISTEN_IDLE_S
    t = [1_000_000.0]
    monkeypatch.setattr(A.time, "time", lambda: t[0])
    lst.asked = t[0]
    t[0] += 1800
    lst.ask()
    assert lst.gap == 1800 and lst.idle_limit_s == 3600
    t[0] += 60
    lst.ask()
    assert lst.gap == 1800
    lst._save()
    again = A.Listener("key", [[0, 0], [1, 1]], tmp_path / "l.json", "ua")
    assert again.gap == 1800 and again.idle_limit_s == 3600
    t[0] += 10 * 86400
    lst.ask()
    assert lst.idle_limit_s == A.LISTEN_IDLE_MAX_S


_OW = {
    "type": "FeatureCollection",
    "attribution": {"aishub": "Open Waters AIS. AISHub"},
    "features": [
        {
            "type": "Feature",
            "id": 563209400,
            "geometry": {"type": "Point", "coordinates": [138.2852, -34.8154]},
            "properties": {
                "mmsi": 563209400,
                "name": "FIRANDO",
                "callsign": "9V7827",
                "imo": 9965772,
                "type": 70,
                "sog": 0,
                "cog": 130.5,
                "heading": 20,
                "nav_status": 1,
                "destination": "AU ADL",
                "eta": "10-27 15:30",
                "draught": 7,
                "length": 229,
                "beam": 32,
                "flag": "SG",
                "seen": "2026-10-28T00:44:50Z",
                "source": "aishub",
            },
        },
        {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [138.50, -34.80]},
            "properties": {
                "mmsi": 503144550,
                "name": "MALUKA",
                "type": 36,
                "sog": 0,
                "to_bow": 6,
                "to_stern": 5,
                "to_port": 3,
                "to_starboard": 0,
                "flag": "AU",
                "source": "aisstream",
            },
        },
        {"type": "Feature", "geometry": None, "properties": {"mmsi": 1}},
    ],
}


def test_openwaters_rows_take_the_feature_shape():
    rows = A._openwaters_rows(_OW)
    assert [r["mmsi"] for r in rows] == ["563209400", "503144550"]
    f = rows[0]
    assert f["lat"] == -34.8154 and f["lon"] == 138.2852
    assert (
        f["len"] == 229
        and f["beam"] == 32
        and f["cc"] == "SG"
        and f["imo"] == "9965772"
    )
    assert f["status"] == 1 and f["dest"] == "AU ADL" and f["eta"]
    assert abs(f["at"] - 1793148290.0) < 1
    assert rows[1]["len"] == 11 and rows[1]["beam"] == 3
    assert A.openwaters_feed(rows) == "Open Waters AIS (aishub, aisstream)"


def test_nearby_openwaters_asks_once_per_render_and_keeps_the_last_answer(
    tmp_path, monkeypatch
):
    calls = []

    def fake_get_json(url, ua="", timeout=0, **kw):
        calls.append(url)
        return (_OW, None) if len(calls) == 1 else (None, "unreachable")

    monkeypatch.setattr(A.N, "get_json", fake_get_json)
    rows, err, feed, warming = A.nearby(
        "openwaters", "", "", -34.93, 138.59, 40, tmp_path, "ua"
    )
    assert err is None and not warming and feed.startswith("Open Waters AIS")
    assert [r["name"] for r in rows] == ["Maluka", "Firando"]
    assert "bbox=" in calls[0] and "max_age=30m" in calls[0]
    # A second render inside LIVE_S reads the cache; after that the stale answer
    # stands in when the service is down.
    rows2, *_ = A.nearby("openwaters", "", "", -34.93, 138.59, 40, tmp_path, "ua")
    assert len(calls) == 1 and len(rows2) == 2
    monkeypatch.setattr(A, "LIVE_S", 0)
    rows3, err3, *_ = A.nearby("openwaters", "", "", -34.93, 138.59, 40, tmp_path, "ua")
    assert len(calls) == 2 and err3 is None and len(rows3) == 2
    # Nothing cached and the service down: an error, not an empty sea.
    rows4, err4, *_ = A.nearby("openwaters", "", "", -20.0, 150.0, 40, tmp_path, "ua")
    assert rows4 == [] and "Open Waters AIS could not be reached" in err4


def test_openwaters_is_the_default_source_and_the_manifest_offers_it():
    m = json.loads(
        (ROOT / "underway_fleet" / "plugin.json").read_text(encoding="utf-8")
    )
    src = next(o for o in m["cell_options"] if o["name"] == "source")
    assert src["default"] == "openwaters"
    assert [c["value"] for c in src["choices"]] == [
        "openwaters",
        "aisstream",
        "receiver",
    ]
