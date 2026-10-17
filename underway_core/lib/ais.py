"""What is on the water: the vessels near a place from aisstream.io (a key,
free) or a receiver of your own (AIS-catcher's /api/ships.json), each with
its type, flag, destination and ETA from its own AIS messages and a
photograph of the very ship from Wikimedia Commons by its IMO number.
Loaded by path.

aisstream.io is a stream, not a request: a listener thread keeps one
connection open per place and keeps the vessels it hears in memory and on
disk; a fetch reads what the listener has. The listener stops when no page
has asked for a while, so an idle dashboard holds no connection."""

from __future__ import annotations

import contextlib
import html
import importlib.util
import json
import math
import re
import sys
import threading
import time
import urllib.parse
from datetime import datetime
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
WS = _sibling("ws")

AISSTREAM = "wss://stream.aisstream.io/v0/stream"
COMMONS = "https://commons.wikimedia.org/w/api.php"
OPEN_METEO = "https://api.open-meteo.com/v1/forecast?latitude={lat:.3f}&longitude={lon:.3f}&current=weather_code,cloud_cover,is_day,wind_speed_10m&daily=sunrise,sunset&timezone=auto&forecast_days=1"
LIVE_S = 15  # a receiver is asked at most this often
STALE_S = 30 * 60  # a vessel not heard for this long has gone
STATIC_S = 30 * 86400  # what a vessel said of itself is kept this long
PHOTO_S = 30 * 86400
WEATHER_S = 15 * 60
LISTEN_IDLE_S = 20 * 60  # a listener no page has asked for stops after this
LISTEN_SAVE_S = 10
LISTEN_WARM_S = 25  # a fresh listener is given this long before an empty sea counts as empty
KM_NM = 1.852


def user_agent(contact: str) -> str:
    c = " ".join(str(contact or "").split())
    return f"tesserae-underway/0.1 (+https://github.com/dmellok/tesserae-widget-underway{'; ' + c if c else ''})"


# ----------------------------------------------------------------------
# Ship types: the AIS type code to a label and a class for the silhouette
# ----------------------------------------------------------------------
CLASSES = ("cargo", "tanker", "passenger", "tug", "fishing", "sail", "pleasure", "service", "naval", "other")
CLASS_ABOUT = {
    "cargo": "a cargo ship",
    "tanker": "a tanker",
    "passenger": "a passenger ship",
    "tug": "a tug",
    "fishing": "a fishing vessel",
    "sail": "a sailing vessel",
    "pleasure": "a pleasure craft",
    "service": "a working boat",
    "naval": "a naval vessel",
    "other": "a vessel",
}
CLASS_LEN = {"cargo": 180.0, "tanker": 200.0, "passenger": 200.0, "tug": 30.0, "fishing": 25.0, "sail": 15.0, "pleasure": 12.0, "service": 25.0, "naval": 100.0, "other": 40.0}
_TYPES: dict[int, tuple[str, str]] = {
    30: ("Fishing vessel", "fishing"), 31: ("Towing vessel", "tug"), 32: ("Towing vessel", "tug"), 33: ("Dredger", "service"),
    34: ("Diving support vessel", "service"), 35: ("Military vessel", "naval"), 36: ("Sailing vessel", "sail"), 37: ("Pleasure craft", "pleasure"),
    50: ("Pilot vessel", "service"), 51: ("Search and rescue vessel", "service"), 52: ("Tug", "tug"), 53: ("Port tender", "service"),
    54: ("Anti-pollution vessel", "service"), 55: ("Law enforcement vessel", "service"), 56: ("Spare vessel", "service"), 57: ("Spare vessel", "service"),
    58: ("Medical transport", "service"), 59: ("Non-combatant ship", "naval"),
}
_RANGES = (
    (20, 29, "Wing-in-ground craft", "other"), (40, 49, "High-speed craft", "passenger"), (60, 69, "Passenger ship", "passenger"),
    (70, 79, "Cargo ship", "cargo"), (80, 89, "Tanker", "tanker"), (90, 99, "Vessel", "other"),
)
HAZARD = {1: " carrying hazardous cargo", 2: " carrying hazardous cargo", 3: " carrying hazardous cargo"}


def type_of(code: Any) -> tuple[str, str, int]:
    """(label, class, code) for an AIS ship type code."""
    try:
        n = int(code or 0)
    except (TypeError, ValueError):
        n = 0
    if n in _TYPES:
        return (*_TYPES[n], n)
    for lo, hi, label, cls in _RANGES:
        if lo <= n <= hi:
            return (label, cls, n)
    return ("Vessel", "other", n)


STATUS = {
    0: "under way using engine", 1: "at anchor", 2: "not under command", 3: "restricted in manoeuvrability", 4: "constrained by her draught",
    5: "moored", 6: "aground", 7: "engaged in fishing", 8: "under way sailing", 11: "towing astern", 12: "pushing ahead", 14: "AIS-SART",
}
MOVING = {0, 7, 8, 11, 12}


def status_of(code: Any, sog: float) -> tuple[str, bool]:
    """(words, moving) for a navigational status; speed decides where the status says nothing."""
    try:
        n = int(code)
    except (TypeError, ValueError):
        n = 15
    if n in STATUS:
        # moored, anchored or aground is still whatever the speed says; otherwise the speed decides
        return STATUS[n], n not in (1, 5, 6) and (sog >= 0.5 or (sog < 0 and n in MOVING))
    return ("under way" if sog >= 0.5 else "stopped"), sog >= 0.5


