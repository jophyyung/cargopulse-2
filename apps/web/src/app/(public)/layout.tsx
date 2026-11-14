import { PublicNotice } from "@/components/public-notice";
export const dynamic = "force-dynamic";
export default function PublicLayout({ children }: { children: React.ReactNode }) {
  return <PublicNotice>{children}</PublicNotice>;
}
