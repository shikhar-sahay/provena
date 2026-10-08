// Provenance motif: evidence-lineage network geometry (nodes, directed traces,
// and evidence hub rings) spanning the full viewport for the sign-in backdrop.
// Theme-aware via currentColor, responsive, non-distracting, decorative.

interface NodeDef {
  x: number;
  y: number;
  r: number;
  hub?: boolean;
}

const NODES: NodeDef[] = [
  // Band 1: Far Left / bleed off-screen
  { x: -60, y: 160, r: 2.5 },
  { x: -40, y: 520, r: 3 },
  { x: -80, y: 860, r: 2.5 },
  { x: 120, y: -40, r: 2.5 },
  { x: 80, y: 340, r: 3 },
  { x: 60, y: 700, r: 2.5 },
  { x: 140, y: 1040, r: 3 },

  // Band 2: Left column (branding area)
  { x: 260, y: 140, r: 3 },
  { x: 360, y: 440, r: 3.5, hub: true },
  { x: 240, y: 680, r: 2.5 },
  { x: 380, y: 920, r: 3 },
  { x: 480, y: 260, r: 3.5, hub: true },
  { x: 540, y: 580, r: 2.5 },
  { x: 480, y: 820, r: 3 },

  // Band 3: Center-left bridge
  { x: 680, y: 80, r: 2.5 },
  { x: 740, y: 380, r: 3.5, hub: true },
  { x: 660, y: 720, r: 2.5 },
  { x: 760, y: 1020, r: 3 },

  // Band 4: Center (spanning behind workspace)
  { x: 920, y: -50, r: 2.5 },
  { x: 960, y: 220, r: 3 },
  { x: 880, y: 540, r: 3 },
  { x: 980, y: 820, r: 2.5 },
  { x: 900, y: 1120, r: 3 },

  // Band 5: Center-right (around login card)
  { x: 1140, y: 120, r: 2.5 },
  { x: 1220, y: 440, r: 3.5, hub: true },
  { x: 1120, y: 740, r: 3 },
  { x: 1240, y: 1000, r: 2.5 },

  // Band 6: Right column
  { x: 1380, y: 80, r: 3 },
  { x: 1460, y: 360, r: 3.5, hub: true },
  { x: 1360, y: 640, r: 2.5 },
  { x: 1440, y: 920, r: 3 },
  { x: 1580, y: 200, r: 3.5, hub: true },
  { x: 1640, y: 560, r: 2.5 },
  { x: 1560, y: 860, r: 3 },

  // Band 7: Far Right / bleed off-screen
  { x: 1760, y: -40, r: 2.5 },
  { x: 1840, y: 340, r: 3 },
  { x: 1780, y: 720, r: 2.5 },
  { x: 1860, y: 1060, r: 3 },
  { x: 2000, y: 140, r: 2.5 },
  { x: 1980, y: 560, r: 3 },
  { x: 2020, y: 920, r: 2.5 },
];

const TRACES: [number, number][] = [
  // Left bleed connections
  [0, 1], [1, 2], [3, 0], [0, 4], [4, 1], [1, 5], [5, 2], [2, 6],
  [3, 7], [4, 7], [4, 8], [5, 9], [6, 10],

  // Left column internal & bridge
  [7, 8], [8, 9], [9, 10],
  [7, 11], [8, 11], [8, 12], [9, 13], [10, 13],
  [11, 12], [12, 13],
  [11, 14], [11, 15], [12, 15], [12, 16], [13, 16], [13, 17],

  // Center-left to Center
  [14, 15], [15, 16], [16, 17],
  [14, 18], [14, 19], [15, 19], [15, 20], [16, 20], [16, 21], [17, 21], [17, 22],
  [18, 19], [19, 20], [20, 21], [21, 22],

  // Center to Center-right
  [18, 23], [19, 23], [19, 24], [20, 24], [20, 25], [21, 25], [21, 26], [22, 26],
  [23, 24], [24, 25], [25, 26],

  // Center-right to Right
  [23, 27], [24, 27], [24, 28], [25, 29], [25, 30], [26, 30],
  [27, 28], [28, 29], [29, 30],
  [27, 31], [28, 31], [28, 32], [29, 33], [30, 33],
  [31, 32], [32, 33],

  // Right to Far Right bleed
  [31, 34], [31, 35], [32, 35], [32, 36], [33, 36], [33, 37],
  [34, 35], [35, 36], [36, 37],
  [34, 38], [35, 38], [35, 39], [36, 39], [36, 40], [37, 40],
  [38, 39], [39, 40],
];

export function ProvenanceMotif({ className = "" }: { className?: string }) {
  return (
    <svg
      aria-hidden="true"
      focusable="false"
      viewBox="0 0 1920 1080"
      preserveAspectRatio="xMidYMid slice"
      className={className}
    >
      <defs>
        <radialGradient id="pv-motif-glow" cx="50%" cy="50%" r="70%">
          <stop offset="0%" stopColor="currentColor" stopOpacity="0.04" />
          <stop offset="70%" stopColor="currentColor" stopOpacity="0.01" />
          <stop offset="100%" stopColor="currentColor" stopOpacity="0" />
        </radialGradient>
      </defs>

      {/* Gentle center glow vignette */}
      <rect width="1920" height="1080" fill="url(#pv-motif-glow)" />

      {/* Line traces */}
      <g stroke="currentColor" strokeOpacity="0.10" strokeWidth="1">
        {TRACES.map(([from, to], index) => (
          <line
            key={index}
            className="pv-trace"
            style={{ animationDelay: `${-(index % 12) * 0.7}s` }}
            x1={NODES[from].x}
            y1={NODES[from].y}
            x2={NODES[to].x}
            y2={NODES[to].y}
          />
        ))}
      </g>

      {/* Standard nodes */}
      <g fill="currentColor" fillOpacity="0.22">
        {NODES.map((node, index) => (
          <circle
            key={index}
            className="pv-node"
            style={{
              animationDelay: `${-(index % 9) * 0.8}s`,
              animationDuration: `${8 + (index % 5)}s`,
            }}
            cx={node.x}
            cy={node.y}
            r={node.r}
          />
        ))}
      </g>

      {/* Evidence hub concentric pulse rings */}
      <g fill="none" stroke="currentColor" strokeOpacity="0.18" strokeWidth="1.2">
        {NODES.filter((n) => n.hub).map((node, index) => (
          <circle
            key={index}
            className="pv-hub-ring"
            style={{ animationDelay: `${-index * 1.4}s` }}
            cx={node.x}
            cy={node.y}
            r={node.r + 7}
          />
        ))}
      </g>
    </svg>
  );
}
