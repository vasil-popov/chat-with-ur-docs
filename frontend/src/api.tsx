const API_BASE_URL = 'http://192.168.1.10:8069';

// ─── Chat ────────────────────────────────────────────────────────────────────

export const sendChatMessage = async (
  userMessage: string,
  options?: { file_ids?: string[] }
) => {
  try {
    const body: Record<string, unknown> = { message: userMessage };
    if (options?.file_ids?.length) body.file_ids = options.file_ids;
    const response = await fetch(`${API_BASE_URL}/api/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    if (!response.ok) throw new Error('Network response was not ok');
    return await response.json();
  } catch (error) {
    console.error('API Error:', error);
    return { role: 'assistant', content: "Sorry, I couldn't reach the server.", metadata: { tools_executed: [] } };
  }
};

// ─── Expenses ─────────────────────────────────────────────────────────────────

export type Expense = {
  id: string;
  date: string;
  amount: number;
  category: string;
  description: string | null;
};

export const getExpenses = async (startDate: string, endDate: string): Promise<Expense[]> => {
  const res = await fetch(`${API_BASE_URL}/api/expenses?start_date=${startDate}&end_date=${endDate}`);
  if (!res.ok) throw new Error('Failed to fetch expenses');
  return res.json();
};

export const createExpense = async (data: {
  amount: number; category: string; description?: string; transaction_date: string;
}): Promise<Expense> => {
  const res = await fetch(`${API_BASE_URL}/api/expenses`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error('Failed to create expense');
  return res.json();
};

export const updateExpense = async (
  id: string,
  data: { amount: number; category: string; description?: string; transaction_date: string }
): Promise<Expense> => {
  const res = await fetch(`${API_BASE_URL}/api/expenses/${id}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error('Failed to update expense');
  return res.json();
};

export const deleteExpense = async (id: string): Promise<void> => {
  const res = await fetch(`${API_BASE_URL}/api/expenses/${id}`, { method: 'DELETE' });
  if (!res.ok) throw new Error('Failed to delete expense');
};

export const createExpensesBulk = async (
  items: { description?: string; amount: number; category: string; transaction_date: string }[]
): Promise<Expense[]> => {
  const res = await fetch(`${API_BASE_URL}/api/expenses/bulk`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(items),
  });
  if (!res.ok) throw new Error('Failed to bulk create expenses');
  return res.json();
};

// ─── Exercises ────────────────────────────────────────────────────────────────

export type ExerciseEntry = {
  exercise_id: string;
  name: string;
  category: string;
  duration: number | null;
  sets: number | null;
  reps: number | null;
  weight_kg: number | null;
  distance_km: number | null;
};

export type WorkoutSession = {
  session_id: string;
  session_name: string;
  date: string;
  exercises: ExerciseEntry[];
};

export const getWorkouts = async (startDate: string, endDate: string): Promise<WorkoutSession[]> => {
  const res = await fetch(`${API_BASE_URL}/api/exercises?start_date=${startDate}&end_date=${endDate}`);
  if (!res.ok) throw new Error('Failed to fetch workouts');
  return res.json();
};

export const createExercise = async (data: {
  exercise_name: string; category: string; workout_date: string; session_name?: string;
  duration_minutes?: number; sets?: number; reps?: number; weight_kg?: number; distance_km?: number;
}): Promise<void> => {
  const res = await fetch(`${API_BASE_URL}/api/exercises`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error('Failed to create exercise');
};

export const deleteExercise = async (id: string): Promise<void> => {
  const res = await fetch(`${API_BASE_URL}/api/exercises/${id}`, { method: 'DELETE' });
  if (!res.ok) throw new Error('Failed to delete exercise');
};

// ─── Files ───────────────────────────────────────────────────────────────────

export type ReceiptItem = {
  description: string;
  amount: number;
  category: string;
  transaction_date: string;
};

export type UploadedFile = {
  id: string;
  original_name: string;
  file_type: string;
  category: string;
  size_bytes: number;
  status: 'processing' | 'ready' | 'error';
  is_receipt: boolean;
  uploaded_at: string;
  extracted_text: string | null;
  error_message: string | null;
  receipt_proposal?: ReceiptItem[];
};

export const uploadFile = async (
  uri: string,
  name: string,
  mimeType: string,
  category = 'general'
): Promise<UploadedFile> => {
  const form = new FormData();
  form.append('file', { uri, name, type: mimeType } as any);
  form.append('category', category);
  const res = await fetch(`${API_BASE_URL}/api/files/upload`, {
    method: 'POST',
    body: form,
  });
  if (!res.ok) throw new Error('Failed to upload file');
  return res.json();
};

export const getFiles = async (category?: string): Promise<UploadedFile[]> => {
  const url = category && category !== 'all'
    ? `${API_BASE_URL}/api/files?category=${encodeURIComponent(category)}`
    : `${API_BASE_URL}/api/files`;
  const res = await fetch(url);
  if (!res.ok) throw new Error('Failed to fetch files');
  return res.json();
};

export const getFile = async (id: string): Promise<UploadedFile> => {
  const res = await fetch(`${API_BASE_URL}/api/files/${id}`);
  if (!res.ok) throw new Error('Failed to fetch file');
  return res.json();
};

export const deleteFile = async (id: string): Promise<void> => {
  const res = await fetch(`${API_BASE_URL}/api/files/${id}`, { method: 'DELETE' });
  if (!res.ok) throw new Error('Failed to delete file');
};
