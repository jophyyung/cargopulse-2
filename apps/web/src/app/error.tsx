"use client";
export default function ErrorPage({ reset }: { reset: () => void }) {
  return (
    <main className="service-error">
      <h1>Workspace unavailable / 工作區暫時無法使用</h1>
      <p>No decision is confirmed. 未確認任何決策。</p>
      <button className="button" onClick={reset}>
        Retry / 重試
      </button>
    </main>
  );
}
