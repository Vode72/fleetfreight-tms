import { useId } from "react";

interface PreferenceSelectProps<T extends string> {
  label: string;
  value: T;
  options: readonly { value: T; label: string }[];
  onChange: (value: T) => void;
}

/** Compact labelled native select: keyboard and screen reader support come from the browser. */
export function PreferenceSelect<T extends string>({ label, value, options, onChange }: PreferenceSelectProps<T>) {
  const id = useId();

  return (
    <div className="topbar-field">
      <label htmlFor={id}>{label}</label>
      <select
        id={id}
        value={value}
        onChange={(event) => {
          const selected = options.find((option) => option.value === event.target.value);
          if (selected) onChange(selected.value);
        }}
      >
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
    </div>
  );
}
