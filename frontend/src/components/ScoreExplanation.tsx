export function ScoreExplanation({ score, weights }: { score: number; weights: number[] }) {
  const sum = weights.reduce((total, weight) => total + weight, 0);
  return <p className="mt-1.5 text-xs text-ink3">{sum === score
    ? `Declared factors total ${sum}/100. Deterministic rule support, not a calibrated probability.`
    : `Historical score ${score}/100 differs from declared factors (${sum}). Regenerate under current rules before relying on this score.`}</p>;
}
