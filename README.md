# Underway

Four Tesserae widgets for the ships on the water near you right now, installed together as one bundle:

| widget | the page |
|---|---|
| **Underway: Photo** | the nearest vessel as a full-bleed photograph of the very ship, the next few along a strip |
| **Underway: Plate** | one vessel painted from her photograph, in a ruled frame, her particulars beside her; or one of four modern looks in the colours of her trade |
| **Underway: Fleet** | everything on the water near you on one page, each painted and cut out, sized by her length; or a log of photograph cards |
| **Underway: Scene** | one whole painting across the page: the vessel on the open sea, in harbour, along the coast, at sunset, at night or in heavy weather |

**Positions** come from aisstream.io (a free key, in the Underway Core settings) or a receiver of your own running AIS-catcher (the widget reads `/api/ships.json`). aisstream.io is a stream rather than a request: the widget keeps one connection open for the sea round your place while a page asks, hears every vessel in it, and lets the connection go when no page has asked for twenty minutes. The first page after a start listens for a moment and fills within a minute; what each vessel has said of herself (name, type, destination, ETA, size) is kept, so the names are known straight away next time.

Each vessel gets her type and flag from her AIS messages and her MMSI, her destination and ETA as her crew entered them, and a photograph of the very ship from Wikimedia Commons, which keeps a category per IMO number, credited to the photographer and the licence on the page. A vessel without an IMO number (most fishing boats, yachts and work boats) has no photograph and is painted from her particulars alone, and the page marks such a painting an impression. On Tesserae 0.465 and later the lookup is the host's (`app.commons`), shared with every widget that paints and kept once under the data root.

**Pictures** are the photographs, or AI paintings: each ship painted once from her own photograph through fal.ai, in a style, on white paper so she cuts out cleanly, at about US$0.04 a painting. Twenty-eight styles, from a shipping-line poster, engravings, watercolour, woodblock, linocut, Art Deco and mid-century flat to a magazine cutaway, a postage stamp, a sailor's tattoo flash, risograph, pixel art, a low-poly render, paper craft, toy bricks, a ship in a bottle, scrimshaw, charcoal, stained glass, an illuminated manuscript, a pulp cover, synthwave and a chalkboard, **Build my own** and **Your own prompt**. The Plate and the Scene take a **backdrop**: none, the open sea, in harbour, along the coast, sunset, night, heavy weather, an ornate framed plate, or the sea as it is now (time of day and weather from Open-Meteo).

**Chance of a visitor** is a slider on the painted pages: each hour the page rolls it, and on a hit something that should not be on the water joins, from the visitors you tick: creatures of myth (a kraken, a sea serpent, a leviathan, a mermaid), vessels of story (a ghost ship, an iron submarine, a black pirate ship, a white whale, a yellow submarine, an ark) and real ships of history (a tea clipper, a ship of the line, a four-funnelled liner, a longship, a trireme, a junk, a galleon), painted from words in the page's style, the smallest thing on the page, captioned with no AIS.

**Settings** live on Underway Core (Settings › Widgets): the aisstream.io key, the fal.ai key (or the one under Settings › Generative AI), a contact for Wikimedia Commons, the daily painting budget, how many paintings start per preview and run at once. The paintings page is under Widgets › Underway Core.

## Install

Needs Tesserae 0.463 or later for the paintings; an older server still shows the photographs.

From the Tesserae catalog as the Underway bundle, or by hand: copy the five folders (`underway_core`, `underway_photo`, `underway_plate`, `underway_fleet`, `underway_scene`) into your plugins folder together; the four widgets load their shared code from `underway_core` by path.

## Development

```sh
PYTHONPATH=../tesserae python -m pytest underway_core/tests -q    # offline: every call on the network is faked
python3 underway_core/tools/manifests.py                           # rewrites the four plugin.json from one description
```