# ----------------------------------------------------------------------
# Flags: the MMSI's first three digits (the MID) to a country, and the two-letter
# codes a receiver gives. Enough for what passes most coasts.
# ----------------------------------------------------------------------
MID: dict[int, tuple[str, str]] = {
    201: ("AL", "Albania"), 202: ("AD", "Andorra"), 203: ("AT", "Austria"), 204: ("PT", "Portugal"), 205: ("BE", "Belgium"), 206: ("BY", "Belarus"), 207: ("BG", "Bulgaria"),
    208: ("VA", "Vatican"), 209: ("CY", "Cyprus"), 210: ("CY", "Cyprus"), 211: ("DE", "Germany"), 212: ("CY", "Cyprus"), 213: ("GE", "Georgia"), 214: ("MD", "Moldova"),
    215: ("MT", "Malta"), 216: ("AM", "Armenia"), 218: ("DE", "Germany"), 219: ("DK", "Denmark"), 220: ("DK", "Denmark"), 224: ("ES", "Spain"), 225: ("ES", "Spain"),
    226: ("FR", "France"), 227: ("FR", "France"), 228: ("FR", "France"), 229: ("MT", "Malta"), 230: ("FI", "Finland"), 231: ("FO", "Faroe Islands"), 232: ("GB", "United Kingdom"),
    233: ("GB", "United Kingdom"), 234: ("GB", "United Kingdom"), 235: ("GB", "United Kingdom"), 236: ("GI", "Gibraltar"), 237: ("GR", "Greece"), 238: ("HR", "Croatia"),
    239: ("GR", "Greece"), 240: ("GR", "Greece"), 241: ("GR", "Greece"), 242: ("MA", "Morocco"), 243: ("HU", "Hungary"), 244: ("NL", "Netherlands"), 245: ("NL", "Netherlands"),
    246: ("NL", "Netherlands"), 247: ("IT", "Italy"), 248: ("MT", "Malta"), 249: ("MT", "Malta"), 250: ("IE", "Ireland"), 251: ("IS", "Iceland"), 252: ("LI", "Liechtenstein"),
    253: ("LU", "Luxembourg"), 254: ("MC", "Monaco"), 255: ("PT", "Madeira"), 256: ("MT", "Malta"), 257: ("NO", "Norway"), 258: ("NO", "Norway"), 259: ("NO", "Norway"),
    261: ("PL", "Poland"), 262: ("ME", "Montenegro"), 263: ("PT", "Portugal"), 264: ("RO", "Romania"), 265: ("SE", "Sweden"), 266: ("SE", "Sweden"), 267: ("SK", "Slovakia"),
    268: ("SM", "San Marino"), 269: ("CH", "Switzerland"), 270: ("CZ", "Czechia"), 271: ("TR", "Türkiye"), 272: ("UA", "Ukraine"), 273: ("RU", "Russia"), 274: ("MK", "North Macedonia"),
    275: ("LV", "Latvia"), 276: ("EE", "Estonia"), 277: ("LT", "Lithuania"), 278: ("SI", "Slovenia"), 279: ("RS", "Serbia"),
    301: ("AI", "Anguilla"), 303: ("US", "Alaska"), 304: ("AG", "Antigua and Barbuda"), 305: ("AG", "Antigua and Barbuda"), 306: ("CW", "Curaçao"), 307: ("AW", "Aruba"),
    308: ("BS", "Bahamas"), 309: ("BS", "Bahamas"), 310: ("BM", "Bermuda"), 311: ("BS", "Bahamas"), 312: ("BZ", "Belize"), 314: ("BB", "Barbados"), 316: ("CA", "Canada"),
    319: ("KY", "Cayman Islands"), 321: ("CR", "Costa Rica"), 323: ("CU", "Cuba"), 325: ("DM", "Dominica"), 327: ("DO", "Dominican Republic"), 329: ("GP", "Guadeloupe"),
    330: ("GD", "Grenada"), 331: ("GL", "Greenland"), 332: ("GT", "Guatemala"), 334: ("HN", "Honduras"), 336: ("HT", "Haiti"), 338: ("US", "United States"), 339: ("JM", "Jamaica"),
    341: ("KN", "Saint Kitts and Nevis"), 343: ("LC", "Saint Lucia"), 345: ("MX", "Mexico"), 347: ("MQ", "Martinique"), 348: ("MS", "Montserrat"), 350: ("NI", "Nicaragua"),
    351: ("PA", "Panama"), 352: ("PA", "Panama"), 353: ("PA", "Panama"), 354: ("PA", "Panama"), 355: ("PA", "Panama"), 356: ("PA", "Panama"), 357: ("PA", "Panama"),
    358: ("PR", "Puerto Rico"), 359: ("SV", "El Salvador"), 361: ("PM", "Saint Pierre and Miquelon"), 362: ("TT", "Trinidad and Tobago"), 364: ("TC", "Turks and Caicos"),
    366: ("US", "United States"), 367: ("US", "United States"), 368: ("US", "United States"), 369: ("US", "United States"), 370: ("PA", "Panama"), 371: ("PA", "Panama"),
    372: ("PA", "Panama"), 373: ("PA", "Panama"), 374: ("PA", "Panama"), 375: ("VC", "Saint Vincent"), 376: ("VC", "Saint Vincent"), 377: ("VC", "Saint Vincent"),
    378: ("VG", "British Virgin Islands"), 379: ("VI", "US Virgin Islands"),
    401: ("AF", "Afghanistan"), 403: ("SA", "Saudi Arabia"), 405: ("BD", "Bangladesh"), 408: ("BH", "Bahrain"), 410: ("BT", "Bhutan"), 412: ("CN", "China"), 413: ("CN", "China"),
    414: ("CN", "China"), 416: ("TW", "Taiwan"), 417: ("LK", "Sri Lanka"), 419: ("IN", "India"), 422: ("IR", "Iran"), 423: ("AZ", "Azerbaijan"), 425: ("IQ", "Iraq"),
    428: ("IL", "Israel"), 431: ("JP", "Japan"), 432: ("JP", "Japan"), 434: ("TM", "Turkmenistan"), 436: ("KZ", "Kazakhstan"), 437: ("UZ", "Uzbekistan"), 438: ("JO", "Jordan"),
    440: ("KR", "South Korea"), 441: ("KR", "South Korea"), 443: ("PS", "Palestine"), 445: ("KP", "North Korea"), 447: ("KW", "Kuwait"), 450: ("LB", "Lebanon"), 451: ("KG", "Kyrgyzstan"),
    453: ("MO", "Macao"), 455: ("MV", "Maldives"), 457: ("MN", "Mongolia"), 459: ("NP", "Nepal"), 461: ("OM", "Oman"), 463: ("PK", "Pakistan"), 466: ("QA", "Qatar"),
    468: ("SY", "Syria"), 470: ("AE", "United Arab Emirates"), 471: ("AE", "United Arab Emirates"), 472: ("TJ", "Tajikistan"), 473: ("YE", "Yemen"), 475: ("YE", "Yemen"),
    477: ("HK", "Hong Kong"), 478: ("BA", "Bosnia and Herzegovina"),
    501: ("AQ", "Antarctica"), 503: ("AU", "Australia"), 506: ("MM", "Myanmar"), 508: ("BN", "Brunei"), 510: ("FM", "Micronesia"), 511: ("PW", "Palau"), 512: ("NZ", "New Zealand"),
    514: ("KH", "Cambodia"), 515: ("KH", "Cambodia"), 516: ("CX", "Christmas Island"), 518: ("CK", "Cook Islands"), 520: ("FJ", "Fiji"), 523: ("CC", "Cocos Islands"),
    525: ("ID", "Indonesia"), 529: ("KI", "Kiribati"), 531: ("LA", "Laos"), 533: ("MY", "Malaysia"), 536: ("MP", "Northern Mariana Islands"), 538: ("MH", "Marshall Islands"),
    540: ("NC", "New Caledonia"), 542: ("NU", "Niue"), 544: ("NR", "Nauru"), 546: ("PF", "French Polynesia"), 548: ("PH", "Philippines"), 550: ("TL", "Timor-Leste"),
    553: ("PG", "Papua New Guinea"), 555: ("PN", "Pitcairn"), 557: ("SB", "Solomon Islands"), 559: ("AS", "American Samoa"), 561: ("WS", "Samoa"), 563: ("SG", "Singapore"),
    564: ("SG", "Singapore"), 565: ("SG", "Singapore"), 566: ("SG", "Singapore"), 567: ("TH", "Thailand"), 570: ("TO", "Tonga"), 572: ("TV", "Tuvalu"), 574: ("VN", "Vietnam"),
    576: ("VU", "Vanuatu"), 577: ("VU", "Vanuatu"), 578: ("WF", "Wallis and Futuna"),
    601: ("ZA", "South Africa"), 603: ("AO", "Angola"), 605: ("DZ", "Algeria"), 607: ("TF", "French Southern Territories"), 608: ("IO", "Ascension"), 609: ("BI", "Burundi"),
    610: ("BJ", "Benin"), 611: ("BW", "Botswana"), 612: ("CF", "Central African Republic"), 613: ("CM", "Cameroon"), 615: ("CG", "Congo"), 616: ("KM", "Comoros"), 617: ("CV", "Cabo Verde"),
    618: ("AQ", "Crozet"), 619: ("CI", "Côte d'Ivoire"), 620: ("KM", "Comoros"), 621: ("DJ", "Djibouti"), 622: ("EG", "Egypt"), 624: ("ET", "Ethiopia"), 625: ("ER", "Eritrea"),
    626: ("GA", "Gabon"), 627: ("GH", "Ghana"), 629: ("GM", "Gambia"), 630: ("GW", "Guinea-Bissau"), 631: ("GQ", "Equatorial Guinea"), 632: ("GN", "Guinea"), 633: ("BF", "Burkina Faso"),
    634: ("KE", "Kenya"), 635: ("AQ", "Kerguelen"), 636: ("LR", "Liberia"), 637: ("LR", "Liberia"), 638: ("SS", "South Sudan"), 642: ("LY", "Libya"), 644: ("LS", "Lesotho"),
    645: ("MU", "Mauritius"), 647: ("MG", "Madagascar"), 649: ("ML", "Mali"), 650: ("MZ", "Mozambique"), 654: ("MR", "Mauritania"), 655: ("MW", "Malawi"), 656: ("NE", "Niger"),
    657: ("NG", "Nigeria"), 659: ("NA", "Namibia"), 660: ("RE", "Réunion"), 661: ("RW", "Rwanda"), 662: ("SD", "Sudan"), 663: ("SN", "Senegal"), 664: ("SC", "Seychelles"),
    665: ("SH", "Saint Helena"), 666: ("SO", "Somalia"), 667: ("SL", "Sierra Leone"), 668: ("ST", "São Tomé and Príncipe"), 669: ("SZ", "Eswatini"), 670: ("TD", "Chad"),
    671: ("TG", "Togo"), 672: ("TN", "Tunisia"), 674: ("TZ", "Tanzania"), 675: ("UG", "Uganda"), 676: ("CD", "DR Congo"), 677: ("TZ", "Tanzania"), 678: ("ZM", "Zambia"), 679: ("ZW", "Zimbabwe"),
    701: ("AR", "Argentina"), 710: ("BR", "Brazil"), 720: ("BO", "Bolivia"), 725: ("CL", "Chile"), 730: ("CO", "Colombia"), 735: ("EC", "Ecuador"), 740: ("FK", "Falkland Islands"),
    745: ("GF", "French Guiana"), 750: ("GY", "Guyana"), 755: ("PY", "Paraguay"), 760: ("PE", "Peru"), 765: ("SR", "Suriname"), 770: ("UY", "Uruguay"), 775: ("VE", "Venezuela"),
}
_BY_CC: dict[str, str] = {}
for _cc, _name in MID.values():
    _BY_CC.setdefault(_cc, _name)
