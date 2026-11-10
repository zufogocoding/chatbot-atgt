import { forwardCatalog } from "../../../lib/catalog-api";

export async function GET() {
  return forwardCatalog("/health", { method: "GET" });
}
