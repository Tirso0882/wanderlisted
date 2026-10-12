"use client";

import { ArrowLeft, ArrowRight } from "lucide-react";
import { usePathname, useRouter } from "next/navigation";
import { useCallback, useEffect } from "react";

export const PROTOTYPE_VARIANTS = {
  A: "Command centre",
  B: "Conversation cockpit",
  C: "Trip studio",
} as const;

export type PrototypeVariant = keyof typeof PROTOTYPE_VARIANTS;

const VARIANT_KEYS = Object.keys(PROTOTYPE_VARIANTS) as PrototypeVariant[];

export function PrototypeSwitcher({ current }: { current: PrototypeVariant }) {
  const pathname = usePathname();
  const router = useRouter();

  const select = useCallback(
    (offset: number) => {
      const currentIndex = VARIANT_KEYS.indexOf(current);
      const nextIndex = (currentIndex + offset + VARIANT_KEYS.length) % VARIANT_KEYS.length;
      router.replace(`${pathname}?variant=${VARIANT_KEYS[nextIndex]}`, { scroll: false });
    },
    [current, pathname, router],
  );

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement | null;
      if (
        target?.matches("input, textarea, select, [contenteditable='true']") ||
        (event.key !== "ArrowLeft" && event.key !== "ArrowRight")
      ) {
        return;
      }
      event.preventDefault();
      select(event.key === "ArrowLeft" ? -1 : 1);
    };

    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [select]);

  if (process.env.NODE_ENV === "production") return null;

  return (
    <nav className="atlas-prototype-switcher" aria-label="UI prototype variants">
      <button type="button" onClick={() => select(-1)} aria-label="Previous variant">
        <ArrowLeft />
      </button>
      <span>
        <strong>{current}</strong>
        {PROTOTYPE_VARIANTS[current]}
      </span>
      <button type="button" onClick={() => select(1)} aria-label="Next variant">
        <ArrowRight />
      </button>
    </nav>
  );
}
