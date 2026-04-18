import Link from "next/link";
import { api } from "@/lib/api";

export const dynamic = "force-dynamic";

export default async function UserPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;

  const [messages, memories] = await Promise.all([
    api.messages(id).catch(() => []),
    api.memories(id).catch(() => []),
  ]);

  return (
    <main className="space-y-10">
      <Link href="/" className="text-sm text-neutral-500 hover:underline">
        ← Back
      </Link>

      <section>
        <h2 className="mb-4 text-lg font-medium">🧠 Memories ({memories.length})</h2>
        {memories.length === 0 ? (
          <p className="text-sm text-neutral-500">No memories yet.</p>
        ) : (
          <ul className="space-y-2">
            {memories.map((m) => (
              <li
                key={m.id}
                className="flex items-start gap-3 rounded-lg border border-neutral-200 p-3 text-sm dark:border-neutral-800"
              >
                <span className="rounded-full bg-neutral-100 px-2 py-0.5 text-xs text-neutral-700 dark:bg-neutral-800 dark:text-neutral-300">
                  {m.type}
                </span>
                <span>{m.content}</span>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section>
        <h2 className="mb-4 text-lg font-medium">💬 Messages ({messages.length})</h2>
        {messages.length === 0 ? (
          <p className="text-sm text-neutral-500">No messages.</p>
        ) : (
          <ul className="space-y-3">
            {messages.map((m) => (
              <li
                key={m.id}
                className={`rounded-lg p-3 text-sm ${
                  m.role === "user"
                    ? "bg-blue-50 dark:bg-blue-950"
                    : "bg-neutral-100 dark:bg-neutral-900"
                }`}
              >
                <div className="mb-1 text-xs text-neutral-500">
                  {m.role} · {new Date(m.created_at).toLocaleString()}
                </div>
                <div className="whitespace-pre-wrap">{m.content}</div>
              </li>
            ))}
          </ul>
        )}
      </section>
    </main>
  );
}
