// GeoTOP's stratigraphic units and lithology classes as the page names and colors them: GeoTOP's own
// colors (bromodels' GTM_STR_UNIT_table.csv and GTM_LITHO_CLASS_table.csv, which notebooks 01, 02 and 04
// use), with the units' Dutch names in English and from young to old, and the classes in GeoTOP's order.

export interface GeotopClass {
  /** The code in soil_model.zarr's flag_meanings */
  code: string;
  name: string;
  color: string;
}

/** The units in the model's area, from young to old (GeoTOP's SEQ_NR) */
export const UNITS: GeotopClass[] = [
  { code: "AAOP", name: "Anthropogenic deposits, made ground", color: "#c8c8c8" },
  { code: "ANAWA", name: "Naaldwijk Formation, Walcheren Member (channel deposits, generation A)", color: "#76933c" },
  { code: "NAWA", name: "Naaldwijk Formation, Walcheren Member", color: "#98dc75" },
  { code: "NIHO", name: "Nieuwkoop Formation, Holland Peat Member", color: "#d08228" },
  { code: "ENAWO", name: "Naaldwijk Formation, Wormer Member (channel deposits, generation E)", color: "#1b65af" },
  { code: "NAWO", name: "Naaldwijk Formation, Wormer Member", color: "#3fa54c" },
  { code: "NAWOVE", name: "Naaldwijk Formation, Wormer Member, Velsen Bed", color: "#bdb76b" },
  { code: "NIBA", name: "Nieuwkoop Formation, Basal Peat Bed", color: "#982f0a" },
  { code: "BXWISIKO", name: "Boxtel Formation, Wierden, Singraven and Kootwijk Members", color: "#ffff50" },
  { code: "BX", name: "Boxtel Formation", color: "#ffeb00" },
  { code: "KRBXDE", name: "Kreftenheye Formation and Boxtel Formation, Delwijnen Member", color: "#b03060" },
  { code: "EE", name: "Eem Formation", color: "#beff73" },
];

/** The lithology classes, by their Dutch names in flag_meanings, in GeoTOP's order (VOXEL_NR) */
export const LITHOLOGY_CLASSES: GeotopClass[] = [
  { code: "antropogeen", name: "Anthropogenic", color: "#c8c8c8" },
  { code: "organisch materiaal (veen)", name: "Organic matter (peat)", color: "#9d4e40" },
  { code: "klei", name: "Clay", color: "#009200" },
  { code: "kleiig zand, zandige klei en leem", name: "Clayey sand, sandy clay and loam", color: "#c2cf5c" },
  { code: "zand niet gedifferentieerd", name: "Sand, not differentiated", color: "#f3e106" },
  { code: "zand fijn", name: "Fine sand", color: "#ffff00" },
  { code: "zand midden", name: "Medium sand", color: "#f3e106" },
  { code: "zand grof", name: "Coarse sand", color: "#e7c316" },
  { code: "grind", name: "Gravel", color: "#d8a320" },
  { code: "schelpen", name: "Shells", color: "#5f5fff" },
];

/**
 * The classes of a legend that codes use, in the legend's order, and each code's index among them. A code
 * the legend lacks comes last, named by itself, in gray.
 */
export function legendOf(legend: GeotopClass[], codes: string[]) {
  const extra = codes.filter((code) => !legend.some((item) => item.code === code));
  const classes = [
    ...legend.filter((item) => codes.includes(item.code)),
    ...extra.map((code) => ({ code, name: code, color: "#cccccc" })),
  ];
  return { classes, index: codes.map((code) => classes.findIndex((item) => item.code === code)) };
}
