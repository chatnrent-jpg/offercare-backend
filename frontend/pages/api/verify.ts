/**
 * VettedMe Verification API Proxy
 * 
 * This Next.js API route acts as a proxy between the frontend and FastAPI backend.
 * 
 * Flow:
 * 1. Frontend calls: POST /api/verify
 * 2. This route forwards to: POST http://localhost:8000/api/v1/reclaim/session/start
 * 3. FastAPI creates Reclaim session
 * 4. We return Reclaim URL to frontend
 * 5. Frontend redirects user to Reclaim
 * 
 * Why proxy?
 * - Hides backend URL from frontend
 * - Can add middleware (rate limiting, logging)
 * - Can transform request/response if needed
 */

import type { NextApiRequest, NextApiResponse } from 'next';

const FASTAPI_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

interface VerifyRequest {
  providerId: string;
  callbackUrl?: string;
}

interface VerifyResponse {
  success: boolean;
  verificationUrl?: string;
  sessionId?: string;
  error?: string;
}

export default async function handler(
  req: NextApiRequest,
  res: NextApiResponse<VerifyResponse>
) {
  // Only allow POST
  if (req.method !== 'POST') {
    return res.status(405).json({
      success: false,
      error: 'Method not allowed'
    });
  }

  try {
    const { providerId, callbackUrl } = req.body as VerifyRequest;

    // Validate input
    if (!providerId) {
      return res.status(400).json({
        success: false,
        error: 'Missing providerId'
      });
    }

    // Get auth token from request headers
    const authHeader = req.headers.authorization;
    if (!authHeader) {
      return res.status(401).json({
        success: false,
        error: 'Missing authorization header'
      });
    }

    // Forward request to FastAPI backend
    const response = await fetch(`${FASTAPI_URL}/api/v1/reclaim/session/start`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': authHeader
      },
      body: JSON.stringify({
        provider_type: providerId,
        callback_url: callbackUrl
      })
    });

    const data = await response.json();

    if (!response.ok) {
      console.error('FastAPI error:', data);
      return res.status(response.status).json({
        success: false,
        error: data.detail || 'Verification failed'
      });
    }

    // Return success with Reclaim URL
    return res.status(200).json({
      success: true,
      verificationUrl: data.reclaim_url,
      sessionId: data.id
    });

  } catch (error: any) {
    console.error('Verification proxy error:', error);
    return res.status(500).json({
      success: false,
      error: error.message || 'Internal server error'
    });
  }
}
