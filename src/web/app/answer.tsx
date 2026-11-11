import { ArrowUpRight, BadgeCheck, BookOpen, CircleHelp, FileText, Scale, ShieldAlert } from "lucide-react";
import { Fragment } from "react";
import { type ChatReply, type Fine, type Penalty, type Source, type Vehicle, vehicleLabels } from "../lib/contracts";

const number = new Intl.NumberFormat("vi-VN");
const subjectLabels: Record<string, string> = {
  chu_phuong_tien: "Chủ phương tiện",
  nguoi_dieu_khien: "Người điều khiển",
  nguoi_duoc_cho: "Người được chở",
};

export function formatDate(value: string) {
  const [year, month, day] = value.split("-");
  return year && month && day ? [day, month, year].join("/") : value;
}

function fineLabel({ min, max, unit, cap }: Fine) {
  if (min === null || max === null) return "Không phạt tiền";
  let label = min === max ? number.format(min) + " ₫" : number.format(min) + " – " + number.format(max) + " ₫";
  if (unit === "per_person") label += " / người vượt quá";
  if (cap !== null) label += " (tối đa " + number.format(cap) + " ₫)";
  return label;
}

function sourceUrl(value: string) {
  try {
    const url = new URL(value);
    return url.protocol === "https:" ? url : null;
  } catch {
    return null;
  }
}

function CitedText({ text, sources }: { text: string; sources: Source[] }) {
  return text.split(/(\[\d+\])/g).map((part, index) => {
    const match = /^\[(\d+)\]$/.exec(part);
    const source = match ? sources[Number(match[1]) - 1] : undefined;
    const url = source && sourceUrl(source.url);
    return url ? (
      <a
        className="citation-inline"
        key={index}
        href={url.href}
        target="_blank"
        rel="noopener noreferrer"
        aria-label={"Mở nguồn " + match?.[1]}
      >
        {part}
      </a>
    ) : <Fragment key={index}>{part}</Fragment>;
  });
}

function SourceList({ sources }: { sources: Source[] }) {
  return (
    <section className="sources" aria-label="Nguồn tham chiếu">
      <h3><BookOpen size={16} aria-hidden="true" /> Nguồn tham chiếu <span>{sources.length}</span></h3>
      <ol>
        {sources.map((source, index) => {
          const url = sourceUrl(source.url);
          const details = (
            <>
              <span className="source-number">{index + 1}</span>
              <span className="source-detail">
                <strong>{source.document}</strong>
                <span>{source.locator}</span>
                <small>
                  {url?.hostname}
                  {source.pages.length > 0 ? " · Trang " + source.pages.join(", ") : ""}
                </small>
              </span>
            </>
          );
          return (
            <li key={index}>
              {url ? (
                <a href={url.href} target="_blank" rel="noopener noreferrer">
                  {details}<ArrowUpRight size={17} aria-hidden="true" className="source-arrow" />
                </a>
              ) : <div className="source-unlinked">{details}</div>}
            </li>
          );
        })}
      </ol>
    </section>
  );
}

function PenaltyDetails({ penalty, sources }: { penalty: Penalty; sources: Source[] }) {
  const fine = penalty.record_kind === "warning" ? "Cảnh cáo" : fineLabel(penalty.fine);
  return (
    <>
      <div className="answer-tags">
        <span>{vehicleLabels[penalty.vehicle_type]}</span>
        <span>{subjectLabels[penalty.subject] ?? "Người điều khiển"}</span>
        {penalty.verification_status === "draft" && <span className="draft-tag">Dữ liệu dự thảo</span>}
      </div>
      <p className="behavior">{penalty.behavior}</p>
      <div className="penalty-facts">
        <div className="fact fact-primary">
          <span>{penalty.organization_fine ? "Mức phạt cá nhân" : "Mức xử phạt"}</span>
          <strong>{fine}</strong>
        </div>
        {penalty.organization_fine && (
          <div className="fact"><span>Mức phạt tổ chức</span><strong>{fineLabel(penalty.organization_fine)}</strong></div>
        )}
        <div className="fact">
          <span>Điểm GPLX bị trừ</span>
          {penalty.license_point_tiers.length > 0 ? (
            <>
              <strong>
                {number.format(penalty.license_point_tiers[0].points)}–
                {number.format(penalty.license_point_tiers[penalty.license_point_tiers.length - 1].points)} điểm
              </strong>
              {penalty.license_point_tiers.map((tier) => (
                <small key={tier.points}>Trừ {number.format(tier.points)} điểm nếu {tier.condition}</small>
              ))}
            </>
          ) : (
            <>
              <strong>{number.format(penalty.license_points)} điểm</strong>
              {penalty.license_points_condition && <small>Nếu {penalty.license_points_condition}</small>}
            </>
          )}
        </div>
      </div>
      {[
        { label: "Hình phạt bổ sung", values: penalty.additional_penalties },
        { label: "Biện pháp khắc phục", values: penalty.remedial_measures },
      ].map(({ label, values }) => values.length > 0 && (
        <section className="penalty-list" key={label}>
          <h3>{label}</h3>
          <ul>{values.map((value, index) => <li key={index}>{value}</li>)}</ul>
        </section>
      ))}
      {penalty.guidance.length > 0 && (
        <section className="penalty-guidance">
          <h3>Nộp phạt và khiếu nại</h3>
          <ul>
            {penalty.guidance.map((item) => (
              <li key={item.title}>
                <strong>{item.title}</strong>
                <p><CitedText text={item.text} sources={sources} /></p>
              </li>
            ))}
          </ul>
        </section>
      )}
      {penalty.source_quote && (
        <details className="legal-quote">
          <summary><BookOpen size={15} aria-hidden="true" /> Đoạn luật áp dụng</summary>
          {penalty.source_quote.split(" || ").map((part, index) => <p key={index}>{part}</p>)}
        </details>
      )}
    </>
  );
}

