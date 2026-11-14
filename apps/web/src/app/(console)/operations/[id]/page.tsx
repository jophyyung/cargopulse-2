import { ScenarioWorkspace } from "@/components/scenario";
export default async function Page({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  return <ScenarioWorkspace id={(await params).id} />;
}
