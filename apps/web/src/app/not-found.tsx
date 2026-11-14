import Link from "next/link";
export default function NotFound() {
  return (
    <main className="service-error">
      <h1>Record not found / 找不到紀錄</h1>
      <p>The requested page is unavailable. 所要求頁面無法使用。</p>
      <Link className="button" href="/operations">
        Recovery desk / 復原作業台
      </Link>
    </main>
  );
}