function MultiPenaltyDetails({ penalties, sources }: { penalties: Penalty[]; sources: Source[] }) {
  const finePenalties = penalties.filter((penalty) => penalty.record_kind === "fine" && penalty.fine.min !== null);
  const canTotal = finePenalties.length > 0
    && finePenalties.every((penalty) => penalty.fine.unit === null && penalty.fine.cap === null);
  const total = canTotal ? {
    min: finePenalties.reduce((sum, penalty) => sum + (penalty.fine.min ?? 0), 0),
    max: finePenalties.reduce((sum, penalty) => sum + (penalty.fine.max ?? 0), 0),
  } : null;
  const noTiers = penalties.every((penalty) => penalty.license_point_tiers.length === 0);
  const points = penalties.reduce((sum, penalty) => sum + penalty.license_points, 0);
  const extras = [...new Set(penalties.flatMap((penalty) => penalty.additional_penalties))];
  const remedies = [...new Set(penalties.flatMap((penalty) => penalty.remedial_measures))];
  const guidance = penalties.find((penalty) => penalty.guidance.length > 0)?.guidance ?? [];
  const vehicles = [...new Set(penalties.map((penalty) => vehicleLabels[penalty.vehicle_type]))];
  return (
    <>
      <div className="answer-tags">
        {vehicles.map((vehicle) => <span key={vehicle}>{vehicle}</span>)}
        <span>{penalties.length} hành vi</span>
        {penalties.some((penalty) => penalty.verification_status === "draft") && (
          <span className="draft-tag">Dữ liệu dự thảo</span>
        )}
      </div>
      <p className="multi-summary">
        Câu hỏi có {penalties.length} hành vi vi phạm độc lập. Mỗi hành vi được xử phạt riêng:
      </p>
      <ol className="multi-list">
        {penalties.map((penalty, index) => (
          <li className="multi-item" key={penalty.record_id}>
            <div className="multi-item-head">
              <span className="multi-index">{index + 1}</span>
              <div>
                <p className="behavior">{penalty.behavior}</p>
                {penalty.legal_basis && <small className="legal-basis">{penalty.legal_basis}</small>}
              </div>
            </div>
            <div className="penalty-facts">
              <div className="fact fact-primary">
                <span>{penalty.record_kind === "warning" ? "Hình thức xử phạt" : "Mức xử phạt"}</span>
                <strong>{penalty.record_kind === "warning" ? "Cảnh cáo" : fineLabel(penalty.fine)}</strong>
              </div>
              {penalty.organization_fine && (
                <div className="fact">
                  <span>Mức phạt tổ chức</span>
                  <strong>{fineLabel(penalty.organization_fine)}</strong>
                </div>
              )}
              <div className="fact">
                <span>Điểm GPLX bị trừ</span>
                {penalty.license_point_tiers.length > 0 ? (
                  <>
                    <strong>
                      {number.format(penalty.license_point_tiers[0].points)}–
                      {number.format(penalty.license_point_tiers[penalty.license_point_tiers.length - 1].points)} điểm
                    </strong>
                    {penalty.license_point_tiers.map((tier) => (
                      <small key={tier.points}>Trừ {number.format(tier.points)} điểm nếu {tier.condition}</small>
                    ))}
                  </>
                ) : (
                  <strong>{number.format(penalty.license_points)} điểm</strong>
                )}
              </div>
            </div>
            {penalty.additional_penalties.length > 0 && (
              <section className="penalty-list">
                <h3>Hình phạt bổ sung</h3>
                <ul>{penalty.additional_penalties.map((value, item) => <li key={item}>{value}</li>)}</ul>
              </section>
            )}
            {penalty.remedial_measures.length > 0 && (
              <section className="penalty-list">
                <h3>Biện pháp khắc phục</h3>
                <ul>{penalty.remedial_measures.map((value, item) => <li key={item}>{value}</li>)}</ul>
              </section>
            )}
          </li>
        ))}
      </ol>
      <section className="multi-total">
        <h3>Tổng hợp</h3>
        {total && (
          <div className="fact fact-primary">
            <span>Tổng mức phạt tiền (cộng các khung)</span>
            <strong>{fineLabel({ ...total, unit: null, cap: null })}</strong>
          </div>
        )}
        {!total && finePenalties.length > 0 && (
          <p>Không cộng gộp tổng tiền vì có khung tính theo người hoặc có mức trần.</p>
        )}
        {noTiers && <p>Tổng trừ điểm GPLX: <strong>{number.format(points)} điểm</strong>.</p>}
        {extras.length > 0 && <p>Hình phạt bổ sung: {extras.join("; ")}.</p>}
        {remedies.length > 0 && <p>Biện pháp khắc phục: {remedies.join("; ")}.</p>}
      </section>
      {guidance.length > 0 && (
        <section className="penalty-guidance">
          <h3>Nộp phạt và khiếu nại</h3>
          <ul>
            {guidance.map((item) => (
              <li key={item.title}>
                <strong>{item.title}</strong>
                <p><CitedText text={item.text} sources={sources} /></p>
              </li>
            ))}
          </ul>
        </section>
      )}
    </>
  );
}

