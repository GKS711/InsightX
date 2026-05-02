interface Props {
  status: string;
}

export function StatusPill({ status }: Props) {
  const cls =
    status === "succeeded"
      ? "pill pill-success"
      : status === "failed"
      ? "pill pill-error"
      : status === "running" || status === "queued"
      ? "pill pill-running"
      : "pill";
  return <span className={cls}>{status}</span>;
}
