import { useCallback, useRef, useState } from "react";
import { useApp } from "../context/AppContext";
import { api } from "../services/api";
import type { AssistantAction, AssistantMessage } from "../types";
import { buildAssistantContext } from "../utils/assistantContext";

/** An action awaiting the user's yes/no. */
export interface PendingAction {
  action: AssistantAction;
  /** The question that produced it, replayed on confirmation. */
  question: string;
}

const HISTORY_LIMIT = 14;

/**
 * Shared chat behaviour for both assistant surfaces.
 *
 * Actions are the interesting part: the backend validates them and hands them
 * back as data, this hook runs them against the app's real controls, and the
 * genuine outcome - success or failure - is reported back so the conversation
 * never claims something worked when it did not.
 */
export function useAssistantChat() {
  const app = useApp();
  const [busy, setBusy] = useState(false);
  const [pending, setPending] = useState<PendingAction[]>([]);
  // Actions run one after another, and some must finish before the next starts
  // (opening the forecast page before setting its horizon).
  const queue = useRef<Promise<unknown>>(Promise.resolve());

  const runActions = useCallback(
    (actions: AssistantAction[]): Promise<string[]> => {
      const next = queue.current.then(async () => {
        const outcomes: string[] = [];
        for (const action of actions) {
          const result = await app.runAssistantAction(action.type, action.params);
          try {
            const res = await api.assistantActionResult({
              action_id: action.id,
              type: action.label,
              success: result.success,
              message: result.message,
            });
            outcomes.push(res.answer);
          } catch {
            // The action still ran; a failed status report must not hide that.
            outcomes.push(result.success ? `Done - ${result.message}` : result.message);
          }
        }
        return outcomes;
      });
      queue.current = next.catch(() => undefined);
      return next;
    },
    [app],
  );

  const pushAssistant = useCallback(
    (content: string, extra?: Partial<{ actions: AssistantAction[]; warnings: string[] }>) => {
      app.setAssistantMessages((m) => [
        ...m,
        { role: "assistant", content, ...extra },
      ]);
    },
    [app],
  );

  const send = useCallback(
    async (text: string) => {
      const question = text.trim();
      if (!question || busy) return;
      app.setAssistantMessages((m) => [...m, { role: "user", content: question }]);
      setBusy(true);
      setPending([]);
      try {
        const history: AssistantMessage[] = app.assistantMessages
          .slice(-HISTORY_LIMIT)
          .map((m) => ({ role: m.role, content: m.content }));
        const res = await api.assistantChat({
          question,
          history,
          horizon_hours: app.seaIceHorizon,
          dashboard: buildAssistantContext(app),
        });

        const immediate = res.actions.filter((a) => !a.needs_confirmation);
        const needsConfirm = res.actions.filter((a) => a.needs_confirmation);

        let content = res.answer;
        if (immediate.length) {
          const outcomes = await runActions(immediate);
          content = `${content}\n\n${outcomes.join(" ")}`.trim();
        }
        pushAssistant(content, {
          actions: res.actions,
          warnings: res.warnings,
        });
        if (needsConfirm.length) {
          setPending(needsConfirm.map((action) => ({ action, question })));
        }
      } catch (e) {
        const msg = e instanceof Error ? e.message : String(e);
        pushAssistant(
          `I hit an error while querying the backend: ${msg}. Try again, or check that the API server is running.`,
        );
        app.toast("Assistant could not reach the backend", "error");
      } finally {
        setBusy(false);
      }
    },
    [app, busy, pushAssistant, runActions],
  );

  const confirm = useCallback(
    async (pendingAction: PendingAction) => {
      setBusy(true);
      try {
        const res = await api.assistantChat({
          question: pendingAction.question,
          history: app.assistantMessages
            .slice(-HISTORY_LIMIT)
            .map((m) => ({ role: m.role, content: m.content })),
          horizon_hours: app.seaIceHorizon,
          dashboard: buildAssistantContext(app),
          confirm_action_id: pendingAction.action.id,
        });
        if (!res.actions.length) {
          pushAssistant(res.answer);
          return;
        }
        const outcomes = await runActions(res.actions);
        pushAssistant(`${res.answer} ${outcomes.join(" ")}`.trim());
      } catch (e) {
        pushAssistant(
          `I couldn't complete that: ${e instanceof Error ? e.message : String(e)}`,
        );
      } finally {
        setPending((p) => p.filter((x) => x.action.id !== pendingAction.action.id));
        setBusy(false);
      }
    },
    [app, pushAssistant, runActions],
  );

  const cancel = useCallback(
    async (pendingAction: PendingAction) => {
      setPending((p) => p.filter((x) => x.action.id !== pendingAction.action.id));
      setBusy(true);
      try {
        await api.assistantChat({
          question: pendingAction.question,
          history: [],
          horizon_hours: app.seaIceHorizon,
          dashboard: buildAssistantContext(app),
          denied_action_ids: [pendingAction.action.id],
        });
      } catch {
        // Cancelling is local; a failed round trip must not block the user.
      } finally {
        setBusy(false);
      }
    },
    [app],
  );

  return { send, confirm, cancel, pending, busy };
}
