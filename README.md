# Underway

Four Tesserae widgets for the ships on the water near you right now, installed together as one bundle:

| widget | the page |
|---|---|
| **Underway: Photo** | the nearest vessel as a full-bleed photograph of the very ship, the next few along a strip |
| **Underway: Plate** | one vessel painted from her photograph, in a ruled frame, her particulars beside her; or one of four modern looks in the colours of her trade |
| **Underway: Fleet** | everything on the water near you on one page, each painted and cut out, sized by her length; or a log of photograph cards |
| **Underway: Scene** | one whole painting across the page: the vessel on the open sea, in harbour, along the coast, at sunset, at night or in heavy weather |

**Positions** come from aisstream.io (a free key, in the Underway Core settings) or a receiver of your own running AIS-catcher (the widget reads `/api/ships.json`). aisstream.io is a stream rather than a request: the widget keeps one connection open for the sea round your place while a page asks, hears every vessel in it, and lets the connection go when no page has asked for twenty minutes. The first page after a start listens for a moment and fills within a minute; what each vessel has said of herself (name, type, destination, ETA, size) is kept, so the names are known straight away next time.

Each vessel gets her type and flag from her AIS messages and her MMSI, her destination and ETA as her crew entered them, and a photograph of the very ship from Wikimedia Commons, which keeps a category per IMO number, credited to the photographer and the licence on the page. On Tesserae 0.465 and later the lookup is the host's (`app.commons`), shared with every widget that paints and kept once under the data root. A vessel Commons has no photograph of is then looked up through **Openverse** (openverse.org, which indexes the openly licensed pictures on Flickr, Wikimedia Commons and others, and answers without a key), by IMO number and then by name, among photographs under a licence that allows a painting to be made from them (CC BY, BY-SA, public domain, and the non-commercial licences unless the Underway Core setting says open only; never the ND licences); ship spotters photograph the tugs, ferries and pilot boats of a port that Commons never sees. Yachts, fishing boats and other small craft are looked up by IMO number only, since a picture found by a name like Lady Anne is most often another boat of that name. Openverse allows two hundred look-ups a day from one address; each answer is kept a month, a miss a week, so a port's regulars are asked for once. A vessel with no photograph anywhere is painted from her particulars alone, and the page marks such a painting an impression; or, with **Paint** set to only vessels with a photograph, she is left unpainted (a silhouette or her photograph, as the page's setting for a vessel not yet painted says) and nothing is spent on her.

**Since the last render** is a setting on every page beside the order: instead of what is within reach at the moment the page is drawn, everything that passed since the page was last drawn for a panel, each vessel at her closest approach with the time, so a page drawn every hour is the hour's traffic rather than one moment of it. The widget keeps a watch on the place between renders (the stream looked at every twenty seconds, a receiver asked every thirty) and remembers each vessel with the moment she came closest, for two days; the windows chain, so nothing falls between two pages, and the warm-ahead, the settle and the send of one page share a window. The editor's previews show the same window without moving it on. The watch stops three hours after a page last asked, and a first render shows the last hour. A label line, **When she was within reach**, says when she was first heard and, once she has gone, when last.

**Which vessels** on a page: by default the photographed ones first within the order chosen (nearest, largest, fastest, under way), looking twice as deep as the page shows, so a page is not silhouettes and impressions while a photographed ship sits just beyond the count; or the order alone.

**Painted from her particulars**, a vessel is described to the painter with everything AIS says of her (type, length, beam, draught, flag, whether she lies at anchor or is under way and how fast, where she is bound), the livery of her line when the widget knows it from her name (Maersk, MSC, CMA CGM, COSCO, Evergreen, Hapag-Lloyd, ONE, ANL, Hamburg Süd, the car carriers, the tanker fleets, Spirit of Tasmania, SeaRoad, Svitzer, Stena, DFDS, Cunard and the cruise lines, the navies, pilot boats), and your own **fleet notes** from the Underway Core settings: one vessel a line, `name: how she looks`, a name ending in `*` covering a fleet. A note of yours on a vessel comes before the livery table.

**Pictures** are the photographs, or AI paintings: each ship painted once from her own photograph through fal.ai, in a style, on white paper so she cuts out cleanly, at about US$0.04 a painting. Twenty-eight styles, from a shipping-line poster, engravings, watercolour, woodblock, linocut, Art Deco and mid-century flat to a magazine cutaway, a postage stamp, a sailor's tattoo flash, risograph, pixel art, a low-poly render, paper craft, toy bricks, a ship in a bottle, scrimshaw, charcoal, stained glass, an illuminated manuscript, a pulp cover, synthwave and a chalkboard, **Build my own** and **Your own prompt**. The Plate and the Scene take a **backdrop**: none, the open sea, in harbour, along the coast, sunset, night, heavy weather, an ornate framed plate, or the sea as it is now (time of day and weather from Open-Meteo).

**Chance of a visitor** is a slider on the painted pages: each hour the page rolls it, and on a hit something that should not be on the water joins, from the visitors you tick: creatures of myth (a kraken, a sea serpent, a leviathan, a mermaid), vessels of story (a ghost ship, an iron submarine, a black pirate ship, a white whale, a yellow submarine, an ark) and real ships of history (a tea clipper, a ship of the line, a four-funnelled liner, a longship, a trireme, a junk, a galleon), painted from words in the page's style, the smallest thing on the page, captioned with no AIS.

**Settings** live on Underway Core (Settings › Widgets): the aisstream.io key, the fal.ai key (or the one under Settings › Generative AI), which photograph licences, your fleet notes, a contact for Wikimedia Commons, the daily painting budget, how many paintings start per preview and run at once. The paintings page is under Widgets › Underway Core.

**How full the catalogue is**: the widgets count every pass of every vessel they see, across all your cells (the same one again within half an hour is one pass), in one ledger under the core's data folder. The paintings page shows the chance the next one past is already painted, what share of passes were of a painted one, how many seen are painted, and an estimate of how many pass your places in all (Chao1, from how many were seen once and twice), with the ones seen most.

## Install

Needs Tesserae 0.463 or later for the paintings; an older server still shows the photographs.

From the Tesserae catalog as the Underway bundle, or by hand: copy the five folders (`underway_core`, `underway_photo`, `underway_plate`, `underway_fleet`, `underway_scene`) into your plugins folder together; the four widgets load their shared code from `underway_core` by path.

## Development

```sh
PYTHONPATH=../tesserae python -m pytest underway_core/tests -q    # offline: every call on the network is faked
python3 underway_core/tools/manifests.py                           # rewrites the four plugin.json from one description
```
