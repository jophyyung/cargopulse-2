import { cn } from "@/lib/utils";

/**
 * Solid Chart Slate surface with a hairline border. The heading strip is
 * separated from the body by a hairline, like a strip on a planning board.
 */
export function Panel({
  title,
  aside,
  children,
  className,
  flush = false,
  as: Heading = "h2",
}: {
  title?: React.ReactNode;
  aside?: React.ReactNode;
  children: React.ReactNode;
  className?: string;
  /** Remove body padding, for full-bleed tables and charts. */
  flush?: boolean;
  as?: "h2" | "h3";
}) {
  return (
    <section className={cn("panel", className)}>
      {title || aside ? (
        <div className="section-heading">
          {title ? <Heading>{title}</Heading> : <span />}
          {aside}
        </div>
      ) : null}
      <div className={cn("panel-body", flush && "flush")}>{children}</div>
    </section>
  );
}
