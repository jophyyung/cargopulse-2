import { cn } from "@/lib/utils";

export type UldContour = "container" | "pallet";

/** IATA ULD type codes starting with P are pallets; A/D/R-prefixed types are containers. */
export function contourOf(uldType: string | null | undefined): UldContour {
  return uldType?.trim().toUpperCase().startsWith("P") ? "pallet" : "container";
}

/**
 * ULD contour silhouettes: the lower-deck container profile with its chamfered
 * outboard corner (AKE / LD3 family) and a netted pallet load (PMC family).
 */
export function UldIcon({
  contour = "container",
  size = 20,
  strokeWidth = 1.6,
  className,
}: {
  contour?: UldContour;
  size?: number;
  strokeWidth?: number;
  className?: string;
}) {
  return (
    <svg
      className={cn("shrink-0", className)}
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={strokeWidth}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
    >
      {contour === "container" ? (
        <>
          <path d="M3 5h18v9.5L16.5 19H3z" />
          <path d="M8 5v14M13 5v14" strokeWidth="1" opacity="0.55" />
          <path d="M2 21.5h20" />
        </>
      ) : (
        <>
          <path d="M4 18.5V9l3-4h10l3 4v9.5" />
          <path d="M4 12h16M9.5 5v13.5M14.5 5v13.5" strokeWidth="1" opacity="0.55" />
          <path d="M2 18.5h20v2.5H2z" />
        </>
      )}
    </svg>
  );
}
