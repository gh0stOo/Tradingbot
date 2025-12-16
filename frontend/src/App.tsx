import { useEffect, useState } from "react";
import axios from "axios";

type CalendarSlot = { date: string; slots: { id: string; status: string; slot_index: number }[] };
type Metric = { metric: string; value: number };

const api = axios.create({ baseURL: "/api" });

function App() {
  const [token, setToken] = useState<string>("");
  const [projectId, setProjectId] = useState<string>("");
  const [calendar, setCalendar] = useState<CalendarSlot[]>([]);
  const [metrics, setMetrics] = useState<Metric[]>([]);
  const [assetId, setAssetId] = useState<string>("");
  const demoEmail = "demo@codex.local";
  const demoPassword = "demopass123";

  useEffect(() => {
    const bootstrap = async () => {
      const login = await api.post("/auth/login", { email: demoEmail, password: demoPassword });
      setToken(login.data.access_token);
      api.defaults.headers.common["Authorization"] = `Bearer ${login.data.access_token}`;
      const orgs = await api.get("/orgs");
      const orgId = orgs.data[0].id;
      const projects = await api.get(`/projects/${orgId}`);
      const pid = projects.data[0].id;
      setProjectId(pid);
      const cal = await api.get(`/plans/calendar/${pid}`);
      setCalendar(cal.data);
      const metricsResp = await api.get(`/analytics/metrics/${pid}`);
      setMetrics(metricsResp.data.metrics);
    };
    bootstrap().catch(console.error);
  }, []);

  const generate = async (planId: string) => {
    const resp = await api.post(`/video/generate/${projectId}/${planId}`);
    setAssetId(resp.data.id);
  };

  const publish = async () => {
    if (!assetId) return;
    await api.post(`/video/publish/${assetId}`);
    alert("Published");
  };

  return (
    <div className="min-h-screen bg-slate-950 text-white p-6">
      <h1 className="text-2xl font-bold mb-4">Codex TikTok Studio</h1>
      <div className="grid grid-cols-3 gap-4">
        <div className="bg-slate-900 p-4 rounded">
          <h2 className="font-semibold mb-2">Calendar</h2>
          <div className="space-y-2 max-h-80 overflow-auto">
            {calendar.slice(0, 10).map((slot) => (
              <div key={slot.date} className="border border-slate-700 p-2 rounded">
                <div className="text-sm text-slate-300">{slot.date}</div>
                <div className="flex gap-2 mt-2">
                  {slot.slots.map((s) => (
                    <button
                      key={s.id}
                      onClick={() => generate(s.id)}
                      className="px-2 py-1 bg-emerald-600 rounded text-sm"
                    >
                      Slot {s.slot_index} ({s.status})
                    </button>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>
        <div className="bg-slate-900 p-4 rounded">
          <h2 className="font-semibold mb-2">Video Library</h2>
          <p className="text-sm text-slate-400">Letzte Asset-ID: {assetId || "noch keins"}</p>
          <button onClick={publish} className="mt-4 px-3 py-2 bg-indigo-600 rounded">
            Publish Now
          </button>
        </div>
        <div className="bg-slate-900 p-4 rounded">
          <h2 className="font-semibold mb-2">Analytics</h2>
          <ul className="space-y-1 text-sm">
            {metrics.map((m) => (
              <li key={m.metric} className="flex justify-between border-b border-slate-800 pb-1">
                <span>{m.metric}</span>
                <span>{m.value}</span>
              </li>
            ))}
          </ul>
        </div>
      </div>
      <div className="mt-4 text-xs text-slate-400">
        Logged in as demo user {demoEmail} (token {token ? "active" : "pending"})
      </div>
    </div>
  );
}

export default App;
