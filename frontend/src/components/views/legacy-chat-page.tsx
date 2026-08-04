"use client";

import { AnimatePresence, motion } from "framer-motion";
import { HitlGateRenderer } from "@/components/hitl/hitl-gate-renderer";
import { AgentView } from "@/components/views/agent-view";
import { HomeView } from "@/components/views/home-view";
import { useChatStore } from "@/stores/chat-store";

export function LegacyChatPage() {
  const activeView = useChatStore((state) => state.activeView);
  const interruptData = useChatStore((state) => state.interruptData);

  if (interruptData) return <HitlGateRenderer />;

  return (
    <AnimatePresence mode="wait">
      {activeView === "home" ? (
        <motion.div
          key="home"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0, y: -20 }}
          transition={{ duration: 0.2 }}
          className="flex flex-1 flex-col overflow-hidden"
        >
          <HomeView />
        </motion.div>
      ) : (
        <motion.div
          key={activeView}
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -20 }}
          transition={{ duration: 0.25 }}
          className="flex flex-1 flex-col overflow-hidden"
        >
          <AgentView />
        </motion.div>
      )}
    </AnimatePresence>
  );
}
