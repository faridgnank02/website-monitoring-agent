"use client";

import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { api } from "@/lib/api";
import type { Site } from "@/lib/types";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
} from "@/components/ui/dialog";
import {
  Globe, Plus, Play, Pause, Trash2, ExternalLink, CheckCircle, AlertCircle, Clock, Pencil,
} from "lucide-react";
import { formatDistanceToNow } from "@/lib/utils";

const USE_CASES = [
  { value: "general", label: "General" },
  { value: "ecommerce_pricing", label: "E-commerce: Pricing" },
  { value: "ecommerce_stock", label: "E-commerce: Stock" },
  { value: "regulatory", label: "Regulatory" },
  { value: "press", label: "Press / News" },
  { value: "competitor", label: "Competitor Intel" },
];

const SCHEDULE_PRESETS = [
  { value: "*/15 * * * *", label: "Every 15 min" },
  { value: "*/30 * * * *", label: "Every 30 min" },
  { value: "0 * * * *", label: "Every hour" },
  { value: "0 */6 * * *", label: "Every 6 hours" },
  { value: "0 */12 * * *", label: "Every 12 hours" },
  { value: "0 8 * * *", label: "Daily (8 AM)" },
  { value: "custom", label: "Custom…" },
];

export default function SitesPage() {
  const router = useRouter();
  const [sites, setSites] = useState<Site[]>([]);
  const [loading, setLoading] = useState(true);
  const [adding, setAdding] = useState(false);
  const [triggering, setTriggering] = useState<number | null>(null);
  const [showAdd, setShowAdd] = useState(false);
  const [showEdit, setShowEdit] = useState(false);
  const [editing, setEditing] = useState(false);
  const [editSite, setEditSite] = useState<Site | null>(null);
  const [form, setForm] = useState({
    instruction: "",
    threshold: 2,
    use_case: "general",
    tags: "",
    schedule_cron: "0 */6 * * *",
    schedule_custom: "",
  });
  const [editForm, setEditForm] = useState({
    threshold: 2,
    use_case: "general",
    tags: "",
    schedule_cron: "0 */6 * * *",
    schedule_custom: "",
    active: true,
  });

  const loadSites = useCallback(async () => {
    try {
      const data = await api.listSites();
      setSites(data);
    } catch {
      router.replace("/login");
    } finally {
      setLoading(false);
    }
  }, [router]);

  useEffect(() => { loadSites(); }, [loadSites]);

  async function addSite() {
    if (!form.instruction.trim()) return;
    setAdding(true);
    try {
      const cron = form.schedule_cron === "custom" ? form.schedule_custom : form.schedule_cron;
      await api.createSite({
        instruction: form.instruction,
        threshold: form.threshold,
        use_case: form.use_case,
        tags: form.tags ? form.tags.split(",").map((t) => t.trim()) : [],
        schedule_cron: cron,
      });
      setShowAdd(false);
      setForm({ instruction: "", threshold: 2, use_case: "general", tags: "", schedule_cron: "0 */6 * * *", schedule_custom: "" });
      loadSites();
    } finally {
      setAdding(false);
    }
  }

  function openEdit(site: Site) {
    const isPreset = SCHEDULE_PRESETS.some((p) => p.value === site.schedule_cron);
    setEditSite(site);
    setEditForm({
      threshold: site.threshold,
      use_case: site.use_case,
      tags: site.tags.join(", "),
      schedule_cron: isPreset ? site.schedule_cron : "custom",
      schedule_custom: isPreset ? "" : site.schedule_cron,
      active: site.active,
    });
    setShowEdit(true);
  }

  async function saveEdit() {
    if (!editSite) return;
    setEditing(true);
    try {
      const cron = editForm.schedule_cron === "custom" ? editForm.schedule_custom : editForm.schedule_cron;
      await api.updateSite(editSite.id, {
        threshold: editForm.threshold,
        use_case: editForm.use_case,
        tags: editForm.tags ? editForm.tags.split(",").map((t) => t.trim()) : [],
        schedule_cron: cron,
        active: editForm.active,
      });
      setShowEdit(false);
      setEditSite(null);
      loadSites();
    } finally {
      setEditing(false);
    }
  }

  async function toggleActive(site: Site) {
    await api.updateSite(site.id, { active: !site.active });
    loadSites();
  }

  async function deleteSite(id: number) {
    if (!confirm("Delete this site and all its history?")) return;
    await api.deleteSite(id);
    loadSites();
  }

  async function trigger(id: number) {
    setTriggering(id);
    try {
      await api.triggerCheck(id);
      // Give backend a moment then reload
      setTimeout(loadSites, 3000);
    } finally {
      setTriggering(null);
    }
  }

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-foreground">Sites</h1>
          <p className="text-sm text-muted-foreground">
            {sites.filter((s) => s.active).length} of {sites.length} active
          </p>
        </div>
        <Button size="sm" onClick={() => setShowAdd(true)} className="gap-1.5">
          <Plus className="h-4 w-4" />
          Add site
        </Button>
      </div>

      {/* Site cards */}
      <div className="space-y-3">
        {loading ? (
          Array.from({ length: 3 }).map((_, i) => (
            <Card key={i}><CardContent className="p-4"><Skeleton className="h-16 w-full" /></CardContent></Card>
          ))
        ) : sites.length === 0 ? (
          <Card>
            <CardContent className="p-12 text-center">
              <Globe className="h-10 w-10 text-muted-foreground mx-auto mb-3" />
              <p className="text-sm text-muted-foreground">No sites yet. Add your first site to start monitoring.</p>
            </CardContent>
          </Card>
        ) : (
          sites.map((site) => (
            <Card key={site.id} className={site.active ? "" : "opacity-60"}>
              <CardContent className="p-4">
                <div className="flex items-start justify-between gap-4">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                      <StatusDot active={site.active} hasError={false} />
                      <Link
                        href={`/sites/${site.id}`}
                        className="text-sm font-medium text-foreground hover:text-primary truncate"
                      >
                        {site.instruction}
                      </Link>
                    </div>
                    <div className="flex items-center gap-2 flex-wrap">
                      {site.url && (
                        <a
                          href={site.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-xs text-muted-foreground hover:text-foreground flex items-center gap-1"
                        >
                          <ExternalLink className="h-3 w-3" />
                          {new URL(site.url).hostname}
                        </a>
                      )}
                      <Badge variant="outline" className="text-xs">{
                        USE_CASES.find((u) => u.value === site.use_case)?.label ?? site.use_case
                      }</Badge>
                      <span className="text-xs text-muted-foreground">threshold {site.threshold}%</span>
                      <span className="text-xs text-muted-foreground font-mono">
                        {SCHEDULE_PRESETS.find((p) => p.value === site.schedule_cron)?.label ?? site.schedule_cron}
                      </span>
                      {site.last_checked_at && (
                        <span className="text-xs text-muted-foreground flex items-center gap-1">
                          <Clock className="h-3 w-3" />
                          {formatDistanceToNow(site.last_checked_at)}
                        </span>
                      )}
                      {site.last_change_score != null && (
                        <Badge variant={site.last_change_score >= site.threshold ? "destructive" : "secondary"} className="text-xs font-mono">
                          {site.last_change_score.toFixed(1)}%
                        </Badge>
                      )}
                    </div>
                  </div>

                  <div className="flex items-center gap-1 shrink-0">
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-8 w-8"
                      title="Edit settings"
                      onClick={() => openEdit(site)}
                    >
                      <Pencil className="h-4 w-4" />
                    </Button>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-8 w-8"
                      title="Run check now"
                      onClick={() => trigger(site.id)}
                      disabled={triggering === site.id}
                    >
                      {triggering === site.id ? (
                        <span className="h-4 w-4 animate-spin border-2 border-current border-t-transparent rounded-full" />
                      ) : (
                        <Play className="h-4 w-4" />
                      )}
                    </Button>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-8 w-8"
                      title={site.active ? "Pause" : "Resume"}
                      onClick={() => toggleActive(site)}
                    >
                      {site.active ? <Pause className="h-4 w-4" /> : <Play className="h-4 w-4 text-green-500" />}
                    </Button>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-8 w-8 text-destructive hover:text-destructive"
                      onClick={() => deleteSite(site.id)}
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </div>
                </div>
              </CardContent>
            </Card>
          ))
        )}
      </div>

      {/* Add Site Dialog */}
      <Dialog open={showAdd} onOpenChange={setShowAdd}>
        <DialogContent className="sm:max-w-lg">
          <DialogHeader>
            <DialogTitle>Add site to monitor</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 py-2">
            <div className="space-y-1.5">
              <label className="text-sm font-medium">Instruction</label>
              <textarea
                value={form.instruction}
                onChange={(e) => setForm({ ...form, instruction: e.target.value })}
                rows={3}
                placeholder='e.g. "Monitor prices on the Nike homepage" or "Track regulatory updates on eur-lex.europa.eu"'
                className="w-full rounded-md border border-input bg-transparent px-3 py-2 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring resize-none"
              />
              <p className="text-xs text-muted-foreground">Describe in natural language what to monitor. AI will parse the URL and elements automatically.</p>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-1.5">
                <label className="text-sm font-medium">Use case</label>
                <select
                  value={form.use_case}
                  onChange={(e) => setForm({ ...form, use_case: e.target.value })}
                  className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                >
                  {USE_CASES.map((u) => <option key={u.value} value={u.value}>{u.label}</option>)}
                </select>
              </div>
              <div className="space-y-1.5">
                <label className="text-sm font-medium">Alert threshold (%)</label>
                <input
                  type="number"
                  value={form.threshold}
                  onChange={(e) => setForm({ ...form, threshold: Number(e.target.value) })}
                  min={0.1}
                  max={100}
                  step={0.5}
                  className="w-full rounded-md border border-input bg-transparent px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                />
              </div>
            </div>
            <div className="space-y-1.5">
              <label className="text-sm font-medium">Tags <span className="text-muted-foreground font-normal">(comma-separated, optional)</span></label>
              <input
                type="text"
                value={form.tags}
                onChange={(e) => setForm({ ...form, tags: e.target.value })}
                placeholder="pricing, competitor, uk"
                className="w-full rounded-md border border-input bg-transparent px-3 py-2 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
              />
            </div>
            <div className="space-y-1.5">
              <label className="text-sm font-medium">Check schedule</label>
              <select
                value={form.schedule_cron}
                onChange={(e) => setForm({ ...form, schedule_cron: e.target.value })}
                className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
              >
                {SCHEDULE_PRESETS.map((p) => <option key={p.value} value={p.value}>{p.label}</option>)}
              </select>
              {form.schedule_cron === "custom" && (
                <input
                  type="text"
                  value={form.schedule_custom}
                  onChange={(e) => setForm({ ...form, schedule_custom: e.target.value })}
                  placeholder="*/10 * * * *"
                  className="w-full rounded-md border border-input bg-transparent px-3 py-2 text-sm font-mono placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
                />
              )}
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowAdd(false)}>Cancel</Button>
            <Button onClick={addSite} disabled={adding || !form.instruction.trim()}>
              {adding ? "Adding…" : "Add site"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Edit Site Dialog */}
      <Dialog open={showEdit} onOpenChange={setShowEdit}>
        <DialogContent className="sm:max-w-lg">
          <DialogHeader>
            <DialogTitle>Edit site settings</DialogTitle>
          </DialogHeader>
          {editSite && (
            <div className="space-y-4 py-2">
              <div className="text-sm text-muted-foreground truncate">{editSite.instruction}</div>
              <div className="space-y-1.5">
                <label className="text-sm font-medium">Check schedule</label>
                <select
                  value={editForm.schedule_cron}
                  onChange={(e) => setEditForm({ ...editForm, schedule_cron: e.target.value })}
                  className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                >
                  {SCHEDULE_PRESETS.map((p) => <option key={p.value} value={p.value}>{p.label}</option>)}
                </select>
                {editForm.schedule_cron === "custom" && (
                  <input
                    type="text"
                    value={editForm.schedule_custom}
                    onChange={(e) => setEditForm({ ...editForm, schedule_custom: e.target.value })}
                    placeholder="*/10 * * * *"
                    className="w-full rounded-md border border-input bg-transparent px-3 py-2 text-sm font-mono placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
                  />
                )}
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-1.5">
                  <label className="text-sm font-medium">Use case</label>
                  <select
                    value={editForm.use_case}
                    onChange={(e) => setEditForm({ ...editForm, use_case: e.target.value })}
                    className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                  >
                    {USE_CASES.map((u) => <option key={u.value} value={u.value}>{u.label}</option>)}
                  </select>
                </div>
                <div className="space-y-1.5">
                  <label className="text-sm font-medium">Alert threshold (%)</label>
                  <input
                    type="number"
                    value={editForm.threshold}
                    onChange={(e) => setEditForm({ ...editForm, threshold: Number(e.target.value) })}
                    min={0.1}
                    max={100}
                    step={0.5}
                    className="w-full rounded-md border border-input bg-transparent px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                  />
                </div>
              </div>
              <div className="space-y-1.5">
                <label className="text-sm font-medium">Tags <span className="text-muted-foreground font-normal">(comma-separated, optional)</span></label>
                <input
                  type="text"
                  value={editForm.tags}
                  onChange={(e) => setEditForm({ ...editForm, tags: e.target.value })}
                  placeholder="pricing, competitor, uk"
                  className="w-full rounded-md border border-input bg-transparent px-3 py-2 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
                />
              </div>
              <div className="flex items-center gap-2">
                <input
                  type="checkbox"
                  id="edit-active"
                  checked={editForm.active}
                  onChange={(e) => setEditForm({ ...editForm, active: e.target.checked })}
                  className="rounded border-input"
                />
                <label htmlFor="edit-active" className="text-sm font-medium">Active</label>
              </div>
            </div>
          )}
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowEdit(false)}>Cancel</Button>
            <Button onClick={saveEdit} disabled={editing}>
              {editing ? "Saving…" : "Save changes"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

function StatusDot({ active, hasError }: { active: boolean; hasError: boolean }) {
  if (!active) return <div className="w-2 h-2 rounded-full bg-muted-foreground shrink-0" />;
  if (hasError) return <AlertCircle className="h-4 w-4 text-destructive shrink-0" />;
  return <CheckCircle className="h-4 w-4 text-green-500 shrink-0" />;
}
