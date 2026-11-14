"use client";
import { Fragment, useState, type CSSProperties } from "react";
import { cn } from "@/lib/utils";

const BLANK = " ";

function Tile({ char, order }: { char: string; order: number }) {
  // Remember the previous character so the leaf that falls shows the old value.
  const [leaf, setLeaf] = useState({ current: char, previous: char, flips: 0, turning: false });
  if (char !== leaf.current)
    setLeaf({ current: char, previous: leaf.current, flips: leaf.flips + 1, turning: true });
  return (
    <span
      className="flap"
      data-narrow={/^[:.,/\-–]$/.test(char) ? "" : undefined}
      style={{ "--flap-order": order } as CSSProperties}
    >
      <span className="flap-half flap-top">
        <span>{leaf.current}</span>
      </span>
      <span className="flap-half flap-bottom">
        <span>{leaf.current}</span>
      </span>
      {leaf.turning ? (
        <Fragment key={leaf.flips}>
          <span className="flap-half flap-bottom flap-old">
            <span>{leaf.previous}</span>
          </span>
          <span className="flap-half flap-top flap-fall">
            <span>{leaf.previous}</span>
          </span>
          <span
            className="flap-half flap-bottom flap-land"
            // Once the new leaf has landed the moving leaves are removed.
            onAnimationEnd={() => setLeaf((settled) => ({ ...settled, turning: false }))}
          >
            <span>{leaf.current}</span>
          </span>
        </Fragment>
      ) : null}
    </span>
  );
}

/**
 * Split-flap readout, as on a departure board. Tiles flip only when the value
 * they show changes: pass `null`/`undefined` while a value is still loading and
 * the tiles turn over once when the real value arrives.
 */
export function FlapNumber({
  value,
  minLength = 1,
  size = "md",
  tone = "fog",
  label,
  className,
}: {
  value: string | number | null | undefined;
  /** Tiles to reserve while loading, and to left-pad short values to. */
  minLength?: number;
  size?: "sm" | "md" | "lg" | "xl";
  tone?: "fog" | "amber";
  /** Spoken alternative; defaults to the value itself. */
  label?: string;
  className?: string;
}) {
  const text = value === null || value === undefined ? "" : String(value);
  const chars = Array.from(text.padStart(minLength, BLANK));
  return (
    <span className={cn("flapboard", className)} data-size={size} data-tone={tone}>
      <span className="sr-only">{label ?? text}</span>
      <span className="flapboard-tiles" aria-hidden="true">
        {chars.map((char, index) => (
          // Keyed from the right so the units tile keeps its identity as numbers grow.
          <Tile key={chars.length - index} char={char} order={index} />
        ))}
      </span>
    </span>
  );
}
