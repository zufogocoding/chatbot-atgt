export type Vehicle = "xe_may" | "o_to";

export type ChatRequest = {
  question: string;
  vehicle_type?: Vehicle;
  record_id?: string;
};

export type Fine = {
  min: number | null;
  max: number | null;
  unit: "per_person" | null;
  cap: number | null;
};

export type Guidance = { title: string; text: string };

export type Penalty = {
  record_id: string;
  vehicle_type: Vehicle | "both";
  subject: string;
  record_kind: "fine" | "warning" | "additional_only";
  behavior: string;
  legal_path: string;
  legal_basis: string | null;
  fine: Fine;
  organization_fine: Fine | null;
  license_points: number;
  license_points_condition: string | null;
  license_point_tiers: { points: number; condition: string }[];
  additional_penalties: string[];
  remedial_measures: string[];
  guidance: Guidance[];
  verification_status: string;
  source_quote: string;
};

export type Source = {
  document: string;
  locator: string;
  url: string;
  pages: number[];
};

export type ChatReply = {
  answer_type: "penalty" | "procedure" | "clarify" | "refuse";
  answer: string;
  as_of: string;
  disclaimer: string;
  reason: string | null;
  penalty: Penalty | null;
  violations: Penalty[];
  options: { record_id: string; label: string }[];
  related: { record_id: string; label: string }[];
  sources: Source[];
};

export type CatalogHealth = {
  status: "ok";
  as_of: string;
  violations: number;
  procedures: number;
};

export const MAX_QUESTION_LENGTH = 1000;

export const vehicleLabels = {
  xe_may: "Xe máy",
  o_to: "Ô tô",
  both: "Xe máy và ô tô",
};
