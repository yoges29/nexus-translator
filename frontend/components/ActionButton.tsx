interface ActionButtonProps {
  label: string;
  onClick: () => void;
  disabled?: boolean;
  confirmLabel?: string;
  showConfirm?: boolean;
}

export function ActionButton({
  label,
  onClick,
  disabled,
  confirmLabel,
  showConfirm,
}: ActionButtonProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className="inline-flex items-center gap-1 rounded-lg border border-nexus-border bg-nexus-surface px-3 py-1.5 text-xs font-medium uppercase tracking-wide text-nexus-muted transition hover:border-nexus-accent hover:text-nexus-accent focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-nexus-accent disabled:cursor-not-allowed disabled:opacity-40"
      aria-label={label}
    >
      {showConfirm && confirmLabel ? confirmLabel : label}
    </button>
  );
}
