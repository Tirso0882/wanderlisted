import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",

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
