import { CircleCheck, CircleDashed, CircleDot, OctagonX, TriangleAlert } from "lucide-react";
import { cn } from "@/lib/utils";

export type Status = "passed" | "verify" | "blocked" | "unknown" | "neutral";

const icons = {
  passed: CircleCheck,
  verify: TriangleAlert,
  blocked: OctagonX,
  unknown: CircleDashed,
  neutral: CircleDot,
} as const;

/** Maps a service state code (PLAN_READY, NEEDS_VERIFICATION, …) to a semantic status. */
export function statusOf(code: string): Status {
  if (/FAIL|BLOCK|QUARANTIN|STALE|ERROR|NO_FEASIBLE|NO_COMPLIANT|REJECT/.test(code)) return "blocked";
  if (/^(PASS|PASSED|READY|PLAN_READY|COMPLETED|APPROVED|PUBLISHED|VERIFIED|SUCCESS)$/.test(code)) return "passed";
  if (/NEEDS_|PENDING|ESCALAT|WARN|REVIEW|UNVERIFIED/.test(code)) return "verify";
  if (/UNKNOWN|UNDEFINED|UNAVAILABLE/.test(code)) return "unknown";
  return "neutral";
}

const acronyms = new Set(["ULD", "ULDS", "AWB", "CSV", "JSON", "API", "UTC", "HKT", "SSO", "OIDC", "ID", "PDF"]);

/** "NEEDS_VERIFICATION" → "Needs verification". Mixed-case input is left as written. */
export function humanise(code: string): string {
  const spaced = code.replaceAll("_", " ");
  if (!/^[A-Z0-9 ]+$/.test(spaced)) return spaced;
  return spaced
    .split(" ")
    .map((word, index) =>
      acronyms.has(word) || word.length === 1
        ? word
        : index === 0
          ? word[0] + word.slice(1).toLowerCase()
          : word.toLowerCase(),
    )
    .join(" ");
}

/** Status is always carried by an icon and a label, never by colour alone. */
export function StatusChip({
  status,
  children,
  className,
}: {
  status: Status;
  children: React.ReactNode;
  className?: string;
}) {
  const Icon = icons[status];
  return (
    <span className={cn("chip", className)} data-status={status}>
      <Icon size={14} strokeWidth={2.25} aria-hidden="true" />
      <span>{children}</span>
    </span>
  );
}
