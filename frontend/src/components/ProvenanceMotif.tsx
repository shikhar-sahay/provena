// Provenance motif: faint evidence-lineage geometry (nodes and traces) for
// the sign-in backdrop. Static SVG, extremely low contrast, theme-aware via
// currentColor. Decorative only and hidden from assistive technology.

const NODES: [number, number, number][] = [
  [80, 120, 3], [200, 70, 2.5], [330, 140, 3], [460, 90, 2.5], [590, 160, 3],
  [140, 260, 2.5], [270, 230, 3], [400, 280, 2.5], [530, 240, 3], [660, 300, 2.5],
  [100, 400, 3], [240, 370, 2.5], [370, 420, 3], [500, 380, 2.5], [630, 440, 3],
  [180, 520, 2.5], [320, 500, 3], [460, 540, 2.5], [600, 510, 2],
];

const TRACES: [number, number][] = [
  [0, 1], [1, 2], [2, 3], [3, 4], [0, 5], [1, 6], [2, 6], [3, 7], [4, 7],
  [5, 6], [6, 7], [7, 8], [8, 9], [5, 10], [6, 11], [7, 12], [8, 12], [9, 14],
  [10, 11], [11, 12], [12, 13], [13, 14], [10, 15], [11, 16], [12, 16],
  [13, 17], [14, 18], [15, 16], [16, 17], [17, 18],
];

export function ProvenanceMotif({ className = "" }: { className?: string }) {
  return (
    <svg
      aria-hidden="true"
      focusable="false"
      viewBox="0 0 720 600"
      preserveAspectRatio="xMidYMid slice"
      className={className}
    >
      <defs>
        <radialGradient id="pv-motif-glow" cx="50%" cy="38%" r="65%">
          <stop offset="0%" stopColor="currentColor" stopOpacity="0.07" />
          <stop offset="100%" stopColor="currentColor" stopOpacity="0" />
        </radialGradient>
      </defs>
      <rect width="720" height="600" fill="url(#pv-motif-glow)" />
      <g stroke="currentColor" strokeOpacity="0.14" strokeWidth="1">
        {TRACES.map(([from, to], index) => (
          <line
            key={index}
            x1={NODES[from][0]}
            y1={NODES[from][1]}
            x2={NODES[to][0]}
            y2={NODES[to][1]}
          />
        ))}
      </g>
      <g fill="currentColor" fillOpacity="0.22">
        {NODES.map(([x, y, radius], index) => (
          <circle key={index} cx={x} cy={y} r={radius} />
        ))}
      </g>
      <g fill="none" stroke="currentColor" strokeOpacity="0.2" strokeWidth="1.5">
        <circle cx={270} cy={230} r={9} />
        <circle cx={400} cy={280} r={9} />
        <circle cx={140} cy={260} r={7} />
      </g>
    </svg>
  );
}
