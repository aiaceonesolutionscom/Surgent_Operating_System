import type { LucideIcon } from "lucide-react";
import { Button } from "../../../components/ui";

interface EmptyStateProps {
  icon: LucideIcon;
  title: string;
  body: string;
  action?: {
    label: string;
    onClick: () => void;
    variant?: "primary" | "cream" | "ghost";
  };
  illustration?: "default" | "illustrated";
}

export function EmptyState({ icon: Icon, title, body, action, illustration = "default" }: EmptyStateProps) {
  if (illustration === "illustrated") {
    return (
      <div className="flex flex-col items-center justify-center px-6 py-16 text-center">
        <div className="relative">
          <div className="absolute -inset-4 bg-gradient-to-r from-teal-500/10 to-teal-300/10 rounded-full blur-2xl" />
          <span className="relative flex h-16 w-16 items-center justify-center rounded-2xl bg-teal-500/10 text-teal-600">
            <Icon className="h-7 w-7" />
          </span>
        </div>
        <p className="mt-5 text-base font-semibold text-ink">{title}</p>
        <p className="mt-2 max-w-sm text-sm text-ink-muted">{body}</p>
        {action && (
          <Button
            variant={action.variant || "primary"}
            size="sm"
            onClick={action.onClick}
            className="mt-5"
          >
            {action.label}
          </Button>
        )}
      </div>
    );
  }

  return (
    <div className="flex flex-col items-center justify-center px-6 py-12 text-center">
      <span className="flex h-12 w-12 items-center justify-center rounded-xl bg-sand-100 text-sand-600">
        <Icon className="h-5 w-5" />
      </span>
      <p className="mt-3 text-sm font-semibold text-ink">{title}</p>
      <p className="mt-1 max-w-xs text-sm text-ink-muted">{body}</p>
      {action && (
        <Button
          variant={action.variant || "primary"}
          size="sm"
          onClick={action.onClick}
          className="mt-4"
        >
          {action.label}
        </Button>
      )}
    </div>
  );
}