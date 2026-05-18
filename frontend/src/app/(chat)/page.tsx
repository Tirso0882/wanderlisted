"use client";

import { motion, AnimatePresence } from "framer-motion";
import { useChatStore } from "@/stores/chat-store";
import { HomeView } from "@/components/views/home-view";
import { AgentView } from "@/components/views/agent-view";
import { HitlGateRenderer } from "@/components/hitl/hitl-gate-renderer";

export default function ChatPage() {
  const activeView = useChatStore((s) => s.activeView);
  const interruptData = useChatStore((s) => s.interruptData);

  if (interruptData) {
    return <HitlGateRenderer />;
  }

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
