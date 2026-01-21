/** @type {import('next').NextConfig} */
const nextConfig = {
  // Enable React strict mode for better development experience
  reactStrictMode: true,

  // Configure for standalone output if needed
  output: 'standalone',

  // API proxy configuration for development
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: 'http://localhost:8111/api/:path*',
      },
    ];
  },
};

module.exports = nextConfig;
