import { TopBar } from "@/components/layout";

export default function ChatLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="flex h-screen flex-col overflow-hidden">
      <TopBar />
      <main className="flex flex-1 min-h-0 overflow-hidden">{children}</main>
    </div>
  );
}
