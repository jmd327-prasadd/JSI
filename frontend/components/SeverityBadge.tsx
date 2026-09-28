export function SeverityBadge({ severity }: { severity: string }) {
  return <span className={`badge severity-${severity}`}>{severity}</span>;
}
