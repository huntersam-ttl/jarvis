/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${process.env.JARVIS_BACKEND_URL || "http://127.0.0.1:8000"}/api/:path*`,
      },
      {
        source: "/health",
        destination: `${process.env.JARVIS_BACKEND_URL || "http://127.0.0.1:8000"}/health`,
      },
    ];
  },
};

export default nextConfig;
