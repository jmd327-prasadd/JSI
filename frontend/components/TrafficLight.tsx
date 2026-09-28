export function TrafficLight({ color, label }: { color: "Red" | "Amber" | "Green"; label: string }) {
  return (
    <span className="traffic-light">
      <span className={`dot ${color}`} />
      {label}
    </span>
  );
}
