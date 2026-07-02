export async function getSummary(date = null) {
  const params = new URLSearchParams();
  if (date) params.append("date", date);
  const response = await fetch(`/summary?${params}`);
  if (!response.ok) throw new Error("Failed to fetch summary");
  return response.json();
}

export async function completeRep(repId) {
  const response = await fetch(`/reps/${repId}/complete`, {
    method: "POST",
  });
  if (!response.ok) throw new Error("Failed to complete rep");
  return response.json();
}

export async function markMissed() {
  const response = await fetch(`/reps/mark-missed`, {
    method: "POST",
  });
  if (!response.ok) throw new Error("Failed to mark missed");
  return response.json();
}

// Goals CRUD
export async function getGoals() {
  const response = await fetch(`/goals`);
  if (!response.ok) throw new Error("Failed to fetch goals");
  return response.json();
}

export async function createGoal(data) {
  const response = await fetch(`/goals`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!response.ok) throw new Error("Failed to create goal");
  return response.json();
}

export async function updateGoal(goalId, data) {
  const response = await fetch(`/goals/${goalId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!response.ok) throw new Error("Failed to update goal");
  return response.json();
}

export async function deleteGoal(goalId) {
  const response = await fetch(`/goals/${goalId}`, {
    method: "DELETE",
  });
  if (!response.ok) throw new Error("Failed to delete goal");
}

export async function deleteGoalHard(goalId) {
  const response = await fetch(`/goals/${goalId}?hard=true`, {
    method: "DELETE",
  });
  if (!response.ok) throw new Error("Failed to permanently delete goal");
}

// Rep Types CRUD
export async function getRepTypes(goalId) {
  const response = await fetch(`/goals/${goalId}/rep-types`);
  if (!response.ok) throw new Error("Failed to fetch rep types");
  return response.json();
}

export async function createRepType(goalId, data) {
  const response = await fetch(`/goals/${goalId}/rep-types`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!response.ok) throw new Error("Failed to create rep type");
  return response.json();
}

export async function updateRepType(repTypeId, data) {
  const response = await fetch(`/rep-types/${repTypeId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!response.ok) throw new Error("Failed to update rep type");
  return response.json();
}

export async function deleteRepType(repTypeId) {
  const response = await fetch(`/rep-types/${repTypeId}`, {
    method: "DELETE",
  });
  if (!response.ok) throw new Error("Failed to delete rep type");
}

// Reps scheduling
export async function createRep(data) {
  const response = await fetch(`/reps`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!response.ok) throw new Error("Failed to create rep");
  return response.json();
}

export async function createReps(repsArray) {
  const response = await fetch(`/reps/bulk`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ reps: repsArray }),
  });
  if (!response.ok) throw new Error("Failed to schedule reps");
  return response.json();
}

export async function deleteRep(repId) {
  const response = await fetch(`/reps/${repId}`, {
    method: "DELETE",
  });
  if (!response.ok) throw new Error("Failed to delete rep");
}
