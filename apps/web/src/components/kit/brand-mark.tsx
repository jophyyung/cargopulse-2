/**
 * CargoPulse mark: the contour of an AKE (LD3) lower-deck container with a pulse
 * trace running through it. Original artwork; not an airline logo.
 */
export function BrandMark({ size = 28, className }: { size?: number; className?: string }) {
  return (
    <svg
      className={className}
      width={size}
      height={size}
      viewBox="0 0 28 28"
      fill="none"
      aria-hidden="true"
      focusable="false"
    >
      <path
        d="M3.5 5.5h21v12.2l-5.8 5.8H3.5z"
        stroke="var(--ink)"
        strokeWidth="1.6"
        strokeLinejoin="round"
      />
      <path
        d="M3.5 14.5h5.2l2.4-5 3.6 9.4 2.5-4.4h7.3"
        stroke="var(--jade)"
        strokeWidth="1.8"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}
