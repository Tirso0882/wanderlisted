"use client";

import { motion } from "framer-motion";
import {
  Plane,
  Hotel,
  MapPin,
  Compass,
  Utensils,
  Bus,
  DollarSign,
  ClipboardList,
  Sparkles,
  type LucideIcon,
} from "lucide-react";
import { ChatInput } from "@/components/chat/chat-input";
import { useChatStore, type ViewMode } from "@/stores/chat-store";

interface AgentCard {
  id: ViewMode;
  icon: LucideIcon;
  label: string;
  description: string;
  gradient: string;
  example: string;
}

const AGENT_CARDS: AgentCard[] = [
  {
    id: "flights",
    icon: Plane,
    label: "Flights",
    description: "Search and compare flights",
    gradient: "from-blue-500/10 to-sky-500/5",
    example: "Find flights from NYC to Tokyo in March",
  },
  {
    id: "hotels",
    icon: Hotel,
    label: "Hotels",
    description: "Find perfect accommodation",
    gradient: "from-amber-500/10 to-orange-500/5",
    example: "Luxury hotels in Paris near the Eiffel Tower",
  },
  {
    id: "destination",
    icon: MapPin,
    label: "Destination",
    description: "City guides & travel info",
    gradient: "from-emerald-500/10 to-green-500/5",
    example: "Tell me about visiting Barcelona in summer",
  },
  {
    id: "activities",
    icon: Compass,
    label: "Activities",
    description: "Things to do & attractions",
    gradient: "from-purple-500/10 to-violet-500/5",
    example: "Top activities for families in London",
  },
  {
    id: "restaurants",
    icon: Utensils,
    label: "Restaurants",
    description: "Food & dining spots",
    gradient: "from-rose-500/10 to-pink-500/5",
    example: "Best sushi restaurants in Tokyo",
  },
  {
    id: "transport",
    icon: Bus,
    label: "Transport",
    description: "Getting around your destination",
    gradient: "from-teal-500/10 to-cyan-500/5",
    example: "How to get from airport to city center in Rome",
  },
  {
    id: "budget",
    icon: DollarSign,
    label: "Budget",
    description: "Cost estimation & planning",
    gradient: "from-lime-500/10 to-green-500/5",
    example: "Budget breakdown for 7 days in Thailand",
  },
  {
    id: "itinerary",
    icon: ClipboardList,
    label: "Itinerary",
    description: "Day-by-day trip planning",
    gradient: "from-indigo-500/10 to-blue-500/5",
    example: "Create a 5-day itinerary for Kyoto",
  },
];

const container = {
  hidden: { opacity: 0 },
  show: {
    opacity: 1,
    transition: { staggerChildren: 0.05 },
  },
};

const item = {
  hidden: { opacity: 0, y: 20 },
  show: { opacity: 1, y: 0 },
};

export function HomeView() {
  const sendMessage = useChatStore((s) => s.sendMessage);
  const setActiveView = useChatStore((s) => s.setActiveView);

  return (
    <div className="flex flex-1 flex-col items-center justify-center px-4 py-8">
      {/* Hero */}
      <motion.div
        initial={{ opacity: 0, y: -10 }}
        animate={{ opacity: 1, y: 0 }}
        className="mb-8 text-center"
      >
        <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-2xl bg-gradient-to-br from-primary/20 to-primary/5">
          <Sparkles className="h-7 w-7 text-primary" />
        </div>
        <h1 className="text-3xl font-bold tracking-tight">
          Where to next?
        </h1>
        <p className="mt-2 text-muted-foreground max-w-md mx-auto">
          Ask me anything about travel — or pick a category below to get started with a specific agent.
        </p>
      </motion.div>

      {/* Central input */}
      <motion.div
        initial={{ opacity: 0, scale: 0.98 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={{ delay: 0.1 }}
        className="w-full max-w-2xl mb-10"
      >
        <ChatInput variant="hero" />
      </motion.div>

      {/* Agent category grid */}
      <motion.div
        variants={container}
        initial="hidden"
        animate="show"
        className="grid w-full max-w-4xl gap-3 sm:grid-cols-2 lg:grid-cols-4"
      >
        {AGENT_CARDS.map((card) => {
          const Icon = card.icon;
          return (
            <motion.button
              key={card.id}
              variants={item}
              onClick={() => {
                setActiveView(card.id);
                sendMessage(card.example);
              }}
              className={`group relative flex flex-col items-start gap-2 rounded-xl border bg-gradient-to-br ${card.gradient} p-4 text-left transition-all hover:shadow-md hover:border-primary/30 hover:-translate-y-0.5`}
            >
              <div className="flex items-center gap-2">
                <Icon className="h-5 w-5 text-foreground/70 group-hover:text-primary transition-colors" />
                <span className="font-medium text-sm">{card.label}</span>
              </div>
              <p className="text-xs text-muted-foreground leading-relaxed">
                {card.description}
              </p>
            </motion.button>
          );
        })}
      </motion.div>
    </div>
  );
}
