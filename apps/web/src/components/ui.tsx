"use client";
import { useEffect, useState } from "react";
import { api, ApiError } from "@/lib/api";
import { useLocale } from "./locale";
import { Panel } from "./kit/panel";
import { StatusChip, humanise, statusOf } from "./kit/status-chip";
export function useResource<T>(path: string | null) {
  const [state, setState] = useState<{
    data?: T;
    error?: unknown;
    loading: boolean;
  }>({ loading: !!path });
  const [revision, setRevision] = useState(0);
  useEffect(() => {
    if (!path) return;
    const controller = new AbortController();
    setState({ loading: true });
    api<T>(path, { signal: controller.signal })
      .then((data) => setState({ data, loading: false }))
      .catch((error) => {
        if (!controller.signal.aborted) setState({ error, loading: false });
      });
    return () => controller.abort();
  }, [path, revision]);
  return { ...state, reload: () => setRevision((v) => v + 1) };
}
export function ErrorNotice({ error }: { error: unknown }) {
  const { t } = useLocale();
  if (!error) return null;
  const e = error instanceof ApiError ? error : null;
  return (
    <div role="alert" className="notice danger">
      <strong>
        {t("Request not confirmed", "請求未獲確認")}
        {e ? ` · ${e.status}` : ""}
      </strong>
      <p>
        {error instanceof Error
          ? error.message
          : t("An unexpected error occurred.", "發生未預期錯誤。")}
      </p>
      {e?.problem.code ? <code>{e.problem.code}</code> : null}
      {e?.problem.correlation_id ? (
        <p>
          {t("Support reference", "支援參考編號")}:{" "}
          <code>{e.problem.correlation_id}</code>
        </p>
      ) : null}
      {e?.status === 401 ? (
        <a href="/login">{t("Sign in again", "重新登入")}</a>
      ) : null}
      {e?.status === 409 ? (
        <p>
          {t(
            "The record has changed. Refresh and review the current version before a new decision.",
            "紀錄已變更。請重新整理並核對最新版本，才再次決策。",
          )}
        </p>
      ) : null}
    </div>
  );
}
export function Loading() {
  const { t } = useLocale();
  return (
    <p role="status" className="empty loading">
      {t("Loading operational records…", "正在載入作業紀錄……")}
    </p>
  );
}
export function Empty({ children }: { children: React.ReactNode }) {
  return <div className="empty">{children}</div>;
}
export function Badge({ value }: { value: string }) {
  return <StatusChip status={statusOf(value)}>{humanise(value)}</StatusChip>;
}
export function PageHeader({
  title,
  description,
  action,
}: {
  /** Kept for callers; the rail and the title already say where you are. */
  eyebrow?: string;
  title: string;
  description: string;
  action?: React.ReactNode;
}) {
  return (
    <header className="page-header">
      <div>
        <h1>{title}</h1>
        <p className="lede">{description}</p>
      </div>
      {action ? <div className="page-header-action">{action}</div> : null}
    </header>
  );
}
export function Time({
  value,
  zone = "UTC",
}: {
  value: string | null | undefined;
  zone?: string;
}) {
  const { locale } = useLocale();
  if (!value) return <span>—</span>;
  return (
    <time dateTime={value} title={value}>
      {new Intl.DateTimeFormat(locale, {
        timeZone: zone,
        year: "numeric",
        month: "short",
        day: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
        hourCycle: "h23",
        timeZoneName: "short",
      }).format(new Date(value))}
    </time>
  );
}
export function Hash({ value }: { value: string }) {
  return (
    <code className="hash" title={value}>
      {value}
    </code>
  );
}
export function JsonDetails({
  value,
  label,
}: {
  value: unknown;
  label: string;
}) {
  return (
    <details className="raw">
      <summary>{label}</summary>
      <pre>{JSON.stringify(value, null, 2)}</pre>
    </details>
  );
}
export function Section({
  title,
  children,
  aside,
}: {
  title: string;
  children: React.ReactNode;
  aside?: React.ReactNode;
}) {
  return (
    <Panel title={title} aside={aside}>
      {children}
    </Panel>
  );
}
export function Table({
  headers,
  children,
  caption,
}: {
  headers: string[];
  children: React.ReactNode;
  caption: string;
}) {
  return (
    <div className="table-wrap" tabIndex={0} role="region" aria-label={caption}>
      <table>
        <caption>{caption}</caption>
        <thead>
          <tr>
            {headers.map((h) => (
              <th key={h} scope="col">
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>{children}</tbody>
      </table>
    </div>
  );
}
