import { NextResponse } from "next/server";

const UNAVAILABLE = "Chưa kết nối được với hệ thống tra cứu. Bạn thử lại sau nhé.";

export async function forwardCatalog(path: "/chat" | "/health", options: RequestInit) {
  const baseUrl = process.env.ATGT_API_URL || "http://127.0.0.1:8000";

  try {
    const upstream = await fetch(baseUrl.replace(/\/+$/, "") + path, {
      ...options,
      cache: "no-store",
      redirect: "error",
      signal: AbortSignal.timeout(12_000),
    });
    if (upstream.status >= 500) {
      return NextResponse.json({ detail: UNAVAILABLE }, { status: 503 });
    }
    const data: unknown = await upstream.json();
    return NextResponse.json(data, {
      status: upstream.status,
      headers: { "Cache-Control": "no-store" },
    });
  } catch {
    return NextResponse.json({ detail: UNAVAILABLE }, { status: 503 });
  }
}
