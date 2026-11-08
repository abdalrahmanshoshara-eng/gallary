import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { Markdown, parseBlocks, safeHref } from "./markdown";

describe("parseBlocks", () => {
  it("reads headings, lists, notes and paragraphs", () => {
    const blocks = parseBlocks("مقدمة\nتكملة\n\n## عنوان\n- أ\n- ب\n\n- ج\n1. أول\n2. ثاني\n> ملاحظة");
    expect(blocks).toEqual([
      { type: "p", text: "مقدمة تكملة" },
      { type: "h2", text: "عنوان" },
      { type: "ul", items: ["أ", "ب", "ج"] },
      { type: "ol", items: ["أول", "ثاني"] },
      { type: "note", text: "ملاحظة" },
    ]);
  });
});

describe("safeHref", () => {
  it("allows internal, https, mailto and tel links only", () => {
    expect(safeHref("/faq")).toBe("/faq");
    expect(safeHref("https://wa.me/1")).toBe("https://wa.me/1");
    expect(safeHref("mailto:a@b.c")).toBe("mailto:a@b.c");
    expect(safeHref("javascript:alert(1)")).toBeNull();
    expect(safeHref("//evil.com")).toBeNull();
    expect(safeHref("http://plain.com")).toBeNull();
  });
});

describe("Markdown", () => {
  it("never renders raw HTML and drops unsafe links", () => {
    const { container } = render(
      <Markdown source={'<img src=x onerror="alert(1)"> **غامق** [سيئ](javascript:alert(1)) [جيد](https://example.com)'} />,
    );
    expect(container.querySelector("img")).toBeNull();
    expect(container.textContent).toContain('<img src=x onerror="alert(1)">');
    expect(container.querySelector("strong")?.textContent).toBe("غامق");
    const links = container.querySelectorAll("a");
    expect(links).toHaveLength(1);
    expect(links[0]!.getAttribute("href")).toBe("https://example.com");
    expect(links[0]!.getAttribute("rel")).toBe("noopener noreferrer");
  });
});
