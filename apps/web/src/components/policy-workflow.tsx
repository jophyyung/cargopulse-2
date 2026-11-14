"use client";
import { useState } from "react";
import { api } from "@/lib/api";
import type { Model, Principal } from "@/lib/types";
import { useLocale } from "./locale";
import {
  Badge,
  ErrorNotice,
  Hash,
  JsonDetails,
  Section,
  useResource,
} from "./ui";
export function PolicyWorkflow({
  policies,
  onPublished,
}: {
  policies: Model<"RuleSet">[];
  onPublished: () => void;
}) {
  const { t } = useLocale();
  const me = useResource<Principal>("/me");
  const manager = me.data?.roles.includes("manager");
  const [input, setInput] = useState("");
  const [draft, setDraft] = useState<Model<"PolicyRecord">>();
  const [id, setId] = useState("");
  const [review, setReview] = useState<Model<"PolicyRecord">>();
  const [confirm, setConfirm] = useState("");
  const [checked, setChecked] = useState(false);
  const [error, setError] = useState<unknown>();
  const [busy, setBusy] = useState(false);
  async function run(fn: () => Promise<void>) {
    setBusy(true);
    setError(undefined);
    try {
      await fn();
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  }
  async function create(e: React.FormEvent) {
    e.preventDefault();
    await run(async () => {
      const policy = JSON.parse(input) as Model<"RuleSet">;
      const result = await api<Model<"PolicyRecord">>("/policies/drafts", {
        method: "POST",
        body: { policy } satisfies Model<"PolicyDraft">,
      });
      setDraft(result);
      setId(result.id);
      setReview(undefined);
    });
  }
  async function load(e: React.FormEvent) {
    e.preventDefault();
    setReview(undefined);
    setChecked(false);
    setConfirm("");
    await run(async () =>
      setReview(
        await api<Model<"PolicyRecord">>(`/policies/${encodeURIComponent(id)}`),
      ),
    );
  }
  async function publish() {
    if (!review) return;
    await run(async () => {
      const result = await api<Model<"PolicyRecord">>(
        `/policies/${review.id}/publish`,
        { method: "POST" },
      );
      setReview(result);
      onPublished();
    });
  }
  return (
    <>
      <div className="two-col">
        <Section title={t("Draft a new policy version", "建立新政策版本草稿")}>
          <p>
            {t(
              "Managers can draft a complete rule set. Published versions stay immutable. A different manager must review and publish.",
              "Manager 可建立完整規則集草稿。已發布版本維持不可變更。必須由另一位 Manager 審查並發布。",
            )}
          </p>
          <button
            className="button"
            disabled={!policies.length || busy || !manager}
            onClick={() => setInput(JSON.stringify(policies[0], null, 2))}
          >
            {t(
              "Copy a published policy as a starting point",
              "複製已發布政策作起點",
            )}
          </button>
          <form onSubmit={create}>
            <label>
              {t("RuleSet JSON", "RuleSet JSON")}
              <textarea
                className="json-input"
                rows={12}
                maxLength={200000}
                value={input}
                onChange={(e) => {
                  setInput(e.target.value);
                  setDraft(undefined);
                }}
                required
                spellCheck={false}
              />
            </label>
            <button className="button" disabled={!manager || busy || !input}>
              {t("Save draft for review", "儲存草稿供審查")}
            </button>
          </form>
          {draft ? (
            <div role="status" className="notice success">
              <Badge value={draft.state} />
              <p>
                {t(
                  "Share this draft ID with a different authorised manager.",
                  "請將此草稿 ID 分享給另一位獲授權 Manager。",
                )}
              </p>
              <Hash value={draft.id} />
              <Hash value={draft.policy_hash} />
            </div>
          ) : null}
        </Section>
        <Section title={t("Review & publish", "審查及發布")}>
          <p>
            {t(
              "Load the draft from the service by ID. Verify its complete content and hash. Self-publication is blocked by the service.",
              "使用 ID 從服務載入草稿。核對其完整內容及雜湊值。服務會阻止作者自行發布。",
            )}
          </p>
          <form onSubmit={load}>
            <label>
              {t("Draft ID", "草稿 ID")}
              <input
                required
                value={id}
                onChange={(e) => {
                  setId(e.target.value);
                  setReview(undefined);
                }}
                pattern="[a-fA-F0-9-]{36}"
                placeholder="UUID"
              />
            </label>
            <button className="button" disabled={!manager || !id || busy}>
              {t("Load draft for review", "載入草稿以審查")}
            </button>
          </form>
          {review ? (
            <div className="import-result">
              <Badge value={review.state} />
              <p>
                {t("Author", "作者")}: {review.authored_by}
              </p>
              <Hash value={review.policy_hash} />
              <JsonDetails
                value={review.policy}
                label={t("Review complete policy content", "檢視完整政策內容")}
              />
              <label className="checkbox">
                <input
                  type="checkbox"
                  checked={checked}
                  onChange={(e) => setChecked(e.target.checked)}
                />
                <span>
                  {t(
                    "I reviewed the full policy and hash, and I am a different manager from the author.",
                    "我已檢視完整政策及雜湊值，並且是與作者不同的 Manager。",
                  )}
                </span>
              </label>
              <label>
                {t("Type PUBLISH to confirm", "輸入 PUBLISH 以確認")}
                <input
                  value={confirm}
                  onChange={(e) => setConfirm(e.target.value)}
                  autoComplete="off"
                />
              </label>
              <button
                className="button primary"
                onClick={publish}
                disabled={
                  !manager ||
                  review.state !== "DRAFT" ||
                  review.authored_by === me.data?.subject ||
                  !checked ||
                  confirm !== "PUBLISH" ||
                  busy
                }
              >
                {t("Publish reviewed version", "發布已審查版本")}
              </button>
            </div>
          ) : null}
        </Section>
      </div>
      {!manager ? (
        <p className="fine">
          {t(
            "Manager role required for policy changes. Publication requires an independent reviewer with the same tenant scope.",
            "政策變更需要 Manager 角色。發布需要同一租戶範圍內的獨立審查者。",
          )}
        </p>
      ) : null}
      <ErrorNotice error={error} />
    </>
  );
}
