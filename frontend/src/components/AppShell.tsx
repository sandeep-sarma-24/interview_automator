import { Outlet } from "react-router-dom";
import TabBar from "./TabBar";

// Mobile-first shell: a centered column with a fixed bottom tab bar.
export default function AppShell() {
  return (
    <div className="mx-auto min-h-screen max-w-md pb-16">
      <main className="px-4 pt-4">
        <Outlet />
      </main>
      <TabBar />
    </div>
  );
}
