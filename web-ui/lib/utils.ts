import { type ClassValue, clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';

const SESSION_ID_KEY = 'research_agent_session_id';

/**
 * Merge class names with Tailwind CSS support
 */
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

/**
 * Format a date to relative time (e.g., "2h ago")
 */
export function formatTime(date: string | Date): string {
  const d = typeof date === 'string' ? new Date(date) : date;
  const now = new Date();
  const diff = now.getTime() - d.getTime();

  const minutes = Math.floor(diff / 60000);
  if (minutes < 1) return 'just now';
  if (minutes < 60) return `${minutes}m ago`;

  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;

  const days = Math.floor(hours / 24);
  if (days < 7) return `${days}d ago`;

  return d.toLocaleDateString();
}

/**
 * Truncate a string to a maximum length
 */
export function truncate(str: string, length: number): string {
  if (str.length <= length) return str;
  return str.slice(0, length) + '...';
}

/**
 * Generate a unique ID
 */
export function generateId(): string {
  return Math.random().toString(36).substring(2, 15) + Math.random().toString(36).substring(2, 15);
}


/**
 * Get the base URL for HTTP API calls
 */
export function getApiBaseUrl(): string {
  if (typeof window === 'undefined') return '';

  // Development: use backend port 8000, Production: same origin
  return process.env.NODE_ENV === 'development'
    ? 'http://localhost:8000'
    : window.location.origin;
}

/**
 * Get or create a session ID from sessionStorage
 * Session ID persists within the same browser tab
 */
export function getSessionId(): string {
  if (typeof window === 'undefined') return generateId();

  let sessionId = sessionStorage.getItem(SESSION_ID_KEY);

  if (!sessionId) {
    sessionId = generateId();
    sessionStorage.setItem(SESSION_ID_KEY, sessionId);
  }

  return sessionId;
}

/**
 * Get the session ID stored in sessionStorage, if any.
 */
export function getStoredSessionId(): string | null {
  if (typeof window === 'undefined') return null;

  return sessionStorage.getItem(SESSION_ID_KEY);
}

/**
 * Reset the session ID (for "New Chat" functionality)
 */
export function resetSessionId(): string {
  if (typeof window === 'undefined') return generateId();

  const newSessionId = generateId();
  sessionStorage.setItem(SESSION_ID_KEY, newSessionId);

  return newSessionId;
}
