import { cn } from "@/lib/utils";

export function AtlasLogo({ className }: { className?: string }) {
  return (
    <div className={cn("flex items-center gap-2.5", className)}>
      <span className="atlas-mark" aria-hidden="true">
        <svg viewBox="0 0 42 42" role="presentation">
          <circle cx="21" cy="21" r="19" fill="currentColor" />
          <path
            d="M9 27c6-13 14-14 24-14M12 30c8 1 14-3 19-12"
            fill="none"
            stroke="white"
            strokeWidth="2.3"
            strokeLinecap="round"
            strokeDasharray="3.8 3.8"
          />
          <circle cx="10" cy="27" r="2.4" fill="#f47b5f" />
          <circle cx="32" cy="13" r="2.4" fill="#7bc8b9" />
        </svg>
      </span>
      <span>
        <span className="block text-[1.05rem] font-extrabold leading-none tracking-[-0.035em] text-[var(--atlas-navy)]">
          Wanderlisted
        </span>
        <span className="mt-1 block text-[0.61rem] font-semibold uppercase tracking-[0.18em] text-[var(--atlas-teal-dark)]">
          Atlas Sunrise
        </span>
      </span>
    </div>
  );
}
