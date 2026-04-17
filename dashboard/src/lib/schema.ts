import { z } from "zod";

// Mirrors eval/parseland_eval/report.py payload shape.
// Keep aligned with the Python side when fields are added.

const AuthorMatchSchema = z.object({
  gold_index: z.number(),
  parsed_index: z.number(),
  key_match: z.boolean(),
  name_ratio: z.number(),
});

const AuthorResultSchema = z.object({
  matched: z.array(AuthorMatchSchema),
  gold_unmatched: z.array(z.number()),
  parsed_unmatched: z.array(z.number()),
  precision: z.number(),
  recall: z.number(),
  f1: z.number(),
  precision_soft: z.number(),
  recall_soft: z.number(),
  f1_soft: z.number(),
});

const AffiliationResultSchema = z.object({
  strict_f1: z.number(),
  soft_f1: z.number(),
  fuzzy_f1: z.number(),
  matched: z.number(),
  gold_total: z.number(),
  parsed_total: z.number(),
});

const AbstractResultSchema = z.object({
  strict_match: z.boolean(),
  soft_ratio: z.number(),
  fuzzy_ratio: z.number(),
  length_ratio: z.number(),
  present: z.boolean(),
});

const PdfUrlResultSchema = z.object({
  strict_match: z.boolean(),
  present: z.boolean(),
  expected_present: z.boolean(),
  divergent: z.boolean(),
});

const RowScoreSchema = z.object({
  doi: z.string(),
  no: z.number(),
  publisher_domain: z.string(),
  parser_name: z.string().nullable(),
  duration_ms: z.number(),
  error: z.string().nullable(),
  gold_quality: z.string(),
  failure_modes: z.array(z.string()),
  has_bot_check: z.boolean().nullable(),
  authors: AuthorResultSchema.nullable(),
  affiliations: AffiliationResultSchema.nullable(),
  abstract: AbstractResultSchema,
  pdf_url: PdfUrlResultSchema,
  bot_check_flag: z.boolean(),
});

const GoldAuthorSchema = z.object({
  name: z.string(),
  affiliations: z.array(z.any()),
  is_corresponding: z.boolean().nullable(),
});

const RowPayloadSchema = z.object({
  no: z.number(),
  doi: z.string(),
  link: z.string(),
  publisher_domain: z.string(),
  gold: z.object({
    authors: z.array(GoldAuthorSchema),
    abstract: z.string().nullable(),
    pdf_url: z.string().nullable(),
    gold_quality: z.string(),
    failure_modes: z.array(z.string()),
    notes: z.string(),
    has_bot_check: z.boolean().nullable(),
    status: z.boolean(),
  }),
  parsed: z.object({
    authors: z.array(z.any()),
    abstract: z.string().nullable(),
    urls: z.array(z.any()),
    license: z.string().nullable(),
    version: z.string().nullable(),
  }),
  score: RowScoreSchema,
  error: z.string().nullable(),
  duration_ms: z.number(),
});

export const OverallSchema = z.object({
  rows: z.number(),
  authors_scored_rows: z.number(),
  authors_f1_strict: z.number(),
  authors_f1_soft: z.number(),
  affiliations_f1_strict: z.number(),
  affiliations_f1_soft: z.number(),
  affiliations_f1_fuzzy: z.number(),
  abstract_ratio_soft: z.number(),
  abstract_ratio_fuzzy: z.number(),
  abstract_strict_match_rate: z.number(),
  abstract_present_rate: z.number(),
  pdf_url_accuracy: z.number(),
  pdf_url_divergence_rate: z.number(),
  errors: z.number(),
  duration_ms_mean: z.number(),
});

export const PerPublisherEntrySchema = z.object({
  rows: z.number(),
  authors_f1_soft: z.number(),
  affiliations_f1_fuzzy: z.number(),
  abstract_ratio_fuzzy: z.number(),
  pdf_url_accuracy: z.number(),
  errors: z.number(),
});

export const PerFailureModeEntrySchema = z.object({
  rows: z.number(),
  authors_f1_soft: z.number(),
  abstract_ratio_fuzzy: z.number(),
  pdf_url_accuracy: z.number(),
});

export const RunSchema = z.object({
  run_id: z.string(),
  label: z.string().nullable().optional(),
  eval_version: z.string(),
  timestamp_utc: z.string(),
  summary: z.object({
    overall: OverallSchema,
    per_publisher: z.record(PerPublisherEntrySchema),
    per_failure_mode: z.record(PerFailureModeEntrySchema),
  }),
  rows: z.array(RowPayloadSchema),
});

export const IndexEntrySchema = z.object({
  file: z.string(),
  run_id: z.string().nullable(),
  label: z.string().nullable().optional(),
  timestamp_utc: z.string().nullable(),
  summary: OverallSchema.partial(),
});

export const IndexSchema = z.object({
  runs: z.array(IndexEntrySchema),
});

export type Run = z.infer<typeof RunSchema>;
export type Overall = z.infer<typeof OverallSchema>;
export type PerPublisher = Record<string, z.infer<typeof PerPublisherEntrySchema>>;
export type PerFailureMode = Record<string, z.infer<typeof PerFailureModeEntrySchema>>;
export type RowPayload = z.infer<typeof RowPayloadSchema>;
export type IndexEntry = z.infer<typeof IndexEntrySchema>;
export type Index = z.infer<typeof IndexSchema>;
