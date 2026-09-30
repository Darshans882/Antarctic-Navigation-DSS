import type { PendingAction } from "../../hooks/useAssistantChat";

interface Props {
  pending: PendingAction[];
  busy: boolean;
  onConfirm: (pending: PendingAction) => void;
  onCancel: (pending: PendingAction) => void;
}

/**
 * Confirm/Cancel controls for an action that changes what the user actually
 * sails. Nothing happens until they choose, and the outcome they see afterwards
 * is the real result reported by the application.
 */
export function ActionConfirmations({ pending, busy, onConfirm, onCancel }: Props) {
  if (!pending.length) return null;
  return (
    <div className="mt-2 space-y-2">
      {pending.map((item) => (
        <div
          key={item.action.id}
          className="rounded-lg border border-amber-300 bg-amber-50 p-3 text-xs text-navy-800"
        >
          <p className="font-medium text-navy-900">
            {item.action.confirmation_prompt ?? item.action.label}
          </p>
          <div className="mt-2 flex gap-2">
            <button
              type="button"
              disabled={busy}
              onClick={() => onConfirm(item)}
              className="rounded-md bg-navy-700 px-3 py-1.5 font-medium text-white transition hover:bg-navy-800 disabled:cursor-not-allowed disabled:opacity-50"
            >
              Confirm
            </button>
            <button
              type="button"
              disabled={busy}
              onClick={() => onCancel(item)}
              className="rounded-md border border-navy-300 bg-white px-3 py-1.5 font-medium text-navy-700 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50"
            >
              Cancel
            </button>
          </div>
        </div>
      ))}
    </div>
  );
}