const answerLabels = {
  penalty: { label: "Kết quả tra mức phạt", icon: Scale },
  procedure: { label: "Hướng dẫn thủ tục", icon: FileText },
  clarify: { label: "Chọn thông tin để tra mức phạt", icon: CircleHelp },
  refuse: { label: "Tra cứu có giới hạn", icon: ShieldAlert },
};

export default function Answer({
  reply,
  onChooseVehicle,
  onChooseOption,
  onEdit,
  pending,
}: {
  reply: ChatReply;
  onChooseVehicle: (vehicle: Vehicle) => void;
  onChooseOption: (option: { record_id: string; label: string }) => void;
  onEdit: () => void;
  pending: boolean;
}) {
  const { label, icon: Icon } = answerLabels[reply.answer_type];
  const title = reply.violations.length > 1 ? "Kết quả tra nhiều hành vi" : label;
  return (
    <article className={"answer-card answer-" + reply.answer_type}>
      <header className="answer-title"><Icon size={19} aria-hidden="true" /><h2>{title}</h2></header>
      {reply.violations.length > 1 ? (
        <MultiPenaltyDetails penalties={reply.violations} sources={reply.sources} />
      ) : reply.penalty ? <PenaltyDetails penalty={reply.penalty} sources={reply.sources} /> : (
        <div className="answer-prose">
          {reply.answer.split(/\n{2,}/).map((paragraph, index) => {
            const newline = paragraph.indexOf("\n");
            return (
              <section key={index}>
                {reply.answer_type === "procedure" && newline >= 0 ? (
                  <>
                    <h3>{paragraph.slice(0, newline)}</h3>
                    <p><CitedText text={paragraph.slice(newline + 1)} sources={reply.sources} /></p>
                  </>
                ) : <p><CitedText text={paragraph} sources={reply.sources} /></p>}
              </section>
            );
          })}
        </div>
      )}
      {reply.related.length > 0 && (
        <section className="related-penalties">
          <h3>So sánh loại xe khác</h3>
          <div className="clarification-actions">
            {reply.related.map((option) => (
              <button key={option.record_id} type="button" disabled={pending} onClick={() => onChooseOption(option)}>
                {option.label}
              </button>
            ))}
          </div>
        </section>
      )}
      {reply.answer_type === "clarify" && (
        <>
          {reply.options.length > 0 && (
            <ul className="clarification-options">
              {reply.options.map((option) => (
                <li key={option.record_id}>
                  <button type="button" disabled={pending} onClick={() => onChooseOption(option)}>
                    {option.label}
                  </button>
                </li>
              ))}
            </ul>
          )}
          <div className="clarification-actions">
            {reply.reason === "vehicle_type" && reply.options.length < 2 && (
              <>
                <button type="button" disabled={pending} onClick={() => onChooseVehicle("xe_may")}>Xe máy</button>
                <button type="button" disabled={pending} onClick={() => onChooseVehicle("o_to")}>Ô tô</button>
              </>
            )}
            <button type="button" onClick={onEdit} disabled={pending}>Bổ sung câu hỏi</button>
          </div>
        </>
      )}
      {reply.sources.length > 0 && (
        <>
          <SourceList sources={reply.sources} />
          <div className="answer-meta"><BadgeCheck size={15} aria-hidden="true" /> Mốc dữ liệu {formatDate(reply.as_of)}</div>
        </>
      )}
    </article>
  );
}
