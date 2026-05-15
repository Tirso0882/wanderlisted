"use client";

import { Avatar } from "@/components/ui/avatar";
import { Compass } from "lucide-react";

export function TypingIndicator() {
  return (
    <div className="mb-4 flex gap-3">
      <Avatar className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-muted text-muted-foreground">
        <Compass className="h-4 w-4" />
      </Avatar>
      <div className="flex items-center gap-1 rounded-2xl bg-muted px-4 py-3">
        <span className="h-2 w-2 animate-bounce rounded-full bg-muted-foreground/60 [animation-delay:-0.3s]" />
        <span className="h-2 w-2 animate-bounce rounded-full bg-muted-foreground/60 [animation-delay:-0.15s]" />
        <span className="h-2 w-2 animate-bounce rounded-full bg-muted-foreground/60" />
      </div>
    </div>
  );
}
