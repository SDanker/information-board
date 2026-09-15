/** @type {import('next').NextConfig} */
const nextConfig = {
  output: "standalone",
  poweredByHeader: false,
  // Old Spanish routes keep working for bookmarks, kiosk URLs and printed QR codes.
  async redirects() {
    return [
      { source: "/admin/publicaciones", destination: "/admin/content", permanent: true },
      { source: "/admin/programacion", destination: "/admin/schedule", permanent: true },
      { source: "/admin/usuarios", destination: "/admin/users", permanent: true },
      { source: "/admin/auditoria", destination: "/admin/audit", permanent: true },
      { source: "/admin/configuracion", destination: "/admin/settings", permanent: true },
      { source: "/biblioteca", destination: "/library", permanent: true },
      { source: "/pantalla/:slug", destination: "/catalog/:slug", permanent: true },
    ];
  },
  // Only used by `next dev`; in Docker, nginx routes /api to the backend.
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${process.env.INTERNAL_API_URL ?? "http://localhost:8000"}/api/:path*`,
      },
    ];
  },
};

export default nextConfig;