_BY_CC.update({"US": "United States", "CY": "Cyprus", "PA": "Panama", "GR": "Greece", "PT": "Portugal", "DE": "Germany", "MT": "Malta", "SG": "Singapore", "LR": "Liberia", "NO": "Norway", "SE": "Sweden", "NL": "Netherlands", "FR": "France", "GB": "United Kingdom", "DK": "Denmark", "ES": "Spain", "CN": "China", "JP": "Japan", "KR": "South Korea", "AE": "United Arab Emirates", "VC": "Saint Vincent", "YE": "Yemen", "KH": "Cambodia", "TZ": "Tanzania", "VU": "Vanuatu", "KM": "Comoros", "BS": "Bahamas", "AG": "Antigua and Barbuda", "AQ": "Antarctica"})


def flag_of(mmsi: str, cc: str = "") -> tuple[str, str]:
    """(two-letter code, country) from the MMSI's MID, or the receiver's code."""
    cc = (cc or "").strip().upper()
    if cc and cc in _BY_CC:
        return cc, _BY_CC[cc]
    digits = re.sub(r"\D", "", str(mmsi or ""))
    if len(digits) == 9:
        mid = int(digits[:3])
        if mid in MID:
            return MID[mid]
        # a coast station, a SAR aircraft, a group: the MID sits further in
        if digits[:2] == "00" and int(digits[2:5]) in MID:
            return MID[int(digits[2:5])]
        if digits[0] == "0" and int(digits[1:4]) in MID:
            return MID[int(digits[1:4])]
        if digits[0] in "89" and int(digits[1:4]) in MID:
            return MID[int(digits[1:4])]
    return cc, ""


