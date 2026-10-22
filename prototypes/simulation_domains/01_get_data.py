# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "bromodels==0.0.1",
#     "marimo",
#     "netcdf4",
#     "polars",
#     "pyarrow",
#     "pygef==0.13.0",
#     "pyproj",
#     "xarray",
#     "xmltodict",
# ]
# ///

# PROTOTYPE: throwaway notebook for the ticket
# "Which geological units does the model distinguish?" (issue #5).

import marimo

__generated_with = "0.24.0"
app = marimo.App(width="medium")


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    # 01 · Get GeoTOP and BRO CPT data  *(prototype)*

    Fetches the two inputs for the simulation-domain prototype and caches them in `data/`:

    - `data/geotop.nc`: GeoTOP v1.6 voxels (`strat`, `lithok`) for the model extent, from DINOloket's OPeNDAP via `bromodels`.
    - `data/cpts.parquet`: one row per CPT reading (BRO ID, RD x/y, z in m NAP, qc, fs, Rf, u2), from the BRO REST API.

    Raw BRO XMLs are cached in `data/cpt_xml/`. Any XML already in a local folder (e.g. `bedrock-experiments/nl_amsterdam/data/01_raw/gi`) is copied instead of downloaded.
    """)
    return


@app.cell
def _():
    import json
    import shutil
    from pathlib import Path
    from urllib.request import Request, urlopen

    import bromodels
    import marimo as mo
    import polars as pl
    import pyproj
    import xmltodict
    from pygef import read_cpt
    return (
        Path,
        Request,
        bromodels,
        json,
        mo,
        pl,
        pyproj,
        read_cpt,
        shutil,
        urlopen,
        xmltodict,
    )


@app.cell
def _(Path, mo):
    DATA_DIR = Path(mo.notebook_dir()) / "data"
    XML_DIR = DATA_DIR / "cpt_xml"
    XML_DIR.mkdir(parents=True, exist_ok=True)

    # Extent from bedrock-experiments/nl_amsterdam/notebooks/amsterdam_noord_geotop_to_speckle.py,
    # plus one extra row of 100 m GeoTOP columns to the north (decided on the map).
    EASTING, NORTHING = 122091, 488736
    EXTENT = dict(
        west=EASTING - 200,
        south=NORTHING - 200,
        east=EASTING + 200,
        north=NORTHING + 300,
        bottom=-50,
    )
    EXTENT
    return DATA_DIR, EXTENT, XML_DIR


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## GeoTOP
    """)
    return


