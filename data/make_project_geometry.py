"""Write the project geometry as RFC 7946 GeoJSON (WGS 84).

The model extent and the site plot are defined in RD New (EPSG:28992);
the RD values stay on the extent's properties. Run from the repo root:

    uv run --with pyproj data/make_project_geometry.py
"""

import json
from pathlib import Path

from pyproj import Transformer

# Plot centre from the bedrock-experiments nl_amsterdam demo. The GeoTOP
# model extent is the centre ±200 m, plus one extra 100 m GeoTOP row to
# the north, down to -50 m NAP.
CENTRE_X, CENTRE_Y = 122_091, 488_736
EXTENT = dict(
    xmin=CENTRE_X - 200,
    xmax=CENTRE_X + 200,
    ymin=CENTRE_Y - 200,
    ymax=CENTRE_Y + 300,
    zmin_nap=-50,
)

# Fictitious building plot: layer "plot" of bedrock-experiments
# nl_amsterdam/data/01_raw/site.gpkg (identical to
# nl_amsterdam/data/04_feature/site_plot_rdnap_epsg7415.geojson)
SITE_PLOT = [[122027.64070962073, 488729.8189280145], [122030.00644952901, 488738.1090989709], [122028.59624384996, 488750.3614187952], [122035.77172480807, 488758.13930359477], [122096.39231516237, 488775.9788510036], [122109.80814416232, 488781.26662535727], [122123.10771052414, 488790.7801649854], [122136.66018252945, 488794.9148247155], [122139.94448296816, 488796.6213380517], [122157.55032301969, 488802.31340891554], [122158.11253250619, 488800.005148611], [122170.07445062054, 488803.8144049903], [122171.75258186687, 488802.84302273515], [122191.19470579161, 488775.26345761435], [122074.11883562425, 488689.34674238], [122072.6407355695, 488691.4451235597], [122068.86331166522, 488691.5903658417], [122067.90519318025, 488692.2689272913], [122067.11905607197, 488693.4744710882], [122054.44721843948, 488684.31678759266], [122052.34070591713, 488686.0112723248], [122045.16524171157, 488696.2617188273], [122043.06596513357, 488695.43553506484], [122041.65879244424, 488697.34140215616], [122040.7164047363, 488696.77155611955], [122036.57302339384, 488703.37685233937], [122027.64070962073, 488729.8189280145]]

# GeoTOP stores x/y on a 100 m grid. Per nlmod these are the cells'
# south-west corners (see research/voxel-export.md), so a cell spans
# [x, x + 100] × [y, y + 100]. The model takes the cells whose x/y fall
# inside the extent, which is what bromodels returns for that bbox.
GEOTOP_CELL = 100
GEOTOP_XY_OFFSET = 0  # set to -50 if x/y turn out to be cell centres

to_wgs84 = Transformer.from_crs("EPSG:28992", "EPSG:4326", always_xy=True)


def polygon(ring_rd):
    # 7 decimals is about 1 cm
    ring = [[round(c, 7) for c in to_wgs84.transform(x, y)] for x, y in ring_rd]
    return {"type": "Polygon", "coordinates": [ring]}


def write(path, name, properties, ring_rd):
    collection = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {"name": name, **properties},
                "geometry": polygon(ring_rd),
            }
        ],
    }
    path.write_text(json.dumps(collection, indent=2, ensure_ascii=False) + "\n")


def geotop_cells():
    first_x = -(-EXTENT["xmin"] // GEOTOP_CELL) * GEOTOP_CELL
    first_y = -(-EXTENT["ymin"] // GEOTOP_CELL) * GEOTOP_CELL
    features = []
    for y in range(first_y, EXTENT["ymax"] + 1, GEOTOP_CELL):
        for x in range(first_x, EXTENT["xmax"] + 1, GEOTOP_CELL):
            x0, y0 = x + GEOTOP_XY_OFFSET, y + GEOTOP_XY_OFFSET
            x1, y1 = x0 + GEOTOP_CELL, y0 + GEOTOP_CELL
            features.append(
                {
                    "type": "Feature",
                    "properties": {"geotop_x": x, "geotop_y": y},
                    "geometry": polygon(
                        [(x0, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0)]
                    ),
                }
            )
    return {"type": "FeatureCollection", "features": features}


data = Path(__file__).parent
e = EXTENT
write(
    data / "model_extent.geojson",
    "GeoTOP model extent",
    {
        "description": "Plot centre ±200 m, plus one extra 100 m GeoTOP row to the north",
        "crs_rd": "EPSG:28992",
        "centre_x": CENTRE_X,
        "centre_y": CENTRE_Y,
        **EXTENT,
    },
    [
        (e["xmin"], e["ymin"]),
        (e["xmax"], e["ymin"]),
        (e["xmax"], e["ymax"]),
        (e["xmin"], e["ymax"]),
        (e["xmin"], e["ymin"]),
    ],
)
write(
    data / "site_plot.geojson",
    "Site plot",
    {"description": "Fictitious building plot"},
    SITE_PLOT,
)
(data / "geotop_cells.geojson").write_text(json.dumps(geotop_cells()) + "\n")
