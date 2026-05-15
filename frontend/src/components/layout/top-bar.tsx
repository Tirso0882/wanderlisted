"use client";

import { Compass, PlusCircle, Menu, X, FlaskConical } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { ThemeToggle } from "./theme-toggle";
import { useChatStore } from "@/stores/chat-store";
import { useState } from "react";

export function TopBar() {
  const clearChat = useChatStore((s) => s.clearChat);
  const loadMockData = useChatStore((s) => s.loadMockData);
  const isMockMode = useChatStore((s) => s.isMockMode);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  return (
    <header className="sticky top-0 z-40 flex h-14 items-center gap-3 border-b bg-background/80 px-4 backdrop-blur-sm">
      {/* Mobile menu toggle */}
      <Button
        variant="ghost"
        size="icon"
        className="md:hidden"
        onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
        aria-label="Toggle menu"
      >
        {mobileMenuOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
      </Button>

      {/* Logo */}
      <div className="flex items-center gap-2">
        <Compass className="h-6 w-6 text-primary" />
        <span className="text-lg font-semibold tracking-tight">Wanderlisted</span>
      </div>

      {/* Mock mode indicator */}
      {isMockMode && (
        <Badge variant="secondary" className="gap-1 text-xs">
          <FlaskConical className="h-3 w-3" />
          Demo Data
        </Badge>
      )}

      {/* Spacer */}
      <div className="flex-1" />

      {/* Actions */}
      {!isMockMode && (
        <Button
          variant="outline"
          size="sm"
          onClick={() => loadMockData()}
          className="gap-1.5 text-xs"
        >
          <FlaskConical className="h-3.5 w-3.5" />
          <span className="hidden sm:inline">Load Demo</span>
        </Button>
      )}

      <Button
        variant="ghost"
        size="sm"
        onClick={clearChat}
        className="gap-1.5 text-muted-foreground hover:text-foreground"
      >
        <PlusCircle className="h-4 w-4" />
        <span className="hidden sm:inline">New Trip</span>
      </Button>

      <ThemeToggle />
    </header>
  );
}
