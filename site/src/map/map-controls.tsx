import { CheckboxButton, CheckboxField } from "react-aria-components";
import {
  type BasemapId,
  basemaps,
  type Overlay,
  overlayColors,
} from "./map-style";
import { RadioButtonGroup } from "./radio-button-group";

interface MapLayersPanelProps {
  visibility: Record<Overlay, boolean>;
  onVisibilityChange: (overlay: Overlay, visible: boolean) => void;
  basemap: BasemapId;
  onBasemapChange: (id: BasemapId) => void;
}

/**
 * Legend with visibility toggles for the project overlays and a
 * basemap picker, after bro-xml-app's MapLayersPanel. Rendered into
 * the map via `PortalControl`.
 */
export function MapLayersPanel({
  visibility,
  onVisibilityChange,
  basemap,
  onBasemapChange,
}: MapLayersPanelProps) {
  return (
    <div className="rounded-sm border border-gray-300 bg-white/90 px-2 py-1.5 text-xs space-y-1">
      <LayerToggle
        swatch={<AreaSwatch color={overlayColors.extent} dashed />}
        label="GeoTOP model extent"
        checked={visibility.extent}
        onChange={(checked) => {
          onVisibilityChange("extent", checked);
        }}
      />
      <LayerToggle
        swatch={<AreaSwatch color={overlayColors.site} />}
        label="Site plot"
        checked={visibility.site}
        onChange={(checked) => {
          onVisibilityChange("site", checked);
        }}
      />
      <LayerToggle
        swatch={<TriangleSwatch color={overlayColors.modelCpt} highlighted />}
        label="CPTs in model extent (66)"
        checked={visibility.modelCpt}
        onChange={(checked) => {
          onVisibilityChange("modelCpt", checked);
        }}
      />

      <div className="space-y-1 border-t border-gray-200 pt-1">
        <LayerToggle
          swatch={<TriangleSwatch color={overlayColors.cpt} />}
          label="CPT"
          checked={visibility.cpt}
          onChange={(checked) => {
            onVisibilityChange("cpt", checked);
          }}
        />
        <LayerToggle
          swatch={<CircleSwatch color={overlayColors.bhrgt} />}
          label="Borehole (BHR-GT)"
          checked={visibility.bhrgt}
          onChange={(checked) => {
            onVisibilityChange("bhrgt", checked);
          }}
        />
        <LayerToggle
          swatch={<CircleSwatch color={overlayColors.bhrg} />}
          label="Borehole (BHR-G)"
          checked={visibility.bhrg}
          onChange={(checked) => {
            onVisibilityChange("bhrg", checked);
          }}
        />
      </div>

      <RadioButtonGroup
        value={basemap}
        onChange={onBasemapChange}
        aria-label="Basemap"
        orientation="vertical"
        options={basemaps.map((definition) => ({
          value: definition.id,
          label: definition.label,
        }))}
        className="border-t border-gray-200 pt-1"
      />
    </div>
  );
}

function LayerToggle({
  swatch,
  label,
  checked,
  onChange,
}: {
  swatch: React.ReactNode;
  label: string;
  checked: boolean;
  onChange: (checked: boolean) => void;
}) {
  return (
    <CheckboxField isSelected={checked} onChange={onChange}>
      <CheckboxButton className="group flex cursor-pointer items-center gap-1.5">
        <span className="flex h-3.5 w-3.5 shrink-0 items-center justify-center rounded-sm border-2 border-gray-300 transition-colors group-hover:border-gray-400 group-data-selected:border-blue-600 group-data-selected:bg-blue-600">
          <svg
            viewBox="0 0 18 18"
            className="h-2.5 w-2.5 fill-none stroke-white stroke-3 opacity-0 group-data-selected:opacity-100"
          >
            <polyline points="1 9 7 14 15 4" />
          </svg>
        </span>
        {swatch}
        {label}
      </CheckboxButton>
    </CheckboxField>
  );
}

function AreaSwatch({
  color,
  dashed = false,
}: {
  color: string;
  dashed?: boolean;
}) {
  return (
    <svg viewBox="0 0 12 12" className="h-3 w-3 shrink-0" aria-hidden>
      <rect
        x="1"
        y="1"
        width="10"
        height="10"
        fill={color}
        fillOpacity={0.25}
        stroke={color}
        strokeWidth={1.5}
        strokeDasharray={dashed ? "2.5 1.5" : undefined}
      />
    </svg>
  );
}

function TriangleSwatch({
  color,
  highlighted = false,
}: {
  color: string;
  highlighted?: boolean;
}) {
  return (
    <svg viewBox="0 0 12 12" className="h-3 w-3 shrink-0" aria-hidden>
      <polygon
        points="1,2 11,2 6,10.5"
        fill={color}
        stroke={highlighted ? "#1f2937" : "rgba(0,0,0,0.25)"}
        strokeWidth={highlighted ? 1.5 : 1}
        strokeLinejoin="round"
      />
    </svg>
  );
}

function CircleSwatch({ color }: { color: string }) {
  return (
    <span
      className="inline-block rounded-full shrink-0"
      style={{
        width: 10,
        height: 10,
        backgroundColor: color,
        border: "1px solid #ffffff",
        boxShadow: "0 0 0 1px rgba(0,0,0,0.25)",
      }}
    />
  );
}
