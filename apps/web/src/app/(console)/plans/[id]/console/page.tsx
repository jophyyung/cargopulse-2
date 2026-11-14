import { DispatchConsole } from "@/components/dispatch";
export default async function Page({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  return <DispatchConsole id={(await params).id} />;
}
