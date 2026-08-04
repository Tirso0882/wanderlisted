import { TopBar } from "@/components/layout";

export default function ChatLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  if (process.env.CHAT_UI_V2_ENABLED?.trim().toLowerCase() === "true") {
    return children;
  }
  return (
    <div className="flex h-screen flex-col overflow-hidden">
      <TopBar />
      <main className="flex flex-1 min-h-0 overflow-hidden">{children}</main>
    </div>
  );
}
