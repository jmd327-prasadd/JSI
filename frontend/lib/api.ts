import type {
  AnalysisRun,
  Artifact,
  ConnectionStub,
  DocumentUpload,
  Finding,
  Project,
  RunSummary,
} from "./types";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: { ...(init?.headers || {}) },
    cache: "no-store",
  });
  if (!res.ok) {
    const detail = await res.text().catch(() => "");
    throw new Error(`${res.status} ${res.statusText}: ${detail}`);
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

function json(body: unknown): RequestInit {
  return {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  };
}

// -- Projects ---------------------------------------------------------------

export const listProjects = () => request<Project[]>("/projects");

export const getProject = (id: string) => request<Project>(`/projects/${id}`);

export const createProject = (name: string, client_name: string) =>
  request<Project>("/projects", json({ name, client_name }));

// -- Artifacts / documents ----------------------------------------------------

export const listArtifacts = (projectId: string) =>
  request<Artifact[]>(`/projects/${projectId}/artifacts`);

export const listDocuments = (projectId: string) =>
  request<DocumentUpload[]>(`/projects/${projectId}/documents`);

async function uploadFile<T>(url: string, file: File): Promise<T> {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(`${API_BASE}${url}`, { method: "POST", body: form });
  if (!res.ok) {
    const detail = await res.text().catch(() => "");
    throw new Error(`${res.status} ${res.statusText}: ${detail}`);
  }
  return res.json() as Promise<T>;
}

export const uploadArtifact = (projectId: string, file: File) =>
  uploadFile<Artifact>(`/projects/${projectId}/artifacts`, file);

export const uploadDocument = (projectId: string, file: File) =>
  uploadFile<DocumentUpload>(`/projects/${projectId}/documents`, file);

// -- Connections (stub only, per v1 scope) -----------------------------------

export const listConnections = (projectId: string) =>
  request<ConnectionStub[]>(`/projects/${projectId}/connections`);

// -- Runs ---------------------------------------------------------------------

export const listRuns = (projectId: string) =>
  request<AnalysisRun[]>(`/projects/${projectId}/runs`);

export const createRun = (projectId: string) =>
  request<AnalysisRun>(`/projects/${projectId}/runs`, { method: "POST" });

export const getRun = (projectId: string, runId: string) =>
  request<AnalysisRun>(`/projects/${projectId}/runs/${runId}`);

export const getRunSummary = (projectId: string, runId: string) =>
  request<RunSummary>(`/projects/${projectId}/runs/${runId}/summary`);

export const getRunFindings = (
  projectId: string,
  runId: string,
  filters?: { severity?: string; category?: string; detection_type?: string; status?: string }
) => {
  const params = new URLSearchParams(
    Object.entries(filters || {}).filter(([, v]) => v) as [string, string][]
  );
  const qs = params.toString();
  return request<Finding[]>(
    `/projects/${projectId}/runs/${runId}/findings${qs ? `?${qs}` : ""}`
  );
};

export const updateFindingStatus = (
  projectId: string,
  findingId: string,
  status: string,
  reviewer_note: string
) =>
  request<Finding>(`/projects/${projectId}/findings/${findingId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ status, reviewer_note }),
  });
