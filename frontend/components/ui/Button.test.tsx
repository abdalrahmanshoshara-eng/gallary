import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { Button } from "./Button";

describe("Button", () => {
  it("defaults to type=button so it never submits forms by accident", () => {
    render(<Button>حفظ</Button>);
    expect(screen.getByRole("button", { name: "حفظ" })).toHaveAttribute("type", "button");
  });

  it("blocks clicks while loading and exposes the busy state", () => {
    const onClick = vi.fn();
    render(
      <Button loading onClick={onClick}>
        حجز
      </Button>,
    );
    const button = screen.getByRole("button", { name: "حجز" });
    fireEvent.click(button);
    expect(onClick).not.toHaveBeenCalled();
    expect(button).toBeDisabled();
    expect(button).toHaveAttribute("aria-busy", "true");
  });
});
