import { redirect } from "next/navigation";
import { principal } from "@/lib/server";
import { Shell } from "@/components/shell";
export const dynamic = "force-dynamic";
export default async function ConsoleLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const result = await principal();
  if (result.unavailable)
    return (
      <main className="service-error">
        <p className="eyebrow">CargoPulse</p>
        <h1>Operational service unavailable / 作業服務暫時無法使用</h1>
        <p>
          Session verification could not complete.
          作業服務恢復連線後，請重新嘗試。
        </p>
        <a className="button" href="/operations">
          Retry / 重試
        </a>
        <p>SYNTHETIC / NOT CONNECTED</p>
      </main>
    );
  if (!result.user) redirect("/login");
  return <Shell user={result.user}>{children}</Shell>;
}
