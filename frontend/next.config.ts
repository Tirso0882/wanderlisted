import type { NextConfig } from "next";

const API_URL = process.env.API_URL ?? "http://localhost:8000";

const nextConfig: NextConfig = {
  // Proxy API calls to the FastAPI backend in dev
  async rewrites() {
    return [
      {
        source: "/api/v1/:path*",
        destination: `${API_URL}/api/v1/:path*`,
      },
    ];
  },

  // Allow hotel/place images from external sources
  images: {
    remotePatterns: [
      { protocol: "https", hostname: "**.googleapis.com" },
      { protocol: "https", hostname: "**.booking.com" },
      { protocol: "https", hostname: "**.hotelbeds.com" },
    ],
  },
};

export default nextConfig;
