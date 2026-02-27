/**
 * HTTP API client for the Research Agent
 * Only contains non-streaming API calls (models list, health check)
 */

import type { ModelInfo } from './types';
import { getApiBaseUrl } from './utils';

/**
 * Response from the models endpoint
 */
export interface ModelsResponse {
  models: ModelInfo[];
  current_provider: string;
  current_model: string;
}

/**
 * Build headers with optional Bearer token
 */
function authHeaders(token?: string | null): Record<string, string> {
  const headers: Record<string, string> = {};
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }
  return headers;
}

/**
 * API client singleton
 */
export const api = {
  /**
   * Get list of available models
   */
  async getModels(token?: string | null): Promise<ModelsResponse> {
    const baseUrl = getApiBaseUrl();
    const res = await fetch(`${baseUrl}/api/models`, {
      headers: authHeaders(token),
    });

    if (!res.ok) {
      throw new Error(`Failed to fetch models: ${res.status} ${res.statusText}`);
    }

    return res.json();
  },

  /**
   * Health check endpoint (public, no auth needed)
   */
  async healthCheck(): Promise<{ status: string; service: string }> {
    const baseUrl = getApiBaseUrl();
    const res = await fetch(`${baseUrl}/api/health`);

    if (!res.ok) {
      throw new Error(`Health check failed: ${res.status} ${res.statusText}`);
    }

    return res.json();
  },

  /**
   * Reset an existing chat session on the backend.
   */
  async resetSession(sessionId: string, token?: string | null): Promise<void> {
    const baseUrl = getApiBaseUrl();
    const res = await fetch(`${baseUrl}/api/chat/reset`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...authHeaders(token) },
      body: JSON.stringify({ session_id: sessionId }),
    });

    if (!res.ok) {
      throw new Error(`Failed to reset session: ${res.status} ${res.statusText}`);
    }
  },
};
