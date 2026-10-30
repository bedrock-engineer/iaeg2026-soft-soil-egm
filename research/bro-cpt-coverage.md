# BRO CPT coverage in the model extent

Answers [#2](https://github.com/bedrock-engineer/iaeg2026-soft-soil-egm/issues/2): how many BRO CPTs fall in the model extent, what they measure, how deep they go, which GeoTOP units they reach, and whether that is enough for per-unit variograms, SGS and hold-out validation.

**Model extent** (RD New, EPSG:28992): x 121 891 – 122 291, y 488 536 – 489 036 (centre 122 091 / 488 736, ±200 m plus one extra 100 m row to the north), bottom −50 m NAP.

## TL;DR

- **66 BRO CPTs** fall in the model extent: 57 in the ±200 m square and 9 more in the northern strip. Raw BRO XML is available locally for 63 of the 66.
- **Parameters:** all 63 have qc and fs, and friction ratio is recorded or computable. **u2 was measured in only 6** of the 63 (2022-09 batch). Inclination was recorded for 38.
- **Depth:** CPTs start at +3 to −3 m NAP. Bases are −28 to −34.5 m NAP (median −28.6 m). Five are short (stopped at −2 to −6 m). **None reaches below −34.5 m NAP**, so the lowest ~15 m of the model (−35 to −50 m, Eem Formation) has no CPT data at all.
- **Units:** there is dense coverage (≥55 CPTs with ≥1 m of data each) for NAWA, NIHO, NAWO, BXWISIKO and KRBXDE. Coverage is partial for NAWOVE (32) and BX (41). Coverage is weak for the top of EE (34 CPTs touch it, 14 have ≥1 m, at most ~6 m into a ~21 m thick unit). Coverage is near zero for ANAWA (3), NIBA (0 with ≥1 m) and AAOP (mostly predrilled).
- **Spread:** strongly clustered. About 33 CPTs, mostly from 2011/2013, sit in the SW ~120 × 130 m. There is a 2017 diagonal line SW→E, a 2022 line in the west-centre and a 2022 line along the east edge. 12 of the 20 100 m cells are occupied. Median nearest-neighbour distance is 15 m and the maximum separation is 554 m.
- **Larger boxes:** ±500 m gives **200** CPTs and ±1 km gives **1 098**. Density stays at roughly 200–350 CPTs/km² at every size.
- **Recommendation:** keep the ±200 m (+100 m N) box. It has enough data for horizontal and vertical variograms in the five main units and plenty for vertical ones. Do one of two things below about −35 m NAP: (a) raise the SGS bottom to about −35 m NAP and keep −35 to −50 as GeoTOP-only geology, or (b) pull in the 69.7 m deep `CPT000000251670` (about 300 m SE, inside the ±500 m box, base −67 m NAP) for EE. Pool or skip the thin units (ANAWA, NIBA, NAWOVE, BX, AAOP). For cross-validation, hold out whole CPT groups (see below), not single CPTs, because 8 CPTs have a twin less than 2 m away.

## How this was established

### Network: the BRO, PDOK and DINO services were blocked

The sandbox egress proxy refused CONNECT (HTTP 403, a policy denial) to every relevant host:

| Host | Purpose |
|---|---|
| `publiek.broservices.nl` | BRO REST CPT search and objects (`/sr/cpt/v1/characteristics/searches`, `/sr/cpt/v1/objects/{id}`) |
| `service.pdok.nl` | PDOK CPT WMS and the *brocptvolledigeset* ATOM full download |
| `dinodata.nl` | GeoTOP OPeNDAP (`http://dinodata.nl/opendap/GeoTOP/geotop.nc`), which `bromodels.GTM.GeoTop` reads from (confirmed in the installed `bromodels/GTM/GeoTop.py`) |
| `www.dinoloket.nl`, `www.broloket.nl` | portals |

So no live query was possible. All numbers below come from first-party BRO data already in `bedrock-experiments`.

### Sources used (local copies of first-party data)

1. **National CPT index:** `bedrock-experiments/bro_cpt_pmtiles/data/cpt_locations.fgb`. According to `bro_cpt_pmtiles/README.md`, this is the `geotechnical_cpt_survey` layer of the PDOK BRO CPT *volledige set* GeoPackage, converted with ogr2ogr. It holds 237 297 CPTs (EPSG:4258, reprojected here to 28992). The newest `research_report_date` is 2025-11-25, so the snapshot is from about December 2025. **Caveat:** CPTs registered after that date are missing. Re-run the REST search below when the network allows it.
2. **Raw BRO CPT XML (IMBRO/A):** `bedrock-experiments/nl_amsterdam/data/01_raw/gi/*.xml`, 91 files. These are exactly the CPTs within the ±500 m box that `get_bro_data_folium.py` downloaded from the BRO REST service. They were parsed with `pygef` 0.13 (`read_cpt`) for ground level (NAP), predrill, depth range, sampling interval and the columns present.
3. **GeoTOP stratigraphy:** `bedrock-experiments/nl_amsterdam/grasshopper/bgt_site_bro-geotop.3dm`. This is a Rhino export of GeoTOP v1.6 voxels with `stratigraphic_unit` and `lithostratigraphic_class` user strings on each 100 × 100 × 0.5 m voxel, read with `rhino3dm`. It covers 4 × 4 = 16 GeoTOP columns (x 121 850 – 122 250, y 488 550 – 488 950), down to −50.25 m NAP, centred on the older notebook centre 122 050 / 488 750. **Caveat:** the model extent's eastern column (x 122 250 – 122 350) and northern row (y 488 950 – 489 050) are not in this export. 19 CPTs on the east edge were therefore assigned the nearest exported column, 100–141 m away (`gdist` in the CSV). The GeoTOP layering here is close to layer-cake (unit thicknesses vary less than ±1.5 m between the 16 columns), so the error is small. Even so, re-run the unit assignment against real GeoTOP via `bromodels` once `dinodata.nl` is reachable.

The REST call to re-run is the one in `get_bro_data_folium.py`: POST `https://publiek.broservices.nl/sr/cpt/v1/characteristics/searches` with `registrationPeriod` and `area.boundingBox` (WGS84 lon/lat). Use a `registrationPeriod.beginDate` of 2017-01-01 and split it into chunks if the service limits the period. The BRO started in 2017, so archive transfers carry a 2017+ *registration* date even when the CPT itself is older.

### Derived data

`research/bro-cpt-coverage_cpts.csv` has one row per CPT in the model extent (66 rows): location, report date, standard, ground level, top and base in m NAP, parameter flags, assigned GeoTOP column, deepest unit reached, and the metres of CPT inside each GeoTOP unit.

## Results

### Counts

| Box (around 122 091 / 488 736) | CPTs | per km² |
|---|---:|---:|
| ±200 m (square) | 57 | 356 |
| **Model extent: ±200 m + 100 m north** | **66** | 330 |
| ±300 m | 104 | 289 |
| ±500 m | 200 | 200 |
| ±750 m | 478 | 212 |
| ±1 km | 1 098 | 274 |

Mix of standards in the larger boxes: ±500 m has 131 NEN 5140, 62 ISO 22476 (D1) and 7 other or unknown. ±1 km has 490 NEN 5140, 531 ISO 22476, 62 unknown and 15 NEN 3680. 74 (±500 m) and 574 (±1 km) are from 2015 or later. Depths in the larger boxes were not checked, because only the ±500 m XMLs exist locally.

### What was measured (63 CPTs with XML in the model extent)

| Batch (report date) | n | Standard | Ground level (m NAP) | Base (m NAP) | Notes |
|---|---:|---|---|---|---|
| 2009-04-15 | 1 | NEN 5140 | +0.4 | −19.6 | predrilled 2 m |
| 2011-05-12 | 8 | NEN 5140 | +1.0 to +1.7 | −21 to −24.5 | first 2 m predrilled |
| 2013-07-09 | 24 | NEN 5140 | +0.7 to +1.8 | −28 to −30.3 (one at −1.8) | some predrilled 2 m |
| 2015-02-23 | 1 | NEN 5140 | +0.6 | −28.9 | 1 cm sampling |
| 2017-06-21 | 9 | ISO 22476 | +0.5 to +2.2 | −32.8 to −34.5 | deepest group |
| 2022-08-24 | 14 | ISO 22476 | +0.5 to +3.1 | −27.5 to −30.0 | |
| 2022-09-21 | 6 (+3 without XML) | ISO 22476 | +0.6 to +1.0 | 2 to −30.5, 4 to about −6 | **only batch with u2**, predrilled 3 – 3.8 m |

- **qc, fs:** 63 / 63.
- **Friction ratio:** stored for 63 and computable for all.
- **u2:** 6 / 63, all from 2022-09. Two older ones outside the model box have u1. Without u2, qt is not available, so take qt ≈ qc. In these soft clays and peats that biases qt and Ic slightly low.
- **Inclination:** recorded for 38 / 63.
- **Sampling interval:** 2 cm (1 cm for the 2015 CPT), about 1 400 – 1 750 readings per full-depth CPT.

### Depth coverage versus the model

- Top of data: +2.9 to −3.0 m NAP. The 2011 batch, part of the 2013 batch and the 2022-09 batch start 2 – 3.8 m below ground level (predrilled).
- Base of data: 46 / 63 reach below −28 m NAP. 9 (the 2017 batch) reach −32.8 to −34.5 m. **0 reach below −34.5 m NAP.**
- Short CPTs ending above −7 m NAP: `CPT000000204248` (−1.8) and four in 2022-09 (−5.8 to −6.3, re-pushed next to a deep twin).
- The model bottom is −50 m NAP, so **about 15 m of the model (≈30 %) has no CPT conditioning data.** Within ±500 m, only `CPT000000251670` goes deeper (69.7 m, base −67.2 m NAP). Its five 2020s neighbours in that SE cluster stop at about −35 to −38 m.

### GeoTOP units reached

GeoTOP column profile in the 16 exported columns (top to bottom; thicknesses are min/mean/max in m):

| Unit | Description | Thickness | Columns with unit | CPTs touching | CPTs with ≥1 m | Total CPT metres |
|---|---|---|---:|---:|---:|---:|
| AAOP | Anthropogenic fill | 0 / 0.4 / 0.5 | 14 | 32 | 0 | 15 |
| NAWA | Naaldwijk, Walcheren | 3 / 4.0 / 5 | 16 | 63 | 61 | 191 |
| NIHO | Nieuwkoop, Hollandveen (peat) | 0 / 1.3 / 2 | 15 | 62 | 62 | 99 |
| NAWO | Naaldwijk, Wormer | 6 / 7.8 / 8.5 | 16 | 62 | 62 | 447 |
| ANAWA | Walcheren channel deposits A | 0 / 0.2 / 3.5 | 1 | 3 | 3 | 10 |
| NAWOVE | Wormer, Laag van Velsen | 0 / 0.6 / 1.5 | 11 | 44 | 32 | 40 |
| NIBA | Basisveen (basal peat) | 0 / 0.2 / 0.5 | 6 | 38 | 0 | 19 |
| BXWISIKO | Boxtel (Wierden/Singraven/Kootwijk) | 0.5 / 2.0 / 3.5 | 16 | 58 | 55 | 98 |
| BX | Boxtel | 0 / 0.6 / 1.5 | 11 | 47 | 41 | 58 |
| KRBXDE | Kreftenheye + Boxtel Delwijnen (Pleistocene sand) | 11 / 12.3 / 13.5 | 16 | 58 | 58 | 668 |
| EE | Eem Formation | 20.5 / 21.6 / 22.5 (to the −50 m base) | 16 | 34 | 14 | 56 |

Approximate unit tops: NAWA about +0.75, NIHO about −3, NAWO about −5, BXWISIKO about −13, KRBXDE about −16, EE about −28 m NAP.

Deepest unit reached: 34 CPTs reach EE, 24 stop in KRBXDE (mostly the NEN 5140 batches ending at −24 to −29 m), 4 stop in NAWO and 1 in NAWA.

Sample counts at 2 cm spacing are large: about 9 500 readings in NAWA, 22 000 in NAWO and 33 000 in KRBXDE. The limit on variograms is therefore the **number of distinct CPT locations per unit**, not the number of readings.

### Horizontal spread

- **SW cluster** (x ≈ 121 935 – 122 055, y ≈ 488 535 – 488 665): 33 CPTs, of which 32 are NEN 5140 from 2011/2013 and 1 is from 2017. Spacing is about 10 – 25 m.
- **2017 diagonal** from SW (122 054, 488 560) to E (122 283, 488 789): 9 CPTs about 40 m apart. These are the deepest and best quality.
- **2022-08 west-centre group** (x ≈ 121 895 – 122 056, y ≈ 488 669 – 488 761): 8 CPTs.
- **East edge line** (x ≈ 122 255 – 122 291, y ≈ 488 784 – 489 026): 2022 CPTs plus one from 2015, about 18 including the twins.
- **Gaps:** the centre and north-centre (x 122 050 – 122 250, y 488 750 – 489 036) hold only `CPT000000198166` and `CPT000000060419`. The NW corner is empty. 8 of the 20 100 m cells are empty.
- **Inter-CPT pair distances:** 304 pairs < 50 m, 616 pairs 50 – 150 m, 1 225 pairs > 150 m. The maximum is 554 m.
- **Near-duplicates (< 2 m apart):** 8 CPTs, for example 198154/198155, 198156/198157, 198152/198153, 204199/204248 and 205986/206226.

## Is it enough?

**Vertical variograms:** yes, for every unit thicker than about 1 m. They come from hundreds to thousands of 2 cm readings per unit in 30 – 60 CPTs.

**Horizontal variograms per unit:**
- **NAWA, NIHO, NAWO, BXWISIKO, KRBXDE** (55 – 63 CPTs each, spanning about 550 m): enough for an omnidirectional experimental horizontal variogram, with lags of about 25 m out to about 250 – 300 m. Short lags are dominated by the SW cluster and long lags by the east line versus the SW, so expect noisy directional (anisotropic) variograms. Fit an isotropic horizontal range, or impose an anisotropy ratio.
- **NAWOVE, BX** (32 – 41 CPTs, 0.5 – 1.5 m thick): fit is marginal. Pool with the adjacent unit (NAWOVE with NAWO, BX with BXWISIKO) or reuse that unit's variogram.
- **AAOP, NIBA, ANAWA:** too thin or too sparse. Pool with neighbours, use a nugget-only or borrowed model, or merge them in the GemPy unit scheme.
- **EE:** the variogram can only be fitted on its top 0 – 6 m (34 CPTs). From −35 to −50 m, SGS would be unconditioned simulation from the prior, which is a poor showcase.

**Holding out CPTs for cross-validation:** there is enough data to hold out about 10 – 15 % (6 – 10 CPTs) and still fit the main-unit variograms. Practical rules:
- Hold out **twins together** (< 2 m apart), otherwise validation is trivially easy.
- A demo-friendly split: hold out the **2017 diagonal (9 CPTs, ISO, deepest)** as a whole-line test. This is leave-one-group-out: it tests interpolation across 40 m gaps. It removes the only CPTs reaching −32 to −34 m, so for the EE top choose instead 3 – 4 of the 2017 CPTs, for example 203445, 202087 and 202327.
- An alternative: thin the redundant SW cluster (hold out about 8 of its 33 CPTs). This costs the model little, but it is also an easy test.
- Avoid holding out `CPT000000198166`, `CPT000000060419` and `CPT000000202240`, which cover the sparse centre and east.
- Mind the standards: NEN 5140 (2009 – 2015, 34 CPTs) and ISO 22476 (2017 – 2022, 32 CPTs) are both class 2/D1-ish electrical cones. Treat them as one population, but check for a qc bias between batches in NAWO and KRBXDE before pooling.

## Recommendation

1. Keep the current extent (66 CPTs). Do not enlarge it to ±500 m for data reasons: 3× the area brings 3× the CPTs at lower density, and they still stop at about −35 m (except one).
2. Either raise the SGS and conditioning bottom to **about −35 m NAP** (and show −35 to −50 m EE as GeoTOP-only geology), or add **`CPT000000251670`** (122 364, 488 518, base −67 m NAP) with a small SE extension as the single deep EE conditioning profile. Make clear in the talk that it is one profile only.
3. Use the five main units (NAWA, NIHO, NAWO, BXWISIKO, KRBXDE) for per-unit variograms. Pool the thin units.
4. Use qt ≈ qc (u2 is in only 6 CPTs). Report Ic with that caveat.
5. When the network allows, re-run the BRO REST search: to pick up any CPTs registered after December 2025, to fetch the three missing XMLs (`CPT000000198146`, `198152`, `198153`; from 2022-09 and likely short re-push twins), and to check the unit assignment against real GeoTOP via `bromodels` for the east and north columns.
