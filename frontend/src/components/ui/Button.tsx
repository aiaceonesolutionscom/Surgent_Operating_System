import React from "react";
import { Link } from "react-router-dom";
import { ArrowRightIcon, Loader2Icon } from "lucide-react";

type ButtonVariant = "primary" | "cream" | "outline-dark" | "ghost" | "ink" | "danger";
type ButtonSize = "sm" | "md" | "lg";

const VARIANT_CLASSES: Record<ButtonVariant, string> = {
  primary: "bg-teal-600 text-white hover:bg-teal-700 focus:ring-2 focus:ring-teal-500/50",
  cream: "bg-teal-300 text-ink hover:bg-white focus:ring-2 focus:ring-teal-400/50",
  "outline-dark": "border border-white/20 text-white hover:bg-white/10 focus:ring-2 focus:ring-white/30",
  ghost: "text-ink transition-colors hover:text-teal-600 focus:ring-2 focus:ring-teal-500/50",
  ink: "bg-ink text-white hover:bg-teal-600 focus:ring-2 focus:ring-teal-500/50",
  danger: "bg-red-600 text-white hover:bg-red-700 focus:ring-2 focus:ring-red-500/50",
};

const SIZE_CLASSES: Record<ButtonSize, string> = {
  sm: "gap-2 px-5 py-2.5 text-sm",
  md: "gap-2 px-7 py-3.5 text-base",
  lg: "gap-2.5 px-8 py-4 text-base",
};

interface ButtonProps {
  children: React.ReactNode;
  variant?: ButtonVariant;
  size?: ButtonSize;
  arrow?: boolean;
  loading?: boolean;
  disabled?: boolean;
  className?: string;
  to?: string;
  href?: string;
  onClick?: () => void;
  type?: "button" | "submit" | "reset";
}

export function Button({
  children,
  variant = "primary",
  size = "md",
  arrow = false,
  loading = false,
  disabled = false,
  className = "",
  to,
  href,
  onClick,
  type = "button"
}: ButtonProps) {
  const isDisabled = disabled || loading;
  const classes = `group inline-flex items-center justify-center rounded-full font-semibold transition-all disabled:opacity-50 disabled:cursor-not-allowed ${VARIANT_CLASSES[variant]} ${SIZE_CLASSES[size]} ${className}`;
  const content = (
    <>
      {loading && <Loader2Icon className="h-4.5 w-4.5 animate-spin" />}
      {!loading && children}
      {arrow && !loading && <ArrowRightIcon className="h-4.5 w-4.5 transition-transform group-hover:translate-x-1" />}
    </>
  );

  if (to) {
    return (
      <Link to={to} onClick={onClick} className={classes} aria-disabled={isDisabled}>
        {content}
      </Link>
    );
  }
  if (href) {
    return (
      <a href={href} onClick={onClick} className={classes} aria-disabled={isDisabled}>
        {content}
      </a>
    );
  }
  return (
    <button type={type} onClick={onClick} disabled={isDisabled} className={classes} aria-busy={loading}>
      {content}
    </button>
  );
}