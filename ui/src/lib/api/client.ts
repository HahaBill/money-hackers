import { env } from '$env/dynamic/public';
import type { ChatReply, ChatTurn, Dashboard, RunGraph, RunSummary } from '$lib/types';

const API_BASE = (env.PUBLIC_API_BASE_URL || '/api').replace(/\/$/, '');

class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number
  ) {
    super(message);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: { 'content-type': 'application/json', ...init?.headers }
  });
  if (!response.ok) {
    let message = `Request failed (${response.status})`;
    try {
      const body = await response.json();
      message = body.detail || message;
    } catch {
      // Keep the status-based message when an upstream proxy returns HTML.
    }
    throw new ApiError(message, response.status);
  }
  return response.json() as Promise<T>;
}

export async function listRuns(): Promise<RunSummary[]> {
  return (await request<{ runs: RunSummary[] }>('/runs')).runs;
}

export function getDashboard(runId: string): Promise<Dashboard> {
  return request(`/dashboard/${encodeURIComponent(runId)}`);
}

export function getGraph(runId: string): Promise<RunGraph> {
  return request(`/runs/${encodeURIComponent(runId)}/graph`);
}

export function answerQuestion(runId: string, questionId: string, option: string) {
  return request<{ text: string }>('/tools/record_answer', {
    method: 'POST',
    body: JSON.stringify({ run_id: runId, question_id: questionId, option })
  });
}

export function rateFinding(
  runId: string,
  findingId: string,
  hypothesisId: string | undefined,
  rating: 'right' | 'wrong' | 'incomplete'
) {
  return request<{ status: string }>('/feedback', {
    method: 'POST',
    body: JSON.stringify({
      run_id: runId,
      finding_id: findingId,
      hypothesis_id: hypothesisId,
      rating
    })
  });
}

export function createVoiceSession(runId: string) {
  return request<{
    signed_url: string;
    dynamic_variables: Record<string, string>;
  }>(`/voice/session?run_id=${encodeURIComponent(runId)}`);
}

async function responseError(response: Response): Promise<ApiError> {
  let message = `Request failed (${response.status})`;
  try {
    const body = await response.json();
    message = body.detail || message;
  } catch {
    // Keep the status-based message when an upstream proxy returns HTML.
  }
  return new ApiError(message, response.status);
}

export async function transcribeVoice(runId: string, audio: Blob): Promise<string> {
  const response = await fetch(
    `${API_BASE}/voice/transcribe?run_id=${encodeURIComponent(runId)}`,
    {
      method: 'POST',
      headers: { 'content-type': audio.type || 'audio/webm' },
      body: audio
    }
  );
  if (!response.ok) throw await responseError(response);
  const body = (await response.json()) as { text: string };
  return body.text;
}

export async function speakVoice(runId: string, text: string): Promise<Blob> {
  const response = await fetch(`${API_BASE}/voice/speak`, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ run_id: runId, text })
  });
  if (!response.ok) throw await responseError(response);
  return response.blob();
}

export function askWorkbook(runId: string, message: string, history: ChatTurn[]) {
  return request<ChatReply>('/chat', {
    method: 'POST',
    body: JSON.stringify({ run_id: runId, message, history })
  });
}
