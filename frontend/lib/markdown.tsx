/**
 * Limited Markdown for CMS text (pages, FAQ answers, the deposit policy), rendered straight
 * to React elements — never through raw HTML — so stored content cannot inject markup.
 *
 * Blocks (separated by blank lines or by their own prefix):
 *   ## heading · ### sub-heading · - / * list item · 1. numbered item · > note · paragraph
 * Inline: **bold** and [text](url) where url is /internal, https://…, mailto: or tel:.
 */
import { Fragment, type ReactNode } from "react";

export type Block =
  | { type: "h2" | "h3" | "p" | "note"; text: string }
  | { type: "ul" | "ol"; items: string[] };

export function parseBlocks(source: string): Block[] {
  const blocks: Block[] = [];
  let paragraph: string[] = [];
  const flush = () => {
    if (paragraph.length) blocks.push({ type: "p", text: paragraph.join(" ") });
    paragraph = [];
  };
  for (const raw of source.replace(/\r\n?/g, "\n").split("\n")) {
    const line = raw.trim();
    const last = blocks.at(-1);
    let match: RegExpMatchArray | null;
    if (!line) {
      flush();
    } else if ((match = line.match(/^(#{2,3})\s+(.+)$/))) {
      flush();
      blocks.push({ type: match[1]!.length === 2 ? "h2" : "h3", text: match[2]! });
    } else if ((match = line.match(/^[-*]\s+(.+)$/))) {
      flush();
      if (last?.type === "ul" && !paragraph.length) last.items.push(match[1]!);
      else blocks.push({ type: "ul", items: [match[1]!] });
    } else if ((match = line.match(/^\d+[.)]\s+(.+)$/))) {
      flush();
      if (last?.type === "ol") last.items.push(match[1]!);
      else blocks.push({ type: "ol", items: [match[1]!] });
    } else if ((match = line.match(/^>\s?(.*)$/))) {
      flush();
      if (last?.type === "note") last.text += ` ${match[1]}`;
      else blocks.push({ type: "note", text: match[1]! });
    } else {
      paragraph.push(line);
    }
  }
  flush();
  // Consecutive list lines separated only by a blank line stay one list.
  return blocks.reduce<Block[]>((acc, block) => {
    const prev = acc.at(-1);
    if (prev && (prev.type === "ul" || prev.type === "ol") && prev.type === block.type && "items" in block) {
      prev.items.push(...block.items);
    } else acc.push(block);
    return acc;
  }, []);
}

export function safeHref(url: string): string | null {
  const value = url.trim();
  if (/^\/(?!\/)/.test(value) || /^https:\/\//i.test(value) || /^(mailto|tel):/i.test(value)) return value;
  return null;
}

const INLINE = /\*\*(.+?)\*\*|\[([^\]]+)\]\(([^)\s]+)\)/g;

export function renderInline(text: string, linkClass = "text-primary underline underline-offset-4 hover:text-secondary"): ReactNode[] {
  const out: ReactNode[] = [];
  let last = 0;
  let key = 0;
  for (const match of text.matchAll(INLINE)) {
    if (match.index! > last) out.push(text.slice(last, match.index));
    if (match[1] !== undefined) {
      out.push(<strong key={key++}>{match[1]}</strong>);
    } else {
      const href = safeHref(match[3]!);
      const external = href?.startsWith("https://");
      out.push(
        href ? (
          <a key={key++} href={href} className={linkClass} {...(external ? { target: "_blank", rel: "noopener noreferrer" } : {})}>
            {match[2]}
          </a>
        ) : (
          <Fragment key={key++}>{match[2]}</Fragment>
        ),
      );
    }
    last = match.index! + match[0].length;
  }
  if (last < text.length) out.push(text.slice(last));
  return out;
}

/** Renders CMS text with the platform's typography. */
export function Markdown({ source, className = "" }: { source: string; className?: string }) {
  return (
    <div className={`flex flex-col gap-4 leading-8 text-text ${className}`}>
      {parseBlocks(source).map((block, index) => {
        switch (block.type) {
          case "h2":
            return (
              <h2 key={index} className="mt-4 text-xl font-semibold text-primary">
                {renderInline(block.text)}
              </h2>
            );
          case "h3":
            return (
              <h3 key={index} className="mt-2 text-lg font-medium text-primary">
                {renderInline(block.text)}
              </h3>
            );
          case "note":
            return (
              <p key={index} className="rounded-[var(--radius-control)] border-s-4 border-secondary/60 bg-surface/60 px-4 py-2 text-sm text-muted">
                {renderInline(block.text)}
              </p>
            );
          case "ul":
          case "ol": {
            const List = block.type;
            return (
              <List key={index} className={`flex flex-col gap-2 ps-6 ${block.type === "ul" ? "list-disc" : "list-decimal"} marker:text-secondary`}>
                {block.items.map((item, i) => (
                  <li key={i}>{renderInline(item)}</li>
                ))}
              </List>
            );
          }
          default:
            return <p key={index}>{renderInline(block.text)}</p>;
        }
      })}
    </div>
  );
}
