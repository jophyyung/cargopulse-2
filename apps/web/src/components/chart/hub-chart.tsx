"use client";
import { useEffect, useId, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { airports, HUB } from "@/lib/airports";
import { cn } from "@/lib/utils";
import { StatusChip, type Status } from "../kit/status-chip";
import { useLocale } from "../locale";
import { buildFrame, CRUISE_KMH } from "./geo";

export type RouteStatus = Exclude<Status, "neutral">;

/** One line on the chart. Everything here comes from scenario data. */
export type HubRoute = {
  id: string;
  /** IATA code; the hub when omitted. */
  origin?: string;
  /** IATA code. */
  destination: string;
  status: RouteStatus;
  /** Plain title shown in the hover card, e.g. the incident name. */
  title?: string;
  /** Flight numbers on this route. */
  flights?: string[];
  /** ULD identifiers carried on this route. */
  ulds?: string[];
  /** Where a click goes, e.g. the scenario workspace. */
  href?: string;
};

type Props = {
  /** "backdrop" fills its parent and is decorative; "band" is the interactive chart. */
  variant?: "backdrop" | "band";
  width?: number;
  height?: number;
  /** Where the hub sits, as a fraction of the frame. */
  hub?: [number, number];
  /** Kilometres spanned by the frame width. */
  kmAcross?: number;
  routes?: HubRoute[];
  /** Reference places drawn as small unconnected dots (IATA codes). */
  waypoints?: string[];
  /** Play the one-off load animation (rings draw outward, routes ink in). */
  intro?: boolean;
  /** Shown in the band when there are no routes yet. */
  emptyHint?: string;
  className?: string;
};

const GLYPH: Record<RouteStatus, string> = {
  passed: "M-3.1 0.3l2.2 2.2 4-4.4",
  verify: "M0-3.3v3.7M0 3v.1",
  blocked: "M-2.5-2.5l5 5M2.5-2.5l-5 5",
  unknown: "M-2.6 0h5.2",
};

const SHOWN_ULDS = 6;

export function HubChart({
  variant = "band",
  width = 1600,
  height = 1000,
  hub = [0.5, 0.5],
  kmAcross = 18500,
  routes = [],
  waypoints = [],
  intro = true,
  emptyHint,
  className,
}: Props) {
  const { t, locale } = useLocale();
  const router = useRouter();
  const uid = useId().replace(/[^a-zA-Z0-9]/g, "");
  const [playing, setPlaying] = useState(intro);
  const [active, setActive] = useState<string | null>(null);
  const [hubX, hubY] = hub;
  const frame = useMemo(
    () => buildFrame({ width, height, hub: [hubX, hubY], kmAcross }),
    [width, height, hubX, hubY, kmAcross],
  );

  // The load animation runs once, for at most 1.5 s; any click or key skips it.
  useEffect(() => {
    if (!playing) return;
    const done = () => setPlaying(false);
    const timer = window.setTimeout(done, 1600);
    window.addEventListener("pointerdown", done);
    window.addEventListener("keydown", done);
    return () => {
      window.clearTimeout(timer);
      window.removeEventListener("pointerdown", done);
      window.removeEventListener("keydown", done);
    };
  }, [playing]);

  const statusLabel: Record<RouteStatus, string> = {
    passed: t("Passed", "通過"),
    verify: t("Needs verification", "需要核實"),
    blocked: t("Blocked", "受阻"),
    unknown: t("Unknown", "未知"),
  };
  const place = (code: string) =>
    airports[code] ? (locale === "en" ? airports[code].name : airports[code].zh) : code;

  const { cx, cy, rings } = frame;
  const step = routes.length ? Math.min(90, 650 / routes.length) : 0;
  const unplotted = new Set<string>();
  const drawn = routes.flatMap((route, index) => {
    const from = airports[route.origin ?? HUB];
    const to = airports[route.destination];
    if (!from) unplotted.add(route.origin ?? HUB);
    if (!to) unplotted.add(route.destination);
    if (!from || !to) return [];
    const end = frame.point(to.at);
    const d = frame.line(from.at, to.at);
    if (!end || !d) {
      unplotted.add(route.destination);
      return [];
    }
    // The label sits just beyond the marker, on the far side from the hub.
    const away = Math.hypot(end[0] - cx, end[1] - cy) || 1;
    const ux = (end[0] - cx) / away;
    const uy = (end[1] - cy) / away;
    return [{ route, index, d, end, ux, uy, delay: 350 + index * step }];
  });
  const marks = waypoints.flatMap((code) => {
    const at = airports[code] && frame.point(airports[code].at);
    return at ? [{ code, at }] : [];
  });
  const shown = drawn.find((item) => item.route.id === active);
  const interactive = variant === "band";
  const firstRing = rings[0]?.r ?? 0;

  return (
    <div
      className={cn("hub-chart", className)}
      data-variant={variant}
      data-intro={playing ? "play" : "off"}
      style={interactive ? { aspectRatio: `${width} / ${height}` } : undefined}
    >
      <svg
        viewBox={`0 0 ${width} ${height}`}
        preserveAspectRatio={interactive ? "xMidYMid meet" : "xMidYMid slice"}
        focusable="false"
        {...(interactive
          ? {
              role: "group",
              "aria-label": t(
                "Route chart centred on Hong Kong. Each line is a destination in the loaded incidents.",
                "以香港為中心的航線圖。每條線代表已載入事件中的一個目的地。",
              ),
            }
          : { "aria-hidden": true })}
      >
        <defs>
          <linearGradient id={`${uid}-gold`} x1="0" y1="0" x2="1" y2="1">
            <stop offset="0" className="hub-gold-deep" />
            <stop offset="0.4" className="hub-gold-mid" />
            <stop offset="0.5" className="hub-gold-pale" />
            <stop offset="0.6" className="hub-gold-mid" />
            <stop offset="1" className="hub-gold-deep" />
          </linearGradient>
          <pattern id={`${uid}-dots`} width="7" height="7" patternUnits="userSpaceOnUse">
            <circle cx="1.5" cy="1.5" r="0.7" className="hub-dot" />
            <circle cx="5" cy="5" r="0.7" className="hub-dot" />
          </pattern>
          {drawn.map(({ route, index, d, delay }) => (
            <mask
              key={route.id}
              id={`${uid}-ink-${index}`}
              maskUnits="userSpaceOnUse"
              x="0"
              y="0"
              width={width}
              height={height}
            >
              <path
                d={d}
                pathLength={1}
                className="hub-ink"
                style={{ "--d": `${delay}ms` } as React.CSSProperties}
              />
            </mask>
          ))}
        </defs>

        <rect className="hub-sea" width={width} height={height} />
        <path className="hub-graticule" d={frame.graticule} />
        <g className="hub-landmass">
          <path className="hub-shallows" d={frame.land} />
          <path className="hub-land" d={frame.land} />
          <path className="hub-land-texture" d={frame.land} fill={`url(#${uid}-dots)`} />
        </g>

        {/* Range rings: flight time from the hub at cruise speed */}
        <g className="hub-rings">
          {rings.map(({ hours, r }, index) => (
            <circle
              key={hours}
              className="hub-ring"
              cx={cx}
              cy={cy}
              r={r}
              pathLength={1}
              transform={`rotate(-90 ${cx} ${cy})`}
              stroke={`url(#${uid}-gold)`}
              style={{ "--d": `${index * 90}ms` } as React.CSSProperties}
            />
          ))}
          {rings.map(({ hours, r }, index) => (
            <text
              key={hours}
              className="hub-text hub-ring-label"
              x={Math.round(cx + r * 0.819)}
              y={Math.round(cy + r * 0.574) + 4}
              textAnchor="middle"
              style={{ "--d": `${index * 90 + 350}ms` } as React.CSSProperties}
            >
              {hours} {t("h", "小時")}
            </text>
          ))}
        </g>

        {/* Bearing ticks on the first ring, as on a compass rose */}
        {firstRing ? (
          <g className="hub-compass">
            {Array.from({ length: 36 }, (_, i) => {
              const a = (i * 10 * Math.PI) / 180;
              const len = i % 9 === 0 ? 9 : i % 3 === 0 ? 6 : 3;
              const x = Math.sin(a);
              const y = -Math.cos(a);
              return (
                <line
                  key={i}
                  x1={(cx + x * (firstRing + 3)).toFixed(1)}
                  y1={(cy + y * (firstRing + 3)).toFixed(1)}
                  x2={(cx + x * (firstRing + 3 + len)).toFixed(1)}
                  y2={(cy + y * (firstRing + 3 + len)).toFixed(1)}
                />
              );
            })}
            <text className="hub-text hub-compass-label" x={cx} y={cy - firstRing - 18} textAnchor="middle">
              N
            </text>
          </g>
        ) : null}

        <g className="hub-waypoints">
          {marks.map(({ code, at }) => (
            <g key={code} transform={`translate(${at[0]} ${at[1]})`}>
              <circle r="2.4" />
              <text className="hub-text" x="8" y="4.5">
                {code}
              </text>
            </g>
          ))}
        </g>

        <g className="hub-routes">
          {drawn.map(({ route, index, d, end, ux, uy, delay }) => {
            const label = `${place(route.destination)} (${route.destination}), ${statusLabel[route.status]}${
              route.ulds?.length ? `, ${route.ulds.length} ULD` : ""
            }`;
            const body = (
              <>
                <path className="hub-route-hit" d={d} />
                <path className="hub-route-line" d={d} mask={`url(#${uid}-ink-${index})`} />
                <g
                  className="hub-route-end"
                  transform={`translate(${end[0]} ${end[1]})`}
                  style={{ "--d": `${delay + 250}ms` } as React.CSSProperties}
                >
                  <circle className="hub-route-marker" r="7.5" />
                  <path className="hub-route-glyph" d={GLYPH[route.status]} />
                  <text
                    className="hub-text hub-route-label"
                    x={Math.round(ux * 15)}
                    y={Math.round(uy * 15) + 4.5}
                    textAnchor={ux > 0.35 ? "start" : ux < -0.35 ? "end" : "middle"}
                  >
                    {route.destination}
                  </text>
                </g>
              </>
            );
            const shared = {
              className: "hub-route",
              "data-status": route.status,
              "data-active": active === route.id || undefined,
              onPointerEnter: () => setActive(route.id),
              onPointerLeave: () => setActive((id) => (id === route.id ? null : id)),
              onFocus: () => setActive(route.id),
              onBlur: () => setActive((id) => (id === route.id ? null : id)),
            };
            return route.href && interactive ? (
              <a
                key={route.id}
                {...shared}
                href={route.href}
                aria-label={label}
                onClick={(event) => {
                  if (event.metaKey || event.ctrlKey || event.shiftKey) return;
                  event.preventDefault();
                  router.push(route.href!);
                }}
              >
                {body}
              </a>
            ) : (
              <g key={route.id} {...shared} role="img" aria-label={label} tabIndex={interactive ? 0 : undefined}>
                {body}
              </g>
            );
          })}
        </g>

        <g className="hub-home" transform={`translate(${cx} ${cy})`}>
          <circle className="hub-home-ring" r="11" stroke={`url(#${uid}-gold)`} />
          <circle className="hub-home-dot" r="4.5" />
          <text className="hub-text hub-home-label" x="17" y="-9">
            {HUB}
          </text>
        </g>
      </svg>

      {interactive && shown ? (
        <div
          className="hub-card"
          role="status"
          data-below={shown.end[1] / height < 0.4 || undefined}
          data-align={shown.end[0] / width < 0.22 ? "start" : shown.end[0] / width > 0.78 ? "end" : undefined}
          style={{ left: `${(shown.end[0] / width) * 100}%`, top: `${(shown.end[1] / height) * 100}%` }}
        >
          <strong>
            {place(shown.route.destination)} <span>{shown.route.destination}</span>
          </strong>
          {shown.route.title ? <p>{shown.route.title}</p> : null}
          <StatusChip status={shown.route.status}>{statusLabel[shown.route.status]}</StatusChip>
          {shown.route.flights?.length ? (
            <p>
              {t("Flights", "航班")}: {shown.route.flights.join(", ")}
            </p>
          ) : null}
          {shown.route.ulds?.length ? (
            <>
              <p>
                {shown.route.ulds.length} {t("containers (ULDs) on this route", "個貨櫃（ULD）在此航線")}
              </p>
              <ul>
                {shown.route.ulds.slice(0, SHOWN_ULDS).map((uld) => (
                  <li key={uld}>{uld}</li>
                ))}
                {shown.route.ulds.length > SHOWN_ULDS ? (
                  <li>
                    +{shown.route.ulds.length - SHOWN_ULDS} {t("more", "個")}
                  </li>
                ) : null}
              </ul>
            </>
          ) : null}
          {shown.route.href ? <small>{t("Click the route to open it", "點擊航線以開啟")}</small> : null}
        </div>
      ) : null}

      {interactive && !routes.length && emptyHint ? <p className="hub-empty">{emptyHint}</p> : null}
      {interactive ? (
        <p className="hub-note">
          {t(
            `Gold rings: approximate flight time from Hong Kong at ${CRUISE_KMH} km/h.`,
            `金色圓環：由香港出發、以時速 ${CRUISE_KMH} 公里計的約略飛行時間。`,
          )}
          {unplotted.size
            ? ` ${t("Not on the chart", "未能顯示於圖上")}: ${[...unplotted].join(", ")}.`
            : null}
        </p>
      ) : null}
    </div>
  );
}
