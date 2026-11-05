"use client";

import { useEffect, useRef, type ReactNode } from "react";

import { Button } from "./Button";

type Props = {
  open: boolean;
  title: string;
  children?: ReactNode;
  confirmLabel: string;
  cancelLabel: string;
  onConfirm: () => void;
  onCancel: () => void;
  busy?: boolean;
};

/** Native <dialog>: focus trap, Esc to close and focus return come from the browser. */
export function ConfirmDialog({ open, title, children, confirmLabel, cancelLabel, onConfirm, onCancel, busy }: Props) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const dialog = ref.current;
    if (!dialog) return;
    if (open && !dialog.open) dialog.showModal();
    if (!open && dialog.open) dialog.close();
  }, [open]);
  return (
    <dialog
      ref={ref}
      onCancel={(e) => {
        e.preventDefault();
        if (!busy) onCancel();
      }}
      aria-labelledby="confirm-title"
      className="m-auto w-[min(28rem,calc(100vw-2rem))] rounded-[var(--radius-card)] bg-white p-6 text-text shadow-xl backdrop:bg-text/40"
    >
      <h2 id="confirm-title" className="text-lg font-medium text-primary">
        {title}
      </h2>
      {children ? <div className="mt-3 text-sm text-muted">{children}</div> : null}
      <div className="mt-6 flex flex-wrap justify-end gap-3">
        <Button variant="ghost" onClick={onCancel} disabled={busy}>
          {cancelLabel}
        </Button>
        <Button variant="primary" loading={busy} onClick={onConfirm}>
          {confirmLabel}
        </Button>
      </div>
    </dialog>
  );
}
