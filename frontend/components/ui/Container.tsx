import type { ComponentPropsWithoutRef, ElementType } from "react";

type ContainerProps<T extends ElementType> = {
  as?: T;
} & Omit<ComponentPropsWithoutRef<T>, "as">;

/** Centred page container using the shared max width and gutters from the design tokens. */
export function Container<T extends ElementType = "div">({ as, className, ...props }: ContainerProps<T>) {
  const Component: ElementType = as ?? "div";
  return (
    <Component
      className={["mx-auto w-full max-w-[var(--container-max)] px-[var(--gutter)]", className]
        .filter(Boolean)
        .join(" ")}
      {...props}
    />
  );
}
