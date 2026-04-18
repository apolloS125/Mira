import Link from "next/link";
import { api } from "@/lib/api";

export const dynamic = "force-dynamic";

export default async function Home() {
  let users: Awaited<ReturnType<typeof api.users>> = [];
  let error: string | null = null;
  try {
    users = await api.users();
  } catch (e) {
    error = e instanceof Error ? e.message : String(e);
  }

  return (
    <main>
      <h1 className="mb-6 text-xl font-medium">Users</h1>
      {error && (
        <p className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700 dark:border-red-900 dark:bg-red-950 dark:text-red-200">
          Failed to load: {error}. Is the backend running on{" "}
          <code>http://localhost:8000</code>?
        </p>
      )}
      {!error && users.length === 0 && (
        <p className="text-sm text-neutral-500">No users yet. Chat with the bot on Telegram first.</p>
      )}
      <ul className="divide-y divide-neutral-200 rounded-xl border border-neutral-200 dark:divide-neutral-800 dark:border-neutral-800">
        {users.map((u) => (
          <li key={u.id}>
            <Link
              href={`/users/${u.id}`}
              className="flex items-center justify-between px-5 py-4 transition hover:bg-neutral-100 dark:hover:bg-neutral-900"
            >
              <div>
                <div className="font-medium">{u.first_name || "(no name)"}</div>
                <div className="text-sm text-neutral-500">
                  @{u.telegram_username || "—"} · TG {u.telegram_id}
                </div>
              </div>
              <span className="text-xs text-neutral-400">
                {new Date(u.created_at).toLocaleDateString()}
              </span>
            </Link>
          </li>
        ))}
      </ul>
    </main>
  );
}
