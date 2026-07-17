/**
 * VettedMe Auth API Proxy
 * 
 * This Next.js API route proxies all authentication requests to FastAPI.
 * 
 * Supported endpoints:
 * - POST /api/auth/register -> POST /api/v1/auth/register
 * - POST /api/auth/login -> POST /api/v1/auth/login
 * - GET /api/auth/me -> GET /api/v1/auth/me
 * - POST /api/auth/logout -> POST /api/v1/auth/logout
 * 
 * Why proxy?
 * - Single API endpoint for frontend
 * - Can add middleware (CORS, rate limiting)
 * - Can cache responses if needed
 */

import type { NextApiRequest, NextApiResponse } from 'next';

const FASTAPI_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export default async function handler(
  req: NextApiRequest,
  res: NextApiResponse
) {
  try {
    // Extract the auth path from the catch-all route
    const { auth } = req.query;
    const authPath = Array.isArray(auth) ? auth.join('/') : auth;

    // Build the FastAPI URL
    const fastApiUrl = `${FASTAPI_URL}/api/v1/auth/${authPath}`;

    console.log(`[Auth Proxy] ${req.method} ${authPath} -> ${fastApiUrl}`);

    // Build headers
    const headers: Record<string, string> = {
      'Content-Type': 'application/json'
    };

    // Forward Authorization header if present
    if (req.headers.authorization) {
      headers['Authorization'] = req.headers.authorization;
    }

    // Forward request to FastAPI
    const response = await fetch(fastApiUrl, {
      method: req.method,
      headers,
      body: req.method !== 'GET' && req.method !== 'HEAD' 
        ? JSON.stringify(req.body)
        : undefined
    });

    const data = await response.json();

    // Forward response status and body
    return res.status(response.status).json(data);

  } catch (error: any) {
    console.error('[Auth Proxy] Error:', error);
    return res.status(500).json({
      error: 'Internal server error',
      detail: error.message
    });
  }
}
