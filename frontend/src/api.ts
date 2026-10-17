export type Company = {
  id: string;
  name: string;
  domain: string;
  authorization: string;
  infrastructure_approved: boolean;
  blocked: boolean;
  domain_verified: boolean;
  dns_record: string;
  dns_value: string;
  employees: number;
  smtp_host: string;
  smtp_port: number;
  smtp_user: string;
  smtp_secret_env: string;
  smtp_tls: string;
  sender: string;
  approved_senders: string[];
  retention_days: number;
};
export type Employee = {
  id: string;
  full_name: string;
  email: string;
  department: string;
  excluded: boolean;
};
export type Template = {
  id: string;
  name: string;
  subject: string;
  html: string;
  signs: string[];
};
export type Campaign = {
  id: string;
  company_id: string;
  name: string;
  template_id: string;
  status: string;
  created_at: string;
  created_by: string;
  test_sent_at: string | null;
  approved_by: string | null;
  approver_name: string | null;
  approved_at: string | null;
  approval_document: string | null;
  error: string | null;
};
export type Recipient = {
  id: string;
  full_name: string;
  email: string;
  department: string;
  delivery: string;
  clicked_at: string | null;
  training_at: string | null;
  sent_at: string | null;
};
export type Stats = {
  campaign: Campaign;
  total: number;
  sent: number;
  failed: number;
  clicked: number;
  training_viewed: number;
  click_rate: number;
  recipients: Recipient[];
};
export type Audit = {
  id: string;
  actor: string;
  action: string;
  detail: string;
  created_at: string;
};
let csrf = "";
export function setCsrf(value: string) {
  csrf = value;
}
export async function api<T>(
  path: string,
  method = "GET",
  data?: unknown,
): Promise<T> {
  const form = data instanceof FormData;
  const response = await fetch("/api" + path, {
    method,
    credentials: "same-origin",
    headers: {
      ...(form ? {} : { "Content-Type": "application/json" }),
      ...(method !== "GET" ? { "X-CSRF-Token": csrf } : {}),
    },
    body: data === undefined ? undefined : form ? data : JSON.stringify(data),
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    const detail = body.detail;
    throw new Error(
      typeof detail === "string"
        ? detail
        : Array.isArray(detail)
          ? detail.map((d: { msg: string }) => d.msg).join("; ")
          : "Не удалось выполнить запрос",
    );
  }
  return response.json();
}
export const scoped = (id: string, company: string, action = "") =>
  `/campaigns/${id}${action}?company_id=${encodeURIComponent(company)}`;
export const date = (value: string | null) =>
  value
    ? new Date(value).toLocaleString("ru-RU", {
        dateStyle: "short",
        timeStyle: "short",
      })
    : "—";
