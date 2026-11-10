import { NextResponse } from "next/server";
import { forwardCatalog } from "../../../lib/catalog-api";
import { MAX_QUESTION_LENGTH } from "../../../lib/contracts";

export async function POST(request: Request) {
  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ detail: "Câu hỏi cần được gửi dưới dạng JSON." }, { status: 400 });
  }

  if (!body || typeof body !== "object") {
    return NextResponse.json({ detail: "Bạn hãy nhập một câu hỏi để tra cứu." }, { status: 422 });
  }
  const { question, vehicle_type, record_id } = body as Record<string, unknown>;
  if (typeof question !== "string" || !question.trim() || question.trim().length > MAX_QUESTION_LENGTH) {
    return NextResponse.json({ detail: "Câu hỏi cần có từ 1 đến 1.000 ký tự." }, { status: 422 });
  }
  if (vehicle_type !== undefined && vehicle_type !== "xe_may" && vehicle_type !== "o_to") {
    return NextResponse.json({ detail: "Bạn hãy chọn xe máy hoặc ô tô." }, { status: 422 });
  }
  if (record_id != null && (typeof record_id !== "string" || record_id.trim().length > 64)) {
    return NextResponse.json({ detail: "Mã bản ghi không hợp lệ." }, { status: 422 });
  }

  return forwardCatalog("/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question: question.trim(), vehicle_type, record_id }),
  });
}
