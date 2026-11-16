import { useEffect, useRef, useState } from "react";
import { api, type AppConfig, type ChartSpec, type EnrichResult } from "../lib/api";
import { SpecChart } from "./Chart";
import { ContextPills, Notice } from "./common";

interface Msg {
  role: "user" | "assistant";
  content: string;
  chart?: ChartSpec | null;
}

interface Gate {
  question: string;
  ctx: Record<string, any>;
  route: string;
  routeLabel: string;
  routeWhy: string;
  sessionId: string;
  startedAt: number;
}

export default function Advisor({
  config,
  ctx,
  setCtx,
}: {
  config: AppConfig;
  ctx: Record<string, any>;
  setCtx: (c: Record<string, any>) => void;
}) {
  const [messages, setMessages] = useState<Msg[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [gate, setGate] = useState<Gate | null>(null);
  const [remaining, setRemaining] = useState(config.hitlTimeoutSecs);
  const bottomRef = useRef<HTMLDivElement>(null);

  const routes = Object.keys(config.routeLabel);
  const [chosenRoute, setChosenRoute] = useState<string>("");

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, gate]);

  // HITL countdown — mirrors the former Streamlit sidebar timer.
  useEffect(() => {
    if (!gate) return;
    const id = setInterval(() => {
      const elapsed = (Date.now() - gate.startedAt) / 1000;
      const left = Math.max(0, config.hitlTimeoutSecs - elapsed);
      setRemaining(left);
      if (left <= 0) {
        setGate(null);
        addAssistant("⏰ Routing confirmation timed out. Please re-send your question.");
      }
    }, 1000);
    return () => clearInterval(id);
  }, [gate, config.hitlTimeoutSecs]);

  function addAssistant(content: string, chart?: ChartSpec | null) {
    setMessages((m) => [...m, { role: "assistant", content, chart }]);
  }

  async function ask(question: string) {
    if (!question.trim() || busy || gate) return;
    setMessages((m) => [...m, { role: "user", content: question }]);
    setInput("");
    setBusy(true);
    try {
      const res: EnrichResult = await api.enrich(question);
      if (res.status === "error") {
        addAssistant(`Couldn't reach the enrichment service. Detail: \`${res.detail}\``);
      } else if (res.status === "out_of_scope") {
        addAssistant(
          "I can only help with brand performance — share trends, insurgent brand analysis, " +
            "and distribution/velocity. Please name a brand and category."
        );
      } else if (res.status === "incomplete") {
        if (res.ctx) setCtx(res.ctx);
        addAssistant(
          `I need a bit more to route this accurately — please specify: **${(res.missing ?? []).join(", ")}**.`
        );
      } else if (res.status === "gate") {
        setCtx(res.ctx ?? {});
        setChosenRoute(res.route ?? routes[0]);
        setGate({
          question,
          ctx: res.ctx ?? {},
          route: res.route ?? routes[0],
          routeLabel: res.routeLabel ?? "",
          routeWhy: res.routeWhy ?? "",
          sessionId: res.sessionId ?? "",
          startedAt: Date.now(),
        });
        setRemaining(config.hitlTimeoutSecs);
      }
    } catch (e: any) {
      addAssistant(`Request failed: ${e.message}`);
    } finally {
      setBusy(false);
    }
  }

  async function confirm() {
    if (!gate) return;
    const g = gate;
    setGate(null);
    setBusy(true);
    try {
      const res = await api.analyze(g.question, chosenRoute, g.ctx, g.sessionId);
      addAssistant(res.text, res.chart);
    } catch (e: any) {
      addAssistant(`Analysis failed: ${e.message}`);
    } finally {
      setBusy(false);
    }
  }

  function cancel() {
    setGate(null);
    addAssistant("Cancelled. Rephrase your question or ask a new one.");
  }

  return (
    <div className="chat-wrap">
      <ContextPills ctx={ctx} />

      {messages.length === 0 && !gate && (
        <div>
          <p className="muted" style={{ fontWeight: 600, marginBottom: 10 }}>
            Suggested questions
          </p>
          <div className="suggestions">
            {config.suggested.map((q) => (
              <button key={q} className="suggestion" onClick={() => ask(q)}>
                {q}
              </button>
            ))}
          </div>
        </div>
      )}

      <div className="bubbles">
        {messages.map((m, i) => (
          <div key={i} className={`bubble ${m.role}`}>
            <div className="role">{m.role === "user" ? "You" : "🤖 BPM Advisor"}</div>
            {m.content}
            {m.chart && (
              <div style={{ marginTop: 12, background: "#fff", borderRadius: 12 }}>
                <SpecChart spec={m.chart} />
              </div>
            )}
          </div>
        ))}
        {busy && (
          <div className="bubble assistant">
            <span className="spinner" /> {gate ? "Analysing…" : "Understanding your question…"}
          </div>
        )}
      </div>

      {gate && (
        <div className="gate">
          <h4>🔀 Confirm Routing</h4>
          <div className="row">
            <b>Question:</b> {gate.question.slice(0, 140)}
            {gate.question.length > 140 ? "…" : ""}
          </div>
          <div className="row">
            <b>Proposed route:</b>{" "}
            <code>{config.routeLabel[chosenRoute] ?? chosenRoute}</code>
          </div>
          <div className="why">Why: {config.routeWhy[chosenRoute] ?? gate.routeWhy}</div>
          <div className="why">
            Context — {gate.ctx.brand} · {gate.ctx.category} · {gate.ctx.retailer} ·{" "}
            {gate.ctx.time_window_weeks}W
          </div>

          <div className="progress-track">
            <div
              className="progress-fill"
              style={{ width: `${(remaining / config.hitlTimeoutSecs) * 100}%` }}
            />
          </div>
          <div className="why">⏱ {Math.round(remaining)}s remaining</div>

          <div style={{ marginTop: 12 }}>
            <label className="why" style={{ display: "block", marginBottom: 4 }}>
              Route
            </label>
            <select
              className="select"
              value={chosenRoute}
              onChange={(e) => setChosenRoute(e.target.value)}
              style={{ width: "100%" }}
            >
              {routes.map((r) => (
                <option key={r} value={r}>
                  {config.routeLabel[r]}
                </option>
              ))}
            </select>
          </div>

          <div className="actions">
            <button className="btn primary" onClick={confirm}>
              ✅ Confirm &amp; Run
            </button>
            <button className="btn" onClick={cancel}>
              ✖ Cancel
            </button>
          </div>
        </div>
      )}

      {gate ? (
        <Notice kind="info">⏳ Confirm the routing above to run the analysis.</Notice>
      ) : (
        <div className="composer">
          <input
            className="text-input"
            placeholder="Ask about brand performance, insurgent brands, or distribution…"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && ask(input)}
            disabled={busy}
          />
          <button className="btn navy" onClick={() => ask(input)} disabled={busy || !input.trim()}>
            Send
          </button>
        </div>
      )}
      <div ref={bottomRef} />
    </div>
  );
}
