import { Platform } from 'react-native';

const API_BASE_URL = 'http://192.168.1.10:8069';

// ─── Chat ────────────────────────────────────────────────────────────────────

export const sendChatMessage = async (userMessage: string) => {
  try {
    const response = await fetch(`${API_BASE_URL}/api/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: userMessage }),
    });

    if (!response.ok) throw new Error('Network response was not ok');
    return await response.json();
  } catch (error) {
    console.error('API Error:', error);
    return { role: 'assistant', content: "Sorry, I couldn't reach the server." };
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
  const res = await fetch(
    `${API_BASE_URL}/api/expenses?start_date=${startDate}&end_date=${endDate}`
  );
  if (!res.ok) throw new Error('Failed to fetch expenses');
  return res.json();
};

export const createExpense = async (data: {
  amount: number;
  category: string;
  description?: string;
  transaction_date: string;
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
  const res = await fetch(
    `${API_BASE_URL}/api/exercises?start_date=${startDate}&end_date=${endDate}`
  );
  if (!res.ok) throw new Error('Failed to fetch workouts');
  return res.json();
};

export const createExercise = async (data: {
  exercise_name: string;
  category: string;
  workout_date: string;
  session_name?: string;
  duration_minutes?: number;
  sets?: number;
  reps?: number;
  weight_kg?: number;
  distance_km?: number;
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
