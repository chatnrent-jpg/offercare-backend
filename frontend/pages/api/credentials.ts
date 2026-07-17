/**
 * VettedMe Credentials API Proxy
 * 
 * This Next.js API route fetches the current user's credentials from FastAPI.
 * 
 * Flow:
 * 1. Frontend calls: GET /api/credentials
 * 2. This route forwards to: GET /api/v1/credentials (FastAPI)
 * 3. FastAPI returns user's verified badges
 * 4. We return to frontend
 * 
 * Note: This endpoint requires authentication.
 */

import type { NextApiRequest, NextApiResponse } from 'next';

const FASTAPI_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

interface Credential {
  id: string;
  provider_type: string;
  claims: Record<string, any>;
  verified_at: string;
  is_valid: boolean;
}

interface ErrorResponse {
  error: string;
  detail?: string;
}

export default async function handler(
  req: NextApiRequest,
  res: NextApiResponse<Credential[] | ErrorResponse>
) {
  // Only allow GET
  if (req.method !== 'GET') {
    return res.status(405).json({
      error: 'Method not allowed'
    });
  }

  try {
    // Get auth token from request headers
    const authHeader = req.headers.authorization;
    if (!authHeader) {
      return res.status(401).json({
        error: 'Missing authorization header'
      });
    }

    // Forward request to FastAPI backend
    const response = await fetch(`${FASTAPI_URL}/api/v1/credentials`, {
      method: 'GET',
      headers: {
        'Authorization': authHeader
      }
    });

    if (!response.ok) {
      const errorData = await response.json();
      console.error('FastAPI error:', errorData);
      return res.status(response.status).json({
        error: errorData.detail || 'Failed to fetch credentials'
      });
    }

    const credentials = await response.json();
    return res.status(200).json(credentials);

  } catch (error: any) {
    console.error('Credentials proxy error:', error);
    return res.status(500).json({
      error: 'Internal server error',
      detail: error.message
    });
  }
}
