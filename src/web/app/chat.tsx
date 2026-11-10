"use client";

import {
  ArrowRight, ArrowUp, BookOpenCheck, ChevronDown, CircleAlert, FileText,
  Gavel, MessageSquareText, Plus, Scale, ShieldCheck,
} from "lucide-react";
import { type FormEvent, type KeyboardEvent, useCallback, useEffect, useRef, useState } from "react";
import {
  type CatalogHealth, type ChatReply, type ChatRequest, type Vehicle, MAX_QUESTION_LENGTH, vehicleLabels,
} from "../lib/contracts";
import Answer, { formatDate } from "./answer";

const topics = [
  { label: "Mức phạt", icon: Scale, description: "Vi phạm, tiền phạt và điểm GPLX", prompt: "Xe máy vượt đèn đỏ bị phạt bao nhiêu?" },
  { label: "Nộp phạt", icon: FileText, description: "Nơi nộp, thời hạn và cách nộp", prompt: "Nộp phạt ở đâu, thời hạn bao lâu?" },
  { label: "Khiếu nại", icon: Gavel, description: "Thời hiệu và cách gửi khiếu nại", prompt: "Khiếu nại quyết định xử phạt như thế nào?" },
];

type Turn = { id: number; request: ChatRequest; reply?: ChatReply; error?: string };
type Connection = "checking" | "ready" | "offline";

function RouteIllustration() {
  return (
    <svg className="route-art" viewBox="0 0 328 270" fill="none" aria-hidden="true">
      <defs>
        <pattern id="route-grid" width="20" height="20" patternUnits="userSpaceOnUse">
          <path d="M20 0H0V20" stroke="#b9caf8" strokeOpacity=".47" />
        </pattern>
        <linearGradient id="route-gradient" x1="58" y1="244" x2="288" y2="14" gradientUnits="userSpaceOnUse">
          <stop stopColor="#88a9ff" /><stop offset="1" stopColor="#4c72ee" />
        </linearGradient>
      </defs>
      <circle cx="209" cy="133" r="114" fill="url(#route-grid)" />
      <circle cx="209" cy="133" r="114" stroke="#bbcdfb" strokeOpacity=".75" />
      <circle cx="209" cy="133" r="86" stroke="#c3d2fa" strokeDasharray="3 7" />
      <path d="M44 257 121 180a66 66 0 0 1 47-19h19a42 42 0 0 0 42-42v-13a48 48 0 0 1 14-34l58-58"
        stroke="#e1e9ff" strokeWidth="28" strokeLinecap="round" />
      <path d="M44 257 121 180a66 66 0 0 1 47-19h19a42 42 0 0 0 42-42v-13a48 48 0 0 1 14-34l58-58"
        stroke="url(#route-gradient)" strokeWidth="9" strokeLinecap="round" />
      <path d="M47 254 121 180a66 66 0 0 1 47-19h19a42 42 0 0 0 42-42v-13a48 48 0 0 1 14-34l58-58"
        stroke="#f7faff" strokeWidth="1.5" strokeDasharray="6 8" />
      <circle cx="121" cy="180" r="10" fill="white" stroke="#7293fa" strokeWidth="3" />
      <circle cx="229" cy="106" r="13" fill="white" stroke="#5b7dee" strokeWidth="3" />
      <circle cx="229" cy="106" r="4.5" fill="#5b7dee" />
      <path d="M300 28V15h-13" stroke="#4c72ee" strokeWidth="5" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M98 89h18m-9-9v18m170 93h15m-7.5-7.5v15" stroke="#8ba7f3" strokeWidth="2" strokeLinecap="round" />
    </svg>
  );
}