@app.cell
def _(DATA_DIR, EXTENT, bromodels, mo):
    geotop_path = DATA_DIR / "geotop.nc"
    if not geotop_path.exists():
        with mo.status.spinner("Downloading GeoTOP from dinodata.nl …"):
            _ds = bromodels.GTM.GeoTop.GeoTopDomain(**EXTENT)
            _ds[["strat", "lithok"]].to_netcdf(geotop_path)
    import xarray as xr

    geotop = xr.open_dataset(geotop_path).load()
    geotop
    return (geotop,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## BRO CPTs
    """)
    return


@app.cell
def _(mo):
    local_xml_dir = mo.ui.text(
        value="../../../bedrock-experiments/nl_amsterdam/data/01_raw/gi",
        label="Local folder with BRO CPT XMLs to reuse (relative to this notebook)",
        full_width=True,
    )
    local_xml_dir
    return (local_xml_dir,)


@app.cell
def _(EXTENT, Request, json, pyproj, urlopen, xmltodict):
    from datetime import date

    # BRO's search takes a WGS84 bounding box; pad it and filter on RD coordinates later.
    _to_wgs84 = pyproj.Transformer.from_crs(28992, 4326, always_xy=True)
    _pad = 50
    _lon0, _lat0 = _to_wgs84.transform(EXTENT["west"] - _pad, EXTENT["south"] - _pad)
    _lon1, _lat1 = _to_wgs84.transform(EXTENT["east"] + _pad, EXTENT["north"] + _pad)

    _body = json.dumps(
        {
            "registrationPeriod": {"beginDate": "2015-01-01", "endDate": date.today().isoformat()},
            "area": {
                "boundingBox": {
                    "lowerCorner": {"lon": _lon0, "lat": _lat0},
                    "upperCorner": {"lon": _lon1, "lat": _lat1},
                }
            },
        }
    ).encode()
    _req = Request(
        "https://publiek.broservices.nl/sr/cpt/v1/characteristics/searches",
        data=_body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(_req, timeout=60) as _resp:
        _doc = xmltodict.parse(_resp.read(), xml_attribs=False, process_namespaces=True, namespaces={
            "http://www.opengis.net/gml/3.2": None,
            "http://www.broservices.nl/xsd/dscpt/1.1": None,
            "http://www.broservices.nl/xsd/brocommon/3.0": None,
        })
    _items = _doc["dispatchCharacteristicsResponse"]["dispatchDocument"]
    _items = _items if isinstance(_items, list) else [_items]
    bro_ids = sorted(i["CPT_C"]["broId"] for i in _items if "CPT_C" in i)
    len(bro_ids)
    return (bro_ids,)


@app.cell
def _(Path, Request, XML_DIR, bro_ids, local_xml_dir, mo, shutil, urlopen):
    _local = (Path(mo.notebook_dir()) / local_xml_dir.value).resolve()
    _copied, _downloaded = 0, 0
    for _bro_id in mo.status.progress_bar(bro_ids, title="Fetching CPT XMLs"):
        _dst = XML_DIR / f"{_bro_id}.xml"
        if _dst.exists():
            continue
        if (_local / _dst.name).exists():
            shutil.copy(_local / _dst.name, _dst)
            _copied += 1
            continue
        _url = f"https://publiek.broservices.nl/sr/cpt/v1/objects/{_bro_id}"
        with urlopen(Request(_url), timeout=60) as _resp:
            _dst.write_bytes(_resp.read())
        _downloaded += 1
    mo.md(f"{len(bro_ids)} CPTs in the padded box: {_copied} copied from the local folder, {_downloaded} downloaded.")
    return


@app.cell
def _(DATA_DIR, EXTENT, XML_DIR, bro_ids, pl, read_cpt):
    _frames = []
    for _bro_id in bro_ids:
        _cpt = read_cpt(XML_DIR / f"{_bro_id}.xml")
        _x, _y = _cpt.delivered_location.x, _cpt.delivered_location.y
        if not (EXTENT["west"] <= _x <= EXTENT["east"] and EXTENT["south"] <= _y <= EXTENT["north"]):
            continue
        _cols = _cpt.data.columns
        _frames.append(
            _cpt.data.select(
                pl.lit(_bro_id).alias("bro_id"),
                pl.lit(_x).alias("x"),
                pl.lit(_y).alias("y"),
                pl.lit(str(_cpt.research_report_date)).alias("report_date"),
                pl.lit(str(_cpt.cpt_standard)).alias("cpt_standard"),
                pl.col("depthOffset").alias("z"),  # m NAP
                pl.col("coneResistance").alias("qc"),  # MPa
                pl.col("localFriction").alias("fs") if "localFriction" in _cols else pl.lit(None, pl.Float64).alias("fs"),
                (pl.col("frictionRatio") if "frictionRatio" in _cols else pl.col("frictionRatioComputed")).alias("rf"),
                pl.col("porePressureU2").alias("u2") if "porePressureU2" in _cols else pl.lit(None, pl.Float64).alias("u2"),
            )
        )
    cpts = pl.concat(_frames).filter(pl.col("qc") > 0)
    cpts.write_parquet(DATA_DIR / "cpts.parquet")
    cpts.group_by("bro_id").agg(
        pl.first("x", "y", "report_date"), pl.max("z").alias("z_top"), pl.min("z").alias("z_base"), pl.len().alias("n")
    ).sort("bro_id")
    return


if __name__ == "__main__":
    app.run()
