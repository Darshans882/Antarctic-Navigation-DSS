import type { ReactNode } from "react";

/**
 * Renders the assistant's message text.
 *
 * The backend writes in markdown - bold lead-ins, inline file paths, numbered
 * steps and the occasional code block - and this used to be printed raw, so
 * the chat showed literal `**stars**` and backticks. That reads like a debug
 * dump rather than a person talking to you.
 *
 * This is deliberately a tiny hand-rolled renderer for exactly the subset the
 * assistant emits, rather than pulling in a markdown library for it. Anything
 * it doesn't recognise is left as plain text, so no answer can fail to render.
 */

const INLINE_RE = /(\*\*[^*]+\*\*|`[^`\n]+`)/g;
const FENCE_RE = /```[a-z]*\n?([\s\S]*?)```/g;
const BULLET_RE = /^\s*[-*]\s+/;
const NUMBERED_RE = /^\s*(\d+)[.)]\s+/;

function renderInline(text: string, keyPrefix: string): ReactNode[] {
  return text.split(INLINE_RE).map((part, i) => {
    const key = `${keyPrefix}:${i}`;
    if (part.length > 4 && part.startsWith("**") && part.endsWith("**")) {
      return (
        <strong key={key} className="font-semibold text-navy-900">
          {part.slice(2, -2)}
        </strong>
      );
    }
    if (part.length > 2 && part.startsWith("`") && part.endsWith("`")) {
      return (
        <code
          key={key}
          className="px-1 py-[1px] rounded bg-slate-200/80 font-mono text-[10.5px] text-navy-800"
        >
          {part.slice(1, -1)}
        </code>
      );
    }
    return <span key={key}>{part}</span>;
  });
}

function renderBlocks(text: string, keyPrefix: string): ReactNode[] {
  const out: ReactNode[] = [];
  const lines = text.split("\n");
  let paragraph: string[] = [];
  let list: { ordered: boolean; items: string[] } | null = null;

  const flushParagraph = () => {
    if (!paragraph.length) return;
    const joined = paragraph.join(" ").trim();
    if (joined) {
      out.push(
        <p key={`${keyPrefix}:p${out.length}`} className="whitespace-pre-wrap">
          {renderInline(joined, `${keyPrefix}:p${out.length}`)}
        </p>,
      );
    }
    paragraph = [];
  };

  const flushList = () => {
    if (!list) return;
    const items = list.items.map((item, i) => (
      <li key={`${keyPrefix}:li${i}`} className="leading-relaxed">
        {renderInline(item, `${keyPrefix}:li${i}`)}
      </li>
    ));
    out.push(
      list.ordered ? (
        <ol
          key={`${keyPrefix}:l${out.length}`}
          className="my-1 ml-4 list-decimal space-y-1 marker:text-navy-400"
        >
          {items}
        </ol>
      ) : (
        <ul
          key={`${keyPrefix}:l${out.length}`}
          className="my-1 ml-4 list-disc space-y-1 marker:text-navy-400"
        >
          {items}
        </ul>
      ),
    );
    list = null;
  };

  for (const raw of lines) {
    const line = raw.trimEnd();
    if (!line.trim()) {
      flushParagraph();
      flushList();
      continue;
    }
    const numbered = NUMBERED_RE.exec(line);
    const bullet = BULLET_RE.exec(line);
    if (numbered || bullet) {
      flushParagraph();
      const ordered = Boolean(numbered);
      const item = ordered
        ? line.slice(numbered![0].length)
        : line.slice(bullet![0].length);
      if (!list || list.ordered !== ordered) {
        flushList();
        list = { ordered, items: [] };
      }
      list.items.push(item);
      continue;
    }
    flushList();
    paragraph.push(line.trim());
  }

  flushParagraph();
  flushList();
  return out;
}

export function MessageContent({ text }: { text: string }) {
  const segments = text.split(FENCE_RE);
  // split() with a capture group yields [before, code, between, code, ...]
  const nodes: ReactNode[] = [];
  segments.forEach((segment, i) => {
    if (!segment) return;
    if (i % 2 === 1) {
      nodes.push(
        <pre
          key={`code${i}`}
          className="my-2 overflow-x-auto rounded-lg bg-slate-900 px-3 py-2 text-[10.5px] leading-relaxed text-slate-100"
        >
          <code>{segment.replace(/\n$/, "")}</code>
        </pre>,
      );
      return;
    }
    nodes.push(...renderBlocks(segment, `s${i}`));
  });
  return <div className="space-y-1.5">{nodes}</div>;
}
