"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { createProject, listProjects } from "@/lib/api";
import type { Project } from "@/lib/types";

export default function ProjectsPage() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [name, setName] = useState("");
  const [clientName, setClientName] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  async function refresh() {
    try {
      setProjects(await listProjects());
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    refresh();
  }, []);

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    if (!name.trim()) return;
    await createProject(name.trim(), clientName.trim());
    setName("");
    setClientName("");
    refresh();
  }

  return (
    <div>
      <h1>Projects</h1>

      <div className="panel">
        <h2>New engagement</h2>
        <form onSubmit={handleCreate} className="form-row">
          <input
            type="text"
            placeholder="Project name"
            value={name}
            onChange={(e) => setName(e.target.value)}
          />
          <input
            type="text"
            placeholder="Client name"
            value={clientName}
            onChange={(e) => setClientName(e.target.value)}
          />
          <button type="submit">Create project</button>
        </form>
      </div>

      <div className="panel">
        {loading && <p className="muted">Loading...</p>}
        {error && <p className="error-text">{error}</p>}
        {!loading && projects.length === 0 && <p className="muted">No projects yet.</p>}
        <ul className="project-list">
          {projects.map((p) => (
            <li key={p.id}>
              <Link href={`/projects/${p.id}`}>{p.name}</Link>
              <div className="project-meta">
                {p.client_name || "no client set"} - status: {p.status} - created{" "}
                {new Date(p.created_at).toLocaleString()}
              </div>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