export default function Chat() {
  const [turns, setTurns] = useState<Turn[]>([]);
  const [draft, setDraft] = useState("");
  const [vehicle, setVehicle] = useState<Vehicle | "">("");
  const [busy, setBusy] = useState(false);
  const [connection, setConnection] = useState<Connection>("checking");
  const [snapshot, setSnapshot] = useState("");
  const input = useRef<HTMLTextAreaElement>(null);
  const scrollArea = useRef<HTMLDivElement>(null);
  const scrollTarget = useRef<number | null>(null);
  const active = useRef<AbortController | null>(null);
  const sequence = useRef(0);

  const checkConnection = useCallback(async (signal?: AbortSignal) => {
    setConnection("checking");
    try {
      const res = await fetch("/api/health", { cache: "no-store", signal });
      if (!res.ok) throw new Error();
      const data: CatalogHealth = await res.json();
      if (data.status !== "ok") throw new Error();
      if (!signal?.aborted) {
        setSnapshot(data.as_of);
        setConnection("ready");
      }
    } catch {
      if (!signal?.aborted) setConnection("offline");
    }
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    void checkConnection(controller.signal);
    return () => {
      controller.abort();
      active.current?.abort();
      active.current = null;
    };
  }, [checkConnection]);

  useEffect(() => {
    const area = scrollArea.current;
    if (!area) return;
    const target = area.querySelector(`#turn-${scrollTarget.current}`);
    area.scrollTop = target ? area.scrollTop + target.getBoundingClientRect().top - area.getBoundingClientRect().top - 12 : 0;
  }, [turns, busy]);

  async function ask(request: ChatRequest, retry?: number) {
    const question = request.question.trim();
    if (!question || question.length > MAX_QUESTION_LENGTH || active.current) return;
    const controller = new AbortController();
    active.current = controller;
    const id = retry ?? ++sequence.current;
    scrollTarget.current = id;
    const turn = { id, request: { ...request, question } };
    setBusy(true);
    setTurns((previous) => retry === undefined
      ? [...previous, turn]
      : previous.map((item) => item.id === id ? turn : item));
    if (retry === undefined) setDraft("");
    let failureMessage = "Kết nối bị gián đoạn. Bạn thử gửi lại câu hỏi nhé.";
    try {
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(turn.request),
        signal: controller.signal,
      });
      const data = await res.json().catch(() => null);
      if (active.current !== controller) return;
      if (!res.ok) {
        if (res.status >= 500) setConnection("offline");
        failureMessage = typeof data?.detail === "string" ? data.detail : "Chưa thể gửi câu hỏi. Bạn thử lại nhé.";
        throw new Error();
      }
      if (!data || typeof data.answer !== "string" || !Array.isArray(data.sources) || !Array.isArray(data.options) || !Array.isArray(data.related)) {
        failureMessage = "Hệ thống trả về dữ liệu chưa đầy đủ. Bạn thử gửi lại câu hỏi nhé.";
        throw new Error();
      }
      const reply: ChatReply = data;
      setTurns((previous) => previous.map((item) => item.id === id ? { ...item, reply } : item));
      setSnapshot(reply.as_of);
      setConnection("ready");
    } catch {
      if (active.current !== controller) return;
      setTurns((previous) => previous.map((item) => item.id === id ? { ...item, error: failureMessage } : item));
    } finally {
      if (active.current === controller) {
        active.current = null;
        setBusy(false);
      }
    }
  }

  function newConversation() {
    active.current?.abort();
    active.current = null;
    scrollTarget.current = null;
    setBusy(false);
    setTurns([]);
    setDraft("");
    setVehicle("");
    input.current?.focus();
  }

  function editQuestion(question: string, selected?: Vehicle) {
    setDraft(question);
    if (selected) setVehicle(selected);
    requestAnimationFrame(() => {
      input.current?.focus();
      input.current?.setSelectionRange(question.length, question.length);
    });
  }

  function submitDraft() {
    const question = draft.trim();
    const previous = turns.at(-1);
    if (previous?.reply?.reason === "vehicle_type") {
      const shortReply = question.toLocaleLowerCase("vi-VN").replace(/[.!?]+$/, "");
      const selected = shortReply === "xe máy" ? "xe_may" : shortReply === "ô tô" ? "o_to" : undefined;
      if (selected) {
        void ask({ ...previous.request, vehicle_type: selected });
        return;
      }
    }
    void ask({ question, vehicle_type: vehicle || undefined });
  }

  function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    submitDraft();
  }

  function onInputKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) {
      event.preventDefault();
      submitDraft();
    }
  }

  return (
    <div className="workspace">
      <aside className="sidebar">
        <div className="brand">
          <span className="brand-mark"><ShieldCheck size={25} aria-hidden="true" /></span>
          <div><strong>Trợ lý ATGT</strong><span>An toàn giao thông</span></div>
        </div>
        <button type="button" className="new-chat" onClick={newConversation}>
          <Plus size={20} aria-hidden="true" /> Trò chuyện mới
        </button>
        <nav className="side-navigation" aria-label="Chủ đề tra cứu">
          <p className="side-label">Chủ đề tra cứu</p>
          {topics.map(({ label, icon: Icon, prompt }) => (
            <button key={label} type="button" onClick={() => editQuestion(prompt)}>
              <Icon size={19} aria-hidden="true" /><span>{label}</span><ArrowRight className="side-arrow" size={15} aria-hidden="true" />
            </button>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <div className="sidebar-info">
            <BookOpenCheck size={21} aria-hidden="true" />
            <strong>Tra cứu có căn cứ</strong>
            <p>Đối chiếu điều khoản và mở văn bản nguồn ngay trong câu trả lời.</p>
          </div>
          <span className="sidebar-footer">{snapshot ? "Mốc dữ liệu " + formatDate(snapshot) : "Đồ án trợ lý giao thông"}</span>
        </div>
      </aside>

      <main className="main">
        <header className="topbar">
          <div className="topbar-title">
            <span className="topbar-icon"><MessageSquareText size={19} aria-hidden="true" /></span>
            <strong>Tra cứu giao thông</strong>
          </div>
          <div className="topbar-actions">
            <div className={"connection connection-" + connection} role="status">
              {connection === "offline" ? (
                <button type="button" onClick={() => void checkConnection()} title="Kiểm tra lại kết nối">
                  <span className="status-dot" /> Mất kết nối
                </button>
              ) : <><span className="status-dot" />{connection === "ready" ? "Đã kết nối" : "Đang kiểm tra"}</>}
            </div>
            <button type="button" className="mobile-new" onClick={newConversation} aria-label="Trò chuyện mới">
              <Plus size={21} aria-hidden="true" />
            </button>
          </div>
        </header>

        <div className="ai-warning" role="note">
          <CircleAlert size={16} aria-hidden="true" />
          <span><strong>Cảnh báo:</strong> Thông tin do AI tạo ra chỉ mang tính tham khảo, không thay thế văn bản pháp luật hoặc tư vấn pháp lý.</span>
        </div>

        <div className="chat-body">
          <div className="chat-scroll" ref={scrollArea}>
            {turns.length === 0 ? (
              <div className="welcome chat-width">
                <section className="hero">
                  <RouteIllustration />
                  <div className="hero-content">
                    <span className="eyebrow"><ShieldCheck size={16} aria-hidden="true" /> Trợ lý tra cứu</span>
                    <h1>Hỏi đáp luật<br />giao thông</h1>
                    <p>Tìm mức phạt, cách nộp phạt và thủ tục khiếu nại với căn cứ pháp lý để bạn đối chiếu.</p>
                  </div>
                </section>
                <div className="quick-heading">
                  <h2>Thử một câu hỏi</h2>
                  <span>Xe máy và ô tô</span>
                </div>
                <div className="quick-grid">
                  {topics.map(({ label, icon: Icon, description, prompt }) => (
                    <button className="quick-card" key={label} type="button" onClick={() => void ask({ question: prompt })}>
                      <span className="quick-top">
                        <span className="quick-icon"><Icon size={21} aria-hidden="true" /></span>
                        <ArrowRight size={17} className="quick-arrow" aria-hidden="true" />
                      </span>
                      <strong>{label}</strong>
                      <span>{description}</span>
                    </button>
                  ))}
                </div>
              </div>
            ) : (
              <div className="transcript chat-width" role="log" aria-label="Cuộc trò chuyện" aria-live="polite">
                {turns.map((turn) => (
                  <div className="turn" id={"turn-" + turn.id} key={turn.id}>
                    <div className="user-turn">
                      <span className="speaker">Bạn</span>
                      <div className="user-bubble">
                        <p>{turn.request.question}</p>
                        {turn.request.vehicle_type && <small>{vehicleLabels[turn.request.vehicle_type]}</small>}
                      </div>
                    </div>
                    <div className="assistant-turn">
                      <div className="assistant-label"><ShieldCheck size={17} aria-hidden="true" /> Trợ lý ATGT</div>
                      {turn.reply ? (
                        <Answer
                          reply={turn.reply}
                          pending={busy}
                          onChooseVehicle={(value) => void ask({ ...turn.request, vehicle_type: value })}
                          onChooseOption={(option) => void ask({ question: option.label, record_id: option.record_id })}
                          onEdit={() => editQuestion(turn.request.question, turn.request.vehicle_type)}
                        />
                      ) : turn.error ? (
                        <div className="request-error" role="alert">
                          <CircleAlert size={19} aria-hidden="true" />
                          <div><p>{turn.error}</p>
                            <button type="button" onClick={() => void ask(turn.request, turn.id)} disabled={busy}>Thử lại</button>
                          </div>
                        </div>
                      ) : (
                        <div className="thinking" role="status"><span className="spinner" /> Đang tra cứu dữ liệu…</div>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          <div className="composer-area">
            <div className="chat-width">
              <form className="composer" onSubmit={onSubmit} aria-label="Gửi câu hỏi">
                <label className="sr-only" htmlFor="question">Câu hỏi</label>
                <textarea
                  id="question"
                  aria-describedby="question-privacy"
                  ref={input}
                  value={draft}
                  onChange={(event) => setDraft(event.target.value)}
                  onKeyDown={onInputKeyDown}
                  placeholder="Nhập câu hỏi về giao thông…"
                  rows={2}
                  maxLength={MAX_QUESTION_LENGTH}
                />
                <div className="composer-actions">
                  <div className="vehicle-select">
                    <label htmlFor="vehicle">Loại xe</label>
                    <select id="vehicle" value={vehicle} onChange={(event) => setVehicle(event.target.value as Vehicle | "")}>
                      <option value="">Tự nhận diện</option>
                      <option value="xe_may">Xe máy</option>
                      <option value="o_to">Ô tô</option>
                    </select>
                    <ChevronDown size={14} aria-hidden="true" />
                  </div>
                  <button className="send" type="submit" disabled={busy || !draft.trim()}>
                    <span>{busy ? "Đang tra cứu" : "Gửi câu hỏi"}</span><ArrowUp size={18} aria-hidden="true" />
                  </button>
                </div>
              </form>
              <p className="composer-note" id="question-privacy">
                Câu hỏi có thể được lưu để cải thiện tra cứu. Vui lòng không nhập thông tin cá nhân.
              </p>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
