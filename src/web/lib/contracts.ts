export type Vehicle = "xe_may" | "o_to";

export type ChatRequest = {
  question: string;
  vehicle_type?: Vehicle;
};

export type Fine = { min: number | null; max: number | null };

export type Penalty = {
  record_id: string;
  vehicle_type: Vehicle | "both";
  subject: string;
  record_kind: "fine" | "warning" | "additional_only";
  behavior: string;
  legal_path: string;
  fine: Fine;
  organization_fine: Fine | null;
  license_points: number;
  license_points_condition: string | null;
  additional_penalties: string[];
  remedial_measures: string[];
  verification_status: string;
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
  options: { record_id: string; label: string }[];
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
