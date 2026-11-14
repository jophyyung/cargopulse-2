import { PlanReview } from "@/components/plan";
export default async function Page({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  return <PlanReview id={(await params).id} />;
}
