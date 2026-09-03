/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  async rewrites() {
    // Local dev only: proxy /api/* to a locally-running api_handler server
    // (see scripts/serve_api.py). In production set NEXT_PUBLIC_API_BASE_URL
    // to the deployed API endpoint — with that absolute URL set, the browser
    // fetches the API directly and these rewrites are never hit.
    if (process.env.NEXT_PUBLIC_API_BASE_URL) {
      return []
    }
    return [
      {
        source: "/api/:path*",
        destination: `${process.env.LOCAL_API_BASE || "http://localhost:8000"}/:path*`,
      },
    ]
  },
}

module.exports = nextConfig
