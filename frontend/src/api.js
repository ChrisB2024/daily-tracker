const API_URL = import.meta.env.VITE_API_URL || '';

function apiUrl(path) {
  return `${API_URL}${path}`;
}

export async function getSummary(date = null) {
  const params = new URLSearchParams();
  if (date) params.append("date", date);
  const response = await fetch(apiUrl(`/summary?${params}`));
  if (!response.ok) throw new Error("Failed to fetch summary");
  return response.json();
}

export async function completeRep(repId) {
  const response = await fetch(apiUrl(`/reps/${repId}/complete`), {
    method: "POST",
  });
  if (!response.ok) throw new Error("Failed to complete rep");
  return response.json();
}

export async function markMissed() {
  const response = await fetch(apiUrl(`/reps/mark-missed`), {
    method: "POST",
  });
  if (!response.ok) throw new Error("Failed to mark missed");
  return response.json();
}

// Goals CRUD
export async function getGoals() {
  const response = await fetch(apiUrl(`/goals`));
  if (!response.ok) throw new Error("Failed to fetch goals");
  return response.json();
}

export async function createGoal(data) {
  const response = await fetch(apiUrl(`/goals`), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!response.ok) throw new Error("Failed to create goal");
  return response.json();
}

export async function updateGoal(goalId, data) {
  const response = await fetch(apiUrl(`/goals/${goalId}`), {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!response.ok) throw new Error("Failed to update goal");
  return response.json();
}

export async function deleteGoal(goalId) {
  const response = await fetch(apiUrl(`/goals/${goalId}`), {
    method: "DELETE",
  });
  if (!response.ok) throw new Error("Failed to delete goal");
}

export async function deleteGoalHard(goalId) {
  const response = await fetch(apiUrl(`/goals/${goalId}?hard=true`), {
    method: "DELETE",
  });
  if (!response.ok) throw new Error("Failed to permanently delete goal");
}

// Rep Types CRUD
export async function getRepTypes(goalId) {
  const response = await fetch(apiUrl(`/goals/${goalId}/rep-types`));
  if (!response.ok) throw new Error("Failed to fetch rep types");
  return response.json();
}

export async function createRepType(goalId, data) {
  const response = await fetch(apiUrl(`/goals/${goalId}/rep-types`), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!response.ok) throw new Error("Failed to create rep type");
  return response.json();
}

export async function updateRepType(repTypeId, data) {
  const response = await fetch(apiUrl(`/rep-types/${repTypeId}`), {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!response.ok) throw new Error("Failed to update rep type");
  return response.json();
}

export async function deleteRepType(repTypeId) {
  const response = await fetch(apiUrl(`/rep-types/${repTypeId}`), {
    method: "DELETE",
  });
  if (!response.ok) throw new Error("Failed to delete rep type");
}

// Reps scheduling
export async function createRep(data) {
  const response = await fetch(apiUrl(`/reps`), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!response.ok) throw new Error("Failed to create rep");
  return response.json();
}

export async function createReps(repsArray) {
  const response = await fetch(apiUrl(`/reps/bulk`), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ reps: repsArray }),
  });
  if (!response.ok) throw new Error("Failed to schedule reps");
  return response.json();
}

export async function deleteRep(repId) {
  const response = await fetch(apiUrl(`/reps/${repId}`), {
    method: "DELETE",
  });
  if (!response.ok) throw new Error("Failed to delete rep");
}

// Analytics & Week View
export async function getAnalytics() {
  const response = await fetch(apiUrl(`/summary/analytics`));
  if (!response.ok) throw new Error("Failed to fetch analytics");
  return response.json();
}

export async function getWeek(date = null) {
  const params = new URLSearchParams();
  if (date) params.append("date", date);
  const response = await fetch(apiUrl(`/summary/week?${params}`));
  if (!response.ok) throw new Error("Failed to fetch week");
  return response.json();
}

export async function getHistory() {
  const response = await fetch(apiUrl(`/history`));
  if (!response.ok) throw new Error("Failed to fetch history");
  return response.json();
}

export async function getDebrief(date = null) {
  const params = new URLSearchParams();
  if (date) params.append("date", date);
  const response = await fetch(apiUrl(`/debrief?${params}`));
  if (!response.ok) throw new Error("Failed to fetch debrief");
  return response.json();
}
