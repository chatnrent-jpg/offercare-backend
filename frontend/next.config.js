/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  env: {
    FASTAPI_BASE_URL: process.env.FASTAPI_BASE_URL || 'http://localhost:8000',
  },
}

module.exports = nextConfig
