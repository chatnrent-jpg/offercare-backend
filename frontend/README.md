# VettedMe Frontend - Next.js Dashboard

Beautiful dark-themed dashboard for managing zkTLS credential badges.

## 🎨 Tech Stack

- **Next.js 14** - React framework
- **TypeScript** - Type safety
- **Tailwind CSS** - Utility-first styling
- **React** - UI library

## 🚀 Getting Started

### 1. Install Dependencies

```bash
cd frontend
npm install
```

### 2. Configure Environment

Create `.env.local`:

```bash
FASTAPI_BASE_URL=http://localhost:8000
```

### 3. Run Development Server

```bash
npm run dev
```

Open [http://localhost:3000](http://localhost:3000)

## 📁 Project Structure

```
frontend/
├── components/
│   └── PassportDashboard.tsx    # Main dashboard component
├── pages/
│   ├── api/
│   │   ├── verify.ts            # Reclaim verification proxy
│   │   ├── credentials.ts       # Get user credentials
│   │   └── auth/
│   │       └── [...auth].ts     # Auth proxy to FastAPI
│   ├── _app.tsx                 # App wrapper
│   └── dashboard.tsx            # Dashboard page
├── styles/
│   └── globals.css              # Global styles + Tailwind
├── package.json                 # Dependencies
├── tailwind.config.js           # Tailwind configuration
└── next.config.js               # Next.js configuration
```

## 🔐 Authentication Flow

### 1. Register

```typescript
const response = await fetch('/api/auth/register', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    email: 'user@example.com',
    password: 'SecurePass123',
    username: 'johndoe'
  })
});

const { access_token, user } = await response.json();

// Store token
localStorage.setItem('auth_token', access_token);
```

### 2. Login

```typescript
const response = await fetch('/api/auth/login', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    email: 'user@example.com',
    password: 'SecurePass123'
  })
});

const { access_token } = await response.json();
localStorage.setItem('auth_token', access_token);
```

### 3. Protected Requests

```typescript
const token = localStorage.getItem('auth_token');

const response = await fetch('/api/auth/me', {
  headers: {
    'Authorization': `Bearer ${token}`
  }
});

const user = await response.json();
```

## 🎫 Credential Verification Flow

### 1. User Clicks "Verify" Button

```typescript
handleVerificationRequest('LINKEDIN')
```

### 2. Frontend Calls Next.js API Route

```typescript
const response = await fetch('/api/verify', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'Authorization': `Bearer ${token}`
  },
  body: JSON.stringify({
    providerId: 'LINKEDIN',
    callbackUrl: window.location.origin + '/dashboard?verified=true'
  })
});

const { verificationUrl } = await response.json();
```

### 3. Next.js Proxies to FastAPI

```typescript
// /api/verify calls FastAPI
const response = await fetch('http://localhost:8000/api/v1/reclaim/session/start', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'Authorization': `Bearer ${token}`
  },
  body: JSON.stringify({
    provider_type: 'LINKEDIN',
    callback_url: callbackUrl
  })
});
```

### 4. Redirect to Reclaim Protocol

```typescript
window.location.href = verificationUrl;
// Example: https://share.reclaimprotocol.org/verify/session-id
```

### 5. User Completes Proof on Reclaim

User scans QR code or logs in on Reclaim Protocol to generate zkTLS proof.

### 6. Reclaim Calls FastAPI Webhook

```
POST /api/v1/reclaim/webhook
{
  "id": "session-id",
  "providerId": "linkedin-profile",
  "proof_data": {...}
}
```

### 7. User Returns to Dashboard

```
https://vettedme.ai/dashboard?verified=true
```

Dashboard refreshes and shows verified badge!

## 🎨 Components

### PassportDashboard

Main dashboard component with:

- **User Profile Header** - Email, logout button, public profile link
- **Stats Cards** - Verified, Pending, Total badges
- **Badge Grid** - All available badges with status
- **Verified Claims Display** - Show extracted claims for verified badges
- **Coming Soon Section** - Future badge types

**Badge States:**
- `NOT_CONNECTED` - Gray, "Verify Now" button
- `PENDING` - Amber, "Pending..." button (disabled)
- `VERIFIED` - Green, "Verified ✓" button (disabled), shows claims

## 🎨 Styling

### Dark Theme

```css
Background: slate-900 (gradient)
Cards: slate-800
Borders: slate-700
Text Primary: white
Text Secondary: slate-400
```

### Colors

```css
Verified: emerald-500 (green)
Pending: amber-500 (orange)
Not Connected: slate-700 (gray)
Primary Action: emerald-500
```

### Responsive

- Mobile-first design
- Grid layout adapts to screen size
- Touch-friendly buttons

## 🔧 Development

### Type Checking

```bash
npm run type-check
```

### Linting

```bash
npm run lint
```

### Production Build

```bash
npm run build
npm start
```

## 🚀 Deployment

### Vercel (Recommended)

```bash
npm install -g vercel
vercel
```

Set environment variable:
```
FASTAPI_BASE_URL=https://api.vettedme.ai
```

### Docker

```dockerfile
FROM node:18-alpine
WORKDIR /app
COPY package*.json ./
RUN npm install
COPY . .
RUN npm run build
EXPOSE 3000
CMD ["npm", "start"]
```

## 📝 Environment Variables

```bash
# .env.local
FASTAPI_BASE_URL=http://localhost:8000  # Development
# FASTAPI_BASE_URL=https://api.vettedme.ai  # Production
```

## 🎯 Next Steps

### Week 1 Day 2 (Tomorrow):
- [ ] Add login/register pages
- [ ] Add email verification UI
- [ ] Add profile editing
- [ ] Add badge sharing (Twitter, LinkedIn)

### Week 2:
- [ ] Add public profile viewer
- [ ] Add badge detail pages
- [ ] Add search/filter badges
- [ ] Add mobile app PWA

## 🐛 Troubleshooting

### "Failed to fetch"

Check FastAPI backend is running:
```bash
cd ../
python -m uvicorn app.main:app --reload
```

### "Unauthorized"

Check JWT token is valid:
```javascript
const token = localStorage.getItem('auth_token');
console.log(token); // Should be a long JWT string
```

### Tailwind styles not working

```bash
rm -rf .next
npm run dev
```

## 📚 Resources

- [Next.js Docs](https://nextjs.org/docs)
- [Tailwind CSS](https://tailwindcss.com/)
- [TypeScript](https://www.typescriptlang.org/)
- [Reclaim Protocol](https://www.reclaimprotocol.org/)

---

**🎨 Beautiful Dark Dashboard Ready for zkTLS Badges**  
**🚀 Connects to FastAPI Backend**  
**💪 Production-Ready Code**
