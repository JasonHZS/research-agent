/** @type {import('next').NextConfig} */
const nextConfig = {
  // Enable React strict mode for better development experience
  reactStrictMode: true,

  // Configure for standalone output if needed
  output: 'standalone',

  // API proxy configuration for development
  async rewrites() {
    const defaultApiPort =
      process.env.NODE_ENV === 'development' ? '8112' : '8111';
    const apiPort = process.env.NEXT_PUBLIC_API_PORT || defaultApiPort;
    return [
      {
        source: '/api/:path*',
        destination: `http://localhost:${apiPort}/api/:path*`,
      },
    ];
  },
};

module.exports = nextConfig;