# ----------------------------------------------------------------------
# Geometry and names
# ----------------------------------------------------------------------
def _bearing(lat1: float, lon1: float, lat2: float, lon2: float) -> tuple[float, float]:
    """(km, degrees) from the first point to the second."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dl = math.radians(lon2 - lon1)
    a = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    km = 6371.0 * 2 * math.asin(math.sqrt(a))
    y = math.sin(dl) * math.cos(p2)
    x = math.cos(p1) * math.sin(p2) - math.sin(p1) * math.cos(p2) * math.cos(dl)
    return km, (math.degrees(math.atan2(y, x)) + 360) % 360


def bbox_of(lat: float, lon: float, radius_km: float) -> list[list[float]]:
    """[[south, west], [north, east]] round a point, as aisstream wants it."""
    dlat = radius_km / 111.0
    dlon = radius_km / max(20.0, 111.0 * math.cos(math.radians(lat)))
    return [[round(max(-90, lat - dlat), 3), round(max(-180, lon - dlon), 3)], [round(min(90, lat + dlat), 3), round(min(180, lon + dlon), 3)]]


_SMALL = {"of", "the", "and", "de", "da", "di", "del", "der", "van", "von", "la", "le", "du", "des", "y", "e"}
# a line's or a navy's prefix stays in capitals: MSC Loreto, HMAS Canberra
_PREFIXES = {"MSC", "CMA", "CGM", "HMAS", "HMS", "USS", "USNS", "HMCS", "HMNZS", "RV", "MV", "MT", "SS", "OOCL", "APL", "NYK", "ONE", "CSCL", "YM", "ZIM", "KMTC", "SITC", "RRS", "TS", "MSV", "FV", "CSAV", "PIL", "CNCO", "ANL", "UASC", "ESL", "KOTC", "SCF", "STI", "BW"}


def ship_name(raw: Any) -> str:
    """AIS names are shouted in capitals and padded with @: 'MAERSK ELBA@@@' to 'Maersk Elba'."""
    s = " ".join(str(raw or "").replace("@", " ").split())
    if not s:
        return ""
    words = []
    for i, w in enumerate(s.split(" ")):
        lw = w.lower()
        if i and lw in _SMALL:
            words.append(lw)
        elif i == 0 and len(s.split()) > 1 and (w in _PREFIXES or (len(w) <= 2 and w.isalpha() and w.isupper())):
            words.append(w)  # a prefix such as MSC, CMA, HMAS, RV
        elif re.fullmatch(r"[A-Z]{1,3}\d+", w):
            words.append(w)  # a hull number: PB 24, FV 7
        else:
            words.append(w[:1].upper() + w[1:].lower() if w.isupper() or w.islower() else w)
    return " ".join(words)


def destination_name(raw: Any) -> str:
    """'AU MEL' stays as a code; 'MELBOURNE' becomes Melbourne; '>' and '@' are tidied."""
    s = " ".join(str(raw or "").replace("@", " ").replace(">", " to ").split())
    if not s:
        return ""
    if re.fullmatch(r"[A-Z]{2} ?[A-Z0-9]{3}", s):
        return s.upper()
    out = []
    for w in s.split(" "):
        if w.lower() in _SMALL or w == "to":
            out.append(w.lower())
        elif len(w) <= 3 and w.isupper():
            out.append(w)
        else:
            out.append(w[:1].upper() + w[1:].lower())
    return " ".join(out)


def eta_text(month: Any, day: Any, hour: Any, minute: Any, now: datetime | None = None) -> str:
    """'Tue 14:00', or '' when the crew left it blank."""
    try:
        m, d, h, mi = int(month or 0), int(day or 0), int(hour if hour is not None else 24), int(minute if minute is not None else 60)
    except (TypeError, ValueError):
        return ""
    if not (1 <= m <= 12 and 1 <= d <= 31):
        return ""
    now = now or datetime.now().astimezone()
    year = now.year + (1 if m < now.month - 1 else 0)
    try:
        when = datetime(year, m, d, h if 0 <= h <= 23 else 0, mi if 0 <= mi <= 59 else 0)
    except ValueError:
        return ""
    day_word = when.strftime("%a %-d %b") if sys.platform != "win32" else when.strftime("%a %d %b")
    return f"{day_word} {when.strftime('%H:%M')}" if 0 <= h <= 23 else day_word


# ----------------------------------------------------------------------
# One vessel record from either source
# ----------------------------------------------------------------------
def _num(v: Any, default: float = 0.0) -> float:
    try:
        f = float(v)
        return f if math.isfinite(f) else default
    except (TypeError, ValueError):
        return default


def make_row(v: dict[str, Any], lat: float, lon: float, now: float) -> dict[str, Any] | None:
    """The page's vessel from a stored record: {mmsi, name, cs, imo, code, typ,
    cls, len, beam, draught, lat, lon, sog, cog, hdg, status, moving, dest,
    eta, flag_cc, flag, km, dir, age_s}."""
    vlat, vlon = v.get("lat"), v.get("lon")
    if not isinstance(vlat, (int, float)) or not isinstance(vlon, (int, float)) or abs(vlat) > 90 or abs(vlon) > 180:
        return None
    km, deg = _bearing(lat, lon, float(vlat), float(vlon))
    label, cls, code = type_of(v.get("type"))
    sog = _num(v.get("sog"), -1)
    sog = sog if 0 <= sog < 102 else -1
    status, moving = status_of(v.get("status"), sog)
    cog = _num(v.get("cog"), -1)
    hdg = _num(v.get("hdg"), -1)
    cc, country = flag_of(str(v.get("mmsi") or ""), str(v.get("cc") or ""))
    length = _num(v.get("len"))
    beam = _num(v.get("beam"))
    name = ship_name(v.get("name"))
    return {
        "mmsi": str(v.get("mmsi") or ""),
        "name": name,
        "cs": str(v.get("cs") or "").strip().upper(),
        "imo": str(v.get("imo") or "").strip() if str(v.get("imo") or "0").strip() not in ("0", "") else "",
        "code": code,
        "typ": label,
        "cls": cls,
        "len": round(length) if length > 0 else 0,
        "beam": round(beam) if beam > 0 else 0,
        "draught": round(_num(v.get("draught")), 1),
        "lat": float(vlat),
        "lon": float(vlon),
        "sog": round(sog, 1) if sog >= 0 else 0.0,
        "cog": int(round(cog)) % 360 if 0 <= cog < 360 else -1,
        "hdg": int(round(hdg)) % 360 if 0 <= hdg < 360 else -1,
        "status": status,
        "moving": moving,
        "dest": destination_name(v.get("dest")),
        "eta": str(v.get("eta") or ""),
        "flag_cc": cc,
        "flag": country,
        "km": round(km, 1),
        "dir": int(round(deg)) % 360,
        "age_s": int(max(0, now - _num(v.get("at"), now))),
    }


# ----------------------------------------------------------------------
# aisstream.io: the listener
# ----------------------------------------------------------------------
_LISTENERS: dict[str, Listener] = {}
_LISTENERS_LOCK = threading.Lock()


class Listener:
    """One connection to aisstream.io for one box of sea, kept open while a
    page asks and stopped after LISTEN_IDLE_S without one. The vessels heard
    are kept in memory and written to disk every LISTEN_SAVE_S, so a server
    restarted knows the names straight away."""

    def __init__(self, key: str, box: list[list[float]], path: Path, ua: str) -> None:
        self.key, self.box, self.path, self.ua = key, box, path, ua
        self.vessels: dict[str, dict[str, Any]] = {}
        self.lock = threading.Lock()
        self.started = time.time()
        self.asked = time.time()
        self.heard = 0
        self.error = ""
        self.connected = False
        self.stop = threading.Event()
        self._dirty = False
        got = N.read_json(path, None)
        if isinstance(got, dict) and isinstance(got.get("vessels"), dict):
            cutoff = time.time() - STATIC_S
            self.vessels = {k: v for k, v in got["vessels"].items() if isinstance(v, dict) and _num(v.get("at")) > cutoff}
        self.thread = threading.Thread(target=self._run, name="underway-listener", daemon=True)
        self.thread.start()

    # -- what a fetch reads -------------------------------------------------

    def snapshot(self) -> list[dict[str, Any]]:
        self.asked = time.time()
        cutoff = time.time() - STALE_S
        with self.lock:
            return [dict(v) for v in self.vessels.values() if _num(v.get("at")) > cutoff and v.get("lat") is not None]

    @property
    def warming(self) -> bool:
        return time.time() - self.started < LISTEN_WARM_S and not self.heard

    # -- the thread ---------------------------------------------------------

    def _run(self) -> None:
        backoff = 2.0
        while not self.stop.is_set():
            if time.time() - self.asked > LISTEN_IDLE_S:
                break
            try:
                self._session()
                backoff = 2.0
            except Exception as err:  # noqa: BLE001 - the stream is reconnected whatever went wrong
                self.connected = False
                self.error = f"{type(err).__name__}: {str(err)[:120]}"
                if "refused" in self.error.lower() or "401" in self.error or "403" in self.error:
                    self.error = "aisstream.io refused the key"
                self._save()
                if self.stop.wait(backoff):
                    break
                backoff = min(60.0, backoff * 2)
        self.connected = False
        self._save()
        with _LISTENERS_LOCK:
            if _LISTENERS.get(self._id()) is self:
                _LISTENERS.pop(self._id(), None)

    def _id(self) -> str:
        return listener_id(self.key, self.box)

    def _session(self) -> None:
        sock = WS.WebSocket(AISSTREAM, timeout=20, ua=self.ua)
        try:
            sock.send_text(json.dumps({
                "APIKey": self.key,
                "BoundingBoxes": [self.box],
                "FilterMessageTypes": ["PositionReport", "ShipStaticData", "StandardClassBPositionReport", "ExtendedClassBPositionReport", "StaticDataReport"],
            }))
            self.connected = True
            self.error = ""
            last_save = time.time()
            while not self.stop.is_set():
                if time.time() - self.asked > LISTEN_IDLE_S:
                    return
                try:
                    msg = sock.recv()
                except TimeoutError:
                    msg = ("idle", b"")
                if msg is None:
                    raise WS.WebSocketError("the stream closed")
                if msg[0] in (WS.OP_TEXT, WS.OP_BINARY) and msg[1]:
                    self._hear(msg[1])
                if time.time() - last_save > LISTEN_SAVE_S:
                    last_save = time.time()
                    self._save()
        finally:
            sock.close()
            self.connected = False

    def _hear(self, raw: bytes) -> None:
        try:
            m = json.loads(raw.decode("utf-8", "replace"))
        except ValueError:
            return
        if not isinstance(m, dict):
            return
        if m.get("error") or m.get("Error"):
            raise WS.WebSocketError(str(m.get("error") or m.get("Error"))[:120])
        kind = str(m.get("MessageType") or "")
        meta = m.get("MetaData") or {}
        body = (m.get("Message") or {}).get(kind) or {}
        if not isinstance(meta, dict) or not isinstance(body, dict):
            return
        mmsi = str(meta.get("MMSI") or body.get("UserID") or "").strip()
        if not mmsi:
            return
        now = time.time()
        with self.lock:
            v = self.vessels.setdefault(mmsi, {"mmsi": mmsi})
            v["at"] = now
            if meta.get("ShipName") and str(meta["ShipName"]).strip("@ "):
                v["name"] = str(meta["ShipName"])
            if kind in ("PositionReport", "StandardClassBPositionReport", "ExtendedClassBPositionReport"):
                if isinstance(body.get("Latitude"), (int, float)) and isinstance(body.get("Longitude"), (int, float)):
                    v["lat"], v["lon"] = float(body["Latitude"]), float(body["Longitude"])
                elif isinstance(meta.get("latitude"), (int, float)):
                    v["lat"], v["lon"] = float(meta["latitude"]), float(meta.get("longitude") or 0)
                v["sog"] = body.get("Sog")
                v["cog"] = body.get("Cog")
                v["hdg"] = body.get("TrueHeading")
                if "NavigationalStatus" in body:
                    v["status"] = body["NavigationalStatus"]
                if kind == "ExtendedClassBPositionReport":
                    if body.get("Name"):
                        v["name"] = body["Name"]
                    if body.get("Type"):
                        v["type"] = body["Type"]
                    _dims(v, body.get("Dimension"))
            elif kind == "ShipStaticData":
                if body.get("Name"):
                    v["name"] = body["Name"]
                if body.get("Type") is not None:
                    v["type"] = body["Type"]
                if body.get("CallSign"):
                    v["cs"] = body["CallSign"]
                if body.get("ImoNumber"):
                    v["imo"] = str(body["ImoNumber"])
                if body.get("Destination") is not None:
                    v["dest"] = body["Destination"]
                if body.get("MaximumStaticDraught"):
                    v["draught"] = body["MaximumStaticDraught"]
                eta = body.get("Eta") or {}
                if isinstance(eta, dict):
                    v["eta"] = eta_text(eta.get("Month"), eta.get("Day"), eta.get("Hour"), eta.get("Minute"))
                _dims(v, body.get("Dimension"))
            elif kind == "StaticDataReport":
                a = body.get("ReportA") or {}
                b = body.get("ReportB") or {}
                if isinstance(a, dict) and a.get("Name"):
                    v["name"] = a["Name"]
                if isinstance(b, dict):
                    if b.get("ShipType") is not None:
                        v["type"] = b["ShipType"]
                    if b.get("CallSign"):
                        v["cs"] = b["CallSign"]
                    _dims(v, b.get("Dimension"))
            self.heard += 1
            self._dirty = True

    def _save(self) -> None:
        if not self._dirty and self.path.exists():
            return
        with self.lock:
            cutoff = time.time() - STATIC_S
            keep = {k: v for k, v in self.vessels.items() if _num(v.get("at")) > cutoff}
            self._dirty = False
        N.write(self.path, json.dumps({"at": time.time(), "box": self.box, "vessels": keep}).encode())


def _dims(v: dict[str, Any], d: Any) -> None:
    if isinstance(d, dict):
        a, b, c, dd = (_num(d.get(k)) for k in ("A", "B", "C", "D"))
        if a + b > 0:
            v["len"] = a + b
        if c + dd > 0:
            v["beam"] = c + dd


def listener_id(key: str, box: list[list[float]]) -> str:
    import hashlib

    return hashlib.sha1(f"{key}|{json.dumps(box)}".encode()).hexdigest()[:12]


def listener_for(key: str, box: list[list[float]], data_dir: Path, ua: str) -> Listener:
    lid = listener_id(key, box)
    with _LISTENERS_LOCK:
        got = _LISTENERS.get(lid)
        if got is None or not got.thread.is_alive():
            got = Listener(key, box, data_dir / "live" / f"aisstream_{lid}.json", ua)
            _LISTENERS[lid] = got
        got.asked = time.time()
        return got


def stop_listeners() -> None:
    with _LISTENERS_LOCK:
        for lst in list(_LISTENERS.values()):
            lst.stop.set()
        _LISTENERS.clear()


# ----------------------------------------------------------------------
# A receiver of your own: AIS-catcher's web viewer
# ----------------------------------------------------------------------
def _receiver_rows(data: Any) -> list[dict[str, Any]]:
    ships = data.get("ships") if isinstance(data, dict) else data
    out: list[dict[str, Any]] = []
    now = time.time()
    for s in ships if isinstance(ships, list) else []:
        if not isinstance(s, dict) or not s.get("mmsi"):
            continue
        out.append({
            "mmsi": str(s.get("mmsi")),
            "name": s.get("shipname") or "",
            "cs": s.get("callsign") or "",
            "imo": str(s.get("imo") or ""),
            "type": s.get("shiptype"),
            "lat": s.get("lat"),
            "lon": s.get("lon"),
            "sog": s.get("speed"),
            "cog": s.get("cog"),
            "hdg": s.get("heading"),
            "status": s.get("status"),
            "dest": s.get("destination") or "",
            "eta": eta_text(s.get("eta_month"), s.get("eta_day"), s.get("eta_hour"), s.get("eta_minute")),
            "draught": s.get("draught"),
            "len": _num(s.get("to_bow")) + _num(s.get("to_stern")),
            "beam": _num(s.get("to_port")) + _num(s.get("to_starboard")),
            "cc": s.get("country") or "",
            "at": now - _num(s.get("last_signal")),
        })
    return out


# ----------------------------------------------------------------------
# The vessels near a place
# ----------------------------------------------------------------------
def nearby(source: str, receiver_url: str, api_key: str, lat: float, lon: float, radius_km: float, data_dir: Path, ua: str) -> tuple[list[dict[str, Any]], str | None, str, bool]:
    """(rows, error, feed, warming): the vessels within ``radius_km`` of a
    point, nearest first. ``warming`` is True while a fresh listener has not
    heard anything yet, so an empty sea is not yet an empty sea."""
    now = time.time()
    if source == "receiver":
        base = str(receiver_url or "").strip().rstrip("/")
        if not base:
            return [], "Give the receiver's address (for AIS-catcher, http://host:8100).", "", False
        if not base.startswith("http"):
            base = "http://" + base
        url = base if base.endswith(".json") else base + "/api/ships.json"
        cache = data_dir / "live" / (N.slug(url) + ".json")
        got = N.read_json(cache, None)
        if isinstance(got, dict) and now - _num(got.get("at")) < LIVE_S:
            data = got.get("data")
        else:
            data, err = N.get_json(url, ua=ua, timeout=4)
            if data is None:
                if isinstance(got, dict):
                    data = got.get("data")
                else:
                    why = {"unreachable": "could not be reached", "auth": "refused the request"}.get(err or "", err or "gave no answer")
                    return [], f"The receiver {why}.", "", False
            else:
                N.write(cache, json.dumps({"at": now, "data": data}).encode())
        records = _receiver_rows(data)
        feed = "your receiver"
        warming = False
    else:
        key = str(api_key or "").strip()
        if not key:
            return [], "Give an aisstream.io key in the Underway Core settings (free at aisstream.io), or point the cell at a receiver of your own.", "", False
        lst = listener_for(key, bbox_of(lat, lon, radius_km), data_dir, ua)
        records = lst.snapshot()
        feed = "aisstream.io"
        warming = lst.warming
        if lst.error and not records and not warming:
            return [], f"aisstream.io: {lst.error}.", feed, False
    rows = []
    for v in records:
        r = make_row(v, lat, lon, now)
        if r is not None and r["km"] <= radius_km:
            rows.append(r)
    rows.sort(key=lambda r: r["km"])
    return rows, None, feed, warming


def listener_note(source: str, api_key: str, lat: float, lon: float, radius_km: float) -> str:
    """A word on the stream for the foot of the page: connected, reconnecting, or nothing."""
    if source != "aisstream":
        return ""
    lid = listener_id(str(api_key or "").strip(), bbox_of(lat, lon, radius_km))
    with _LISTENERS_LOCK:
        lst = _LISTENERS.get(lid)
    if lst is None:
        return ""
    if lst.error and not lst.connected:
        return f"aisstream.io: {lst.error}; trying again"
    return ""


# ----------------------------------------------------------------------
# Photographs: Wikimedia Commons keeps a category per IMO number
# ----------------------------------------------------------------------
def photo_of(imo: str, data_dir: Path, ua: str, name: str = "") -> dict[str, str]:
    """{src, by, lic, link, w, h} for a photograph of the ship on Wikimedia
    Commons (Category:IMO <number>), kept a month; {} when there is none."""
    imo = re.sub(r"\D", "", str(imo or ""))
    if not imo or imo == "0":
        return {}
    cache = data_dir / "photos" / f"imo_{imo}.json"
    got = N.read_json(cache, None)
    if isinstance(got, dict) and time.time() - _num(got.get("at")) < (PHOTO_S if got.get("photo") else 7 * 86400):
        return got.get("photo") or {}
    # the IMO category holds the ship's own category (Ever Given (ship, 2018)); the photographs are in that
    data, err = _members(f"Category:IMO {imo}", ua)
    photo: dict[str, str] = {}
    titles, subcats = _files_and_subcats(data)
    if not titles and subcats:
        ship_cat = next((c for c in subcats if "(ship" in c.lower()), subcats[0])
        deeper, _err = _members(ship_cat, ua)
        titles, _more = _files_and_subcats(deeper)
    if titles:
        q = urllib.parse.urlencode({"action": "query", "format": "json", "titles": "|".join(titles[:8]), "prop": "imageinfo", "iiprop": "url|extmetadata|size", "iiurlwidth": "1400"})
        info, err2 = N.get_json(f"{COMMONS}?{q}", ua=ua, timeout=4)
        best: tuple[float, dict[str, str]] | None = None
        with contextlib.suppress(KeyError, TypeError, AttributeError):
            for page in info["query"]["pages"].values():
                ii = (page.get("imageinfo") or [{}])[0]
                w, h = _num(ii.get("width")), _num(ii.get("height"))
                if not ii.get("thumburl") or w < 640 or h < 360:
                    continue
                ex = ii.get("extmetadata") or {}
                by = _plain(str((ex.get("Artist") or {}).get("value") or ""))
                lic = str((ex.get("LicenseShortName") or {}).get("value") or "")
                score = min(w / max(h, 1), 2.2) + (0.5 if 1.2 <= w / max(h, 1) <= 1.9 else 0)
                title = str(page.get("title") or "").lower()
                # a file named for the ship or her number over a harbour view she happens to be in;
                # never a plaque, a cabin, a model or a plan
                if imo in title:
                    score += 2.0
                elif any(len(wd) > 3 and wd in title for wd in str(name or "").lower().split()):
                    score += 1.0
                if any(bad in title for bad in NOT_A_PORTRAIT):
                    score -= 3.0
                score += min(w, 4000) / 8000
                cand = {"src": str(ii["thumburl"]), "by": by[:80], "lic": lic[:40], "link": str(ii.get("descriptionurl") or ""), "w": str(int(w)), "h": str(int(h))}
                if best is None or score > best[0]:
                    best = (score, cand)
        if best:
            photo = best[1]
        if info is None and err2 == "unreachable":
            return {}
    if data is not None:
        N.write(cache, json.dumps({"at": time.time(), "photo": photo}).encode())
    return photo


NOT_A_PORTRAIT = (
    "plaque", "plate", "interior", "cabin", "deck", "bridge", "restaurant", "lobby", "atrium", "pool", "lounge", "theatre", "theater",
    "model", "logo", "map", "plan", "drawing", "diagram", "engine", "propeller", "anchor", "bell", "funnel", "detail", "crew", "captain",
    "menu", "ticket", "poster", "stamp", "crop", "closeup", "close-up", "inside", "stair", "corridor", "suite", "room",
    "on board", "aboard", "onboard", "from the deck", "view from", "seen from", "wake of",
)


def _members(category: str, ua: str) -> tuple[Any, str | None]:
    q = urllib.parse.urlencode({"action": "query", "format": "json", "list": "categorymembers", "cmtitle": category, "cmtype": "file|subcat", "cmlimit": "20"})
    return N.get_json(f"{COMMONS}?{q}", ua=ua, timeout=4)


def _files_and_subcats(data: Any) -> tuple[list[str], list[str]]:
    files: list[str] = []
    subcats: list[str] = []
    with contextlib.suppress(KeyError, TypeError, AttributeError):
        for m in data["query"]["categorymembers"]:
            title = str(m.get("title") or "")
            if title.lower().endswith((".jpg", ".jpeg")):
                files.append(title)
            elif title.startswith("Category:"):
                subcats.append(title)
    return files, subcats


def _plain(text: str) -> str:
    s = re.sub(r"<[^>]+>", "", text)
    return " ".join(html.unescape(s).split())


def photo_src(photo: dict[str, str], data_dir: Path, ua: str, px: int, levels: str) -> str:
    """The photograph as a data URI, fetched once and resized for the page."""
    url = photo.get("src") or ""
    if not url:
        return ""
    raw = N.cached_get(data_dir, url, ua=ua)
    if not raw:
        return ""
    import hashlib

    cache = data_dir / "img" / (hashlib.sha1(url.encode()).hexdigest()[:20] + f"_{px}.jpg")
    return N.render(raw, px, None, cache, levels)


# ----------------------------------------------------------------------
# The sea as it is: a time of day and a weather, for a painted backdrop
# ----------------------------------------------------------------------
TIMES = {
    "night": "a night sea under a dark starry sky, the vessel's navigation lights and deck lights on and their reflections on the water",
    "dawn": "the sea at dawn, the first light low on the horizon and the vessel lit from the side",
    "morning": "a bright morning at sea, the light clean and from the side",
    "midday": "a high midday sky over the sea, the light from above",
    "afternoon": "a warm afternoon at sea, the light long and from the side",
    "dusk": "the sea at dusk just after sunset, the last light on the vessel's superstructure",
}
WEATHERS = {
    "clear": "clear, the water calm",
    "partly": "with scattered fair-weather cumulus and a light chop on the water",
    "overcast": "flat and grey under overcast cloud, the sea the colour of slate",
    "fog": "soft and pale with fog, the vessel's shape fading into it",
    "rain": "grey with rain clouds and rain on the water",
    "snow": "pale with snow falling over the water",
    "storm": "brooding with storm clouds, white horses on the swell and lightning far off",
    "gale": "under a gale, the sea heaped into grey swell with spray blowing off the crests",
}


def weather_bucket(code: int, cloud: float, wind: float = 0.0) -> str:
    if wind >= 50:
        return "gale"
    if code in (95, 96, 99):
        return "storm"
    if code in (71, 73, 75, 77, 85, 86):
        return "snow"
    if code in (51, 53, 55, 56, 57, 61, 63, 65, 66, 67, 80, 81, 82):
        return "rain"
    if code in (45, 48):
        return "fog"
    if code == 3 or cloud >= 80:
        return "overcast"
    if code in (1, 2) or cloud >= 25:
        return "partly"
    return "clear"


def time_bucket(mins: int, rise: int | None, set_: int | None) -> str:
    if rise is None or set_ is None:
        return "night" if mins < 6 * 60 or mins > 19 * 60 else "midday"
    if abs(mins - rise) <= 45:
        return "dawn"
    if abs(mins - set_) <= 45:
        return "dusk"
    if mins < rise or mins > set_:
        return "night"
    if mins < 11 * 60:
        return "morning"
    if mins < 14 * 60:
        return "midday"
    return "afternoon"


def _hhmm(text: str) -> int | None:
    t = str(text or "")[-5:]
    if len(t) == 5 and t[2] == ":" and t[:2].isdigit() and t[3:].isdigit():
        return int(t[:2]) * 60 + int(t[3:])
    return None


def sea_now(lat: float, lon: float, mins: int, data_dir: Path, ua: str) -> tuple[str, str]:
    """(time bucket, weather bucket) at the place now, Open-Meteo kept WEATHER_S;
    clear midday or night when it cannot be reached."""
    cache = data_dir / "weather" / f"{lat:.2f}_{lon:.2f}.json"
    got = N.read_json(cache, None)
    if not (isinstance(got, dict) and time.time() - _num(got.get("at")) < WEATHER_S):
        data, _err = N.get_json(OPEN_METEO.format(lat=lat, lon=lon), ua=ua, timeout=4)
        if isinstance(data, dict):
            got = {"at": time.time(), "data": data}
            N.write(cache, json.dumps(got).encode())
    data = (got or {}).get("data") if isinstance(got, dict) else None
    rise = set_ = None
    code, cloud, wind = 0, 0.0, 0.0
    if isinstance(data, dict):
        cur = data.get("current") or {}
        daily = data.get("daily") or {}
        with contextlib.suppress(TypeError, ValueError, IndexError):
            code = int(cur.get("weather_code") or 0)
            cloud = float(cur.get("cloud_cover") or 0)
            wind = float(cur.get("wind_speed_10m") or 0)
            rise = _hhmm((daily.get("sunrise") or [""])[0])
            set_ = _hhmm((daily.get("sunset") or [""])[0])
    return time_bucket(mins, rise, set_), weather_bucket(code, cloud, wind)


def sea_words(tod: str, wx: str) -> str:
    return f"{TIMES.get(tod, TIMES['midday'])}, {WEATHERS.get(wx, 'clear, the water calm')}, in the same style"
