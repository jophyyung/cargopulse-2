import { geoAzimuthalEquidistant, geoGraticule, geoPath } from "d3-geo";

// Hong Kong International Airport (HKG): 22.308°N 113.918°E.
export const HKG: [number, number] = [113.918, 22.308];

const WIDTH = 1600;
const HEIGHT = 1000;
// Ten degrees of arc span 150 px at the centre of the chart.
const SCALE = 150 / ((10 * Math.PI) / 180);

function build() {
  const projection = geoAzimuthalEquidistant()
    .rotate([-HKG[0], -HKG[1]])
    .scale(SCALE)
    .translate([WIDTH * 0.62, HEIGHT * 0.5])
    .clipAngle(80)
    .clipExtent([
      [-40, -40],
      [WIDTH + 40, HEIGHT + 40],
    ])
    .precision(0.4);
  const path = geoPath(projection).digits(1);
  return {
    major: path(geoGraticule().step([10, 10])()) ?? "",
    minor: path(geoGraticule().step([5, 5])()) ?? "",
  };
}

const lines = build();

/**
 * Page background: the latitude/longitude grid of an azimuthal chart centred on
 * HKG, computed from the real projection. Decorative, so hidden from assistive
 * technology; it never moves.
 */
export function Graticule() {
  return (
    <svg
      className="graticule"
      viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
      preserveAspectRatio="xMidYMid slice"
      aria-hidden="true"
      focusable="false"
    >
      <path className="graticule-minor" d={lines.minor} />
      <path className="graticule-major" d={lines.major} />
    </svg>
  );
}
