import { Slot } from "radix-ui";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

// Variants resolve to the shared `.button` classes in globals.css so that
// component buttons and plain `<button className="button">` markup stay identical.
const buttonVariants = cva("button", {
  variants: {
    variant: {
      primary: "primary",
      secondary: "",
      danger: "danger",
      quiet: "ghost",
    },
    size: { md: "", sm: "small" },
    wide: { true: "wide", false: "" },
  },
  defaultVariants: { variant: "secondary", size: "md", wide: false },
});

export function Button({
  className,
  variant,
  size,
  wide,
  asChild = false,
  ...props
}: React.ComponentProps<"button"> &
  VariantProps<typeof buttonVariants> & { asChild?: boolean }) {
  const Component = asChild ? Slot.Root : "button";
  return <Component className={cn(buttonVariants({ variant, size, wide }), className)} {...props} />;
}

export { buttonVariants };
