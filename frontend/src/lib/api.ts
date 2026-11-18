// Client de l'API locale StudyAI (même adresse que l'interface).

export type Steps = Record<string, string>;

export interface Course {
  id: string;
  title: string;
  filename: string;
  has_video: number;
  duration: number | null;
  language: string | null;
  status: "queued" | "running" | "done" | "error" | "cancelled";
  stage: string | null;
  stage_label: string | null;
  progress: number;
  eta_seconds: number | null;
  steps: Steps;
  options: Record<string, unknown>;
  error: string | null;
  cost_usd: number;
  created_at: number;
  counts: { segments: number; slides: number; flashcards: number };
  analysis_kinds: string[];
}

export interface Segment { id: number; start: number; end: number; text: string; uncertain: number }

export interface Slide {
  idx: number;
  ts: number;
  end_ts: number;
  ocr_text: string | null;
  vision: { text: string; tables: string; formulas: string; figures: string } | null;
}

export interface Chapter { title: string; start: number; end: number; summary: string; key_points: string[]; slides: number[] }

export interface CourseAnalysis {
  title: string;
  subject: string;
  general_summary: string;
  chapters: Chapter[];
  uncertainties: { timestamp: number; excerpt: string; issue: string }[];
}

export interface Notions {
  definitions: { term: string; definition: string; timestamp: number; source: string }[];
  key_notions: { notion: string; explanation: string; timestamp: number }[];
  formulas: { name: string; formula: string; variables: string; explanation: string; timestamp: number }[];
  examples: { title: string; description: string; timestamp: number }[];
  simplified: { notion: string; explanation: string }[];
  common_mistakes: { mistake: string; correction: string }[];
  exam_points: { point: string; reason: string; timestamp: number }[];
  likely_questions: { question: string; expected_answer: string; timestamp: number }[];
}

export interface Step {
  explanation: string;
  expression: string;
  result: number;
  unit: string;
  check: "ok" | "erreur" | "non_verifiable";
  computed?: number;
}

export interface JournalEntry {
  label: string;
  lines: { account: string; account_name: string; debit: number; credit: number }[];
  total_debit: number;
  total_credit: number;
  balanced: boolean;
  problems: string[];
}

export interface Exercise {
  title: string;
  statement: string;
  notion: string;
  from_course: boolean;
  steps: Step[];
  journal_entries: JournalEntry[];
  final_answer: string;
  verification: { errors: number; checked_steps: number; status: "ok" | "a_verifier" };
}

export interface MCQ { id: string; question: string; choices: string[]; correct_index: number; explanation: string; notion: string; timestamp: number }
export interface OpenQuestion { id: string; question: string; model_answer: string; notion: string; points: number }

export interface Revision {
  sheets: { title: string; content: string }[];
  flashcards: { front: string; back: string; notion: string }[];
  mcq: MCQ[];
  open_questions: OpenQuestion[];
  exercises: Exercise[];
}

export interface Analysis { course?: CourseAnalysis; notions?: Notions; revision?: Revision }

export interface Flashcard {
  id: string; course_id: string; front: string; back: string; notion: string | null;
  ease: number; interval_days: number; reps: number; due: number;
}

export interface Settings {
  whisper_engine: string; whisper_model: string; language: string;
  provider: "claude" | "local"; claude_model: string; local_model: string; effort: string;
  slide_interval: number; slide_threshold: number; vision_default: boolean; accounting_default: boolean;
}

export interface Status {
  ffmpeg: boolean;
  whisper_engines: string[];
  apple_silicon: boolean;
  ocr: string | null;
  api_key: boolean;
  api_key_hint: string | null;
  ollama_models: string[] | null;
  pulling: string[];
  settings: Settings;
  claude_models: Record<string, { label: string; input: number; output: number }>;
  local_models: Record<string, string>;
  whisper_models: string[];
  current_job: string | null;
}

export interface Stats {
  attempts: { id: string; course_id: string; mode: string; score: number; total: number; duration_seconds: number | null; created_at: number }[];
  weak_notions: { course_id: string; notion: string; success_rate: number; answers: number }[];
  flashcards_due: number;
  flashcards_total: number;
  answers: number;
  success_rate: number | null;
}

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(path, { ...init, headers: { "Content-Type": "application/json", ...(init?.headers || {}) } });
  } catch {
    throw new ApiError(0, "Le moteur StudyAI ne répond pas. Est-il lancé ?");
  }
  if (!res.ok) {
    let msg = `Erreur ${res.status}`;
    try {
      const body = await res.json();
      msg = typeof body.detail === "string" ? body.detail : msg;
    } catch {}
    throw new ApiError(res.status, msg);
  }
  return res.json() as Promise<T>;
}

