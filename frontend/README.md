# VettedMe Enterprise Compliance Dashboard

Modern Next.js dashboard for real-time OHCQ compliance monitoring connected to the VettedMe FastAPI backend.

## Features

- 🎯 Real-time compliance health scoring
- 📊 Live scraper infrastructure diagnostics
- 👥 Active worker placement clearance monitoring
- 🔄 Automatic telemetry data streaming
- 🎨 Modern Tailwind CSS design with dark theme

## Getting Started

### Prerequisites

- Node.js 18+ installed
- VettedMe FastAPI backend running on http://localhost:8000

### Installation

```bash
# Install dependencies
npm install

# Start the development server
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) in your browser to see the dashboard.

## Backend Integration

The dashboard automatically proxies API requests to the FastAPI backend at `http://localhost:8000`. This is configured in `next.config.js`:

```javascript
async rewrites() {
  return [
    {
      source: '/api/:path*',
      destination: 'http://localhost:8000/api/:path*',
    },
  ];
}
```

## API Endpoints

The dashboard connects to:
- `GET /api/v1/analytics/scraper-summary` - Real-time compliance metrics

## Tech Stack

- **Next.js 14** - React framework
- **React 18** - UI library
- **Tailwind CSS** - Utility-first styling
- **FastAPI Backend** - Python API (separate repository)

## Production Build

```bash
npm run build
npm start
```

## License

Proprietary - VettedMe Enterprise Platform
