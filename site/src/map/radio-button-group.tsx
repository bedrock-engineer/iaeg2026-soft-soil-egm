import {
  Label,
  RadioButton,
  RadioField,
  RadioGroup,
} from "react-aria-components";

interface RadioButtonGroupProps<V extends string> {
  value: V;
  onChange: (value: V) => void;
  options: ReadonlyArray<{ value: V; label: string }>;
  /** Visible label rendered before the options. */
  label?: string;
  /** Accessible label for groups without a visible one. */
  "aria-label"?: string;
  orientation?: "horizontal" | "vertical";
  className?: string;
}

/**
 * App-wide radio group: conventional circle-and-dot radio buttons, laid out
 * horizontally by default with an optional inline label. Text size and color
 * are inherited from the surrounding context so the group blends into both
 * the text-sm cards and the text-xs map legend.
 */
export function RadioButtonGroup<V extends string>({
  value,
  onChange,
  options,
  label,
  "aria-label": ariaLabel,
  orientation = "horizontal",
  className,
}: RadioButtonGroupProps<V>) {
  const horizontal = orientation === "horizontal";

  return (
    <RadioGroup
      value={value}
      onChange={(v) => {
        onChange(v as V);
      }}
      orientation={orientation}
      aria-label={ariaLabel}
      className={[
        horizontal ? "flex flex-wrap items-center gap-x-3 gap-y-1" : undefined,
        className,
      ]
        .filter(Boolean)
        .join(" ")}
    >
      {label !== undefined && <Label className="font-medium">{label}</Label>}
      <div
        className={
          horizontal
            ? "flex flex-wrap items-center gap-x-4 gap-y-1"
            : "space-y-0.5"
        }
      >
        {options.map((option) => (
          <RadioField key={option.value} value={option.value}>
            <RadioButton className="group flex cursor-pointer items-center gap-1.5">
              <span className="flex h-3.5 w-3.5 shrink-0 items-center justify-center rounded-full border-2 border-gray-300 transition-colors group-hover:border-gray-400 group-data-selected:border-blue-600">
                <span className="h-1.5 w-1.5 rounded-full bg-blue-600 opacity-0 transition-opacity group-data-selected:opacity-100" />
              </span>
              {option.label}
            </RadioButton>
          </RadioField>
        ))}
      </div>
    </RadioGroup>
  );
}