const json = (body: unknown) => ({ method: "POST", body: JSON.stringify(body) });

export const api = {
  status: () => req<Status>("/api/status"),
  saveSettings: (s: Partial<Settings>) => req<Settings>("/api/settings", { method: "PUT", body: JSON.stringify(s) }),
  saveKey: (key: string) => req<{ api_key: boolean }>("/api/settings/api-key", { method: "PUT", body: JSON.stringify({ key }) }),
  pull: (model: string) => req("/api/ollama/pull", json({ model })),
  courses: () => req<Course[]>("/api/courses"),
  course: (id: string) => req<Course>(`/api/courses/${id}`),
  rename: (id: string, title: string) => req<Course>(`/api/courses/${id}`, { method: "PATCH", body: JSON.stringify({ title }) }),
  remove: (id: string) => req(`/api/courses/${id}`, { method: "DELETE" }),
  retry: (id: string) => req<Course>(`/api/courses/${id}/retry`, { method: "POST" }),
  cancel: (id: string) => req<Course>(`/api/courses/${id}/cancel`, { method: "POST" }),
  reanalyze: (id: string, body: Record<string, unknown>) => req<Course>(`/api/courses/${id}/analyze`, json(body)),
  transcript: (id: string) => req<Segment[]>(`/api/courses/${id}/transcript`),
  editSegment: (id: string, segId: number, text: string) =>
    req(`/api/courses/${id}/transcript/${segId}`, { method: "PUT", body: JSON.stringify({ text }) }),
  slides: (id: string) => req<Slide[]>(`/api/courses/${id}/slides`),
  analysis: (id: string) => req<Analysis>(`/api/courses/${id}/analysis`),
  estimate: (minutes: number) => req<Record<string, { usd: number }>>(`/api/estimate?minutes=${minutes}`),
  flashcards: (courseId?: string, due = false) =>
    req<Flashcard[]>(`/api/flashcards?${new URLSearchParams({ ...(courseId ? { course_id: courseId } : {}), due: String(due) })}`),
  review: (cardId: string, grade: number) => req<Flashcard>(`/api/flashcards/${cardId}/review`, json({ grade })),
  attempt: (body: { course_id: string; mode: string; score: number; total: number; duration_seconds?: number; details: unknown[] }) =>
    req<{ id: string }>("/api/attempts", json(body)),
  stats: (courseId?: string) => req<Stats>(`/api/stats${courseId ? `?course_id=${courseId}` : ""}`),
  grade: (courseId: string, questionId: string, answer: string) =>
    req<{ score: number; max_score: number; feedback: string; missing_points: string[] }>("/api/grade",
      json({ course_id: courseId, question_id: questionId, answer })),
  tool: <T,>(name: string, body: unknown) => req<T>(`/api/tools/${name}`, json(body)),
};

export const mediaUrl = (id: string) => `/api/courses/${id}/media`;
export const slideUrl = (id: string, idx: number) => `/api/courses/${id}/slides/${idx}/image`;
export const exportUrl = (id: string, fmt: string) => `/api/courses/${id}/export/${fmt}`;

/** Envoi du fichier en flux avec suivi de progression (XHR : fetch ne donne pas l'avancement de l'envoi). */
export function uploadCourse(file: File, options: Record<string, unknown>, onProgress: (f: number) => void): Promise<Course> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", "/api/courses/upload");
    xhr.setRequestHeader("x-filename", encodeURIComponent(file.name));
    xhr.setRequestHeader("x-options", encodeURIComponent(JSON.stringify(options)));
    xhr.upload.onprogress = (e) => e.lengthComputable && onProgress(e.loaded / e.total);
    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) resolve(JSON.parse(xhr.responseText));
      else {
        let msg = `Erreur ${xhr.status}`;
        try { msg = JSON.parse(xhr.responseText).detail || msg; } catch {}
        reject(new ApiError(xhr.status, msg));
      }
    };
    xhr.onerror = () => reject(new ApiError(0, "Envoi impossible : le moteur StudyAI ne répond pas."));
    xhr.send(file);
  });
}
