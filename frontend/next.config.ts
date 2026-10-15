import type { NextConfig } from "next";

// The browser only ever talks to this origin; /api/* is proxied to FastAPI.
// That keeps the session cookie first party and avoids CORS entirely.
// 127.0.0.1 rather than localhost: Node may resolve localhost to ::1 first, and
// an IPv6 listener on the same port (another app) would then answer instead.
const API_ORIGIN = process.env.API_ORIGIN ?? "http://127.0.0.1:8000";

const nextConfig: NextConfig = {
  output: "standalone",
  cacheComponents: true,
  partialPrefetching: true,
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
  async redirects() {
    // Older paths from the first version of the web app.
    return [
      { source: "/dashboard", destination: "/today", permanent: true },
      { source: "/history", destination: "/prescriptions", permanent: true },
      { source: "/scans/:id", destination: "/prescriptions/:id", permanent: true },
    ];
  },
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${API_ORIGIN}/api/:path*` }];
  },
};

export default nextConfig;
