import { completeRep, deleteRep } from "../api";
import RepItem from "./RepItem";

export default function TodayReps({ goals, onRepComplete }) {
  if (!goals || goals.length === 0) {
    return (
      <section>
        <h2>Today's Reps</h2>
        <p className="empty">No reps scheduled for today.</p>
      </section>
    );
  }

  async function handleCompleteRep(repId) {
    try {
      await completeRep(repId);
      onRepComplete();
    } catch (err) {
      alert("Failed to complete rep: " + err.message);
    }
  }

  async function handleDeleteRep(repId) {
    if (!confirm("Delete this rep? This cannot be undone.")) return;
    try {
      await deleteRep(repId);
      onRepComplete();
    } catch (err) {
      alert("Failed to delete rep: " + err.message);
    }
  }

  return (
    <section>
      <h2>Today's Reps</h2>
      {goals.map((goal) => (
        <div key={goal.goal_id} className="goal-group">
          <h3>{goal.goal_title}</h3>
          {goal.reps.length > 0 ? (
            <ul className="reps">
              {goal.reps.map((rep) => (
                <RepItem
                  key={rep.rep_id}
                  rep={rep}
                  onComplete={() => handleCompleteRep(rep.rep_id)}
                  onDelete={() => handleDeleteRep(rep.rep_id)}
                />
              ))}
            </ul>
          ) : (
            <p className="empty">No reps for this goal today.</p>
          )}
        </div>
      ))}
    </section>
  );
}
