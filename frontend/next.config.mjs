/** @type {import('next').NextConfig} */
const nextConfig = {
  async rewrites() {
    return [
      {
        // Proxy all /api/* routes to the backend EXCEPT /api/auth/* (handled by NextAuth)
        source: '/api/:path((?!auth).*)',
        destination: 'http://localhost:8000/:path*',
      },
    ];
  },
};

export default nextConfig;
