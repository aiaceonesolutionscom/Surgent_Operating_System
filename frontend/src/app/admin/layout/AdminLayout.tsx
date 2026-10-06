import { Outlet } from "react-router-dom";
import { AdminSidebar } from "./AdminSidebar";
import { AdminTopbar } from "./AdminTopbar";

export function AdminLayout() {
  return (
    <div className="min-h-screen bg-canvas font-sans text-ink">
      <AdminSidebar />
      <div className="lg:pl-[260px]">
        <AdminTopbar />
        <main className="mx-auto max-w-[1440px] px-6 py-8">
          <Outlet />
        </main>
      </div>
    </div>);

}
