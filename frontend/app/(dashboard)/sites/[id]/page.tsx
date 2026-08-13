"use client";

import { useEffect, useState, useCallback } from "react";
import { useRouter, useParams } from "next/navigation";
import { api } from "@/lib/api";
import type { SiteHistory, Change, Diff } from "@/lib/types";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Separator } from "@/components/ui/separator";
import { ArrowLeft, Play, ExternalLink, Clock } from "lucide-react";
import Link from "next/link";
import { formatDistanceToNow } from "@/lib/utils";

export default function SiteDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [history, setHistory] = useState<SiteHistory | null>(null);
  const [selectedChange, setSelectedChange] = useState<Change | null>(null);
  const [diff, setDiff] = useState<Diff | null>(null);
  const [diffLoading, setDiffLoading] = useState(false);
  const [triggering, setTriggering] = useState(false);

  const load = useCallback(async () => {
    try {
      const h = await api.getSiteHistory(Number(id));
      setHistory(h);
      if (h.changes.length > 0 && !selectedChange) {
        setSelectedChange(h.changes[0]);
      }
    } catch {
      router.replace("/login");
    }
  }, [id, router, selectedChange]);

  useEffect(() => { load(); }, [load]);

  useEffect(() => {
    if (!selectedChange) return;
    setDiffLoading(true);
    api.getDiff(selectedChange.id)
      .then(setDiff)
      .finally(() => setDiffLoading(false));
  }, [selectedChange]);

  async function triggerNow() {
    setTriggering(true);
    await api.triggerCheck(Number(id));
    setTimeout(load, 4000);
    setTriggering(false);
  }

  const site = history?.site;

  const scoreVariant = (score: number) => {
    if (score >= 30) return "destructive";
    if (score >= 15) return "secondary";
    return "outline";
  };

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Link href="/sites">
            <Button variant="ghost" size="icon" className="h-8 w-8">
              <ArrowLeft className="h-4 w-4" />
            </Button>
          </Link>
          <div>
            {site ? (
              <>
                <h1 className="text-base font-semibold text-foreground line-clamp-1">{site.instruction}</h1>
                <div className="flex items-center gap-2 mt-0.5">
                  {site.url && (
                    <a href={site.url} target="_blank" rel="noopener noreferrer"
                      className="text-xs text-muted-foreground hover:text-foreground flex items-center gap-1">
                      <ExternalLink className="h-3 w-3" />{new URL(site.url).hostname}
                    </a>
                  )}
                  <Badge variant="outline" className="text-xs">{site.use_case}</Badge>
                  <span className="text-xs text-muted-foreground">threshold {site.threshold}%</span>
                </div>
              </>
            ) : <Skeleton className="h-6 w-64" />}
          </div>
        </div>
        <Button size="sm" variant="outline" onClick={triggerNow} disabled={triggering} className="gap-1.5">
          {triggering ? (
            <span className="h-4 w-4 animate-spin border-2 border-current border-t-transparent rounded-full" />
          ) : <Play className="h-4 w-4" />}
          Run now
        </Button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Change timeline */}
        <Card className="lg:col-span-1">
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium">Change History</CardTitle>
          </CardHeader>
          <CardContent className="p-0">
            {!history ? (
              <div className="p-4 space-y-2">{Array.from({ length: 5 }).map((_, i) => <Skeleton key={i} className="h-10 w-full" />)}</div>
            ) : history.changes.length === 0 ? (
              <p className="text-sm text-muted-foreground p-4 text-center">No changes recorded yet.<br/>Click &ldquo;Run now&rdquo; to check.</p>
            ) : (
              <ul>
                {history.changes.map((c, i) => (
                  <li key={c.id}>
                    <button
                      onClick={() => setSelectedChange(c)}
                      className={`w-full text-left px-4 py-3 flex items-center justify-between hover:bg-accent/50 transition-colors ${selectedChange?.id === c.id ? "bg-accent" : ""}`}
                    >
                      <div>
                        <div className="flex items-center gap-2">
                          <Badge variant={scoreVariant(c.change_score)} className="font-mono text-xs">
                            {c.change_score.toFixed(1)}%
                          </Badge>
                          {c.alert_sent && <span className="text-xs text-amber-500">⚡</span>}
                        </div>
                        <p className="text-xs text-muted-foreground mt-1 flex items-center gap-1">
                          <Clock className="h-3 w-3" />{formatDistanceToNow(c.detected_at)}
                        </p>
                      </div>
                      <div className="text-xs text-muted-foreground text-right">
                        <span className="text-green-500">+{c.added_lines}</span>
                        {" / "}
                        <span className="text-red-400">−{c.removed_lines}</span>
                      </div>
                    </button>
                    {i < history.changes.length - 1 && <Separator />}
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>

        {/* Diff viewer */}
        <Card className="lg:col-span-2">
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium">
              {selectedChange ? (
                <span className="flex items-center gap-2">
                  Diff — <Badge variant={scoreVariant(selectedChange.change_score)} className="font-mono text-xs">{selectedChange.change_score.toFixed(1)}% change</Badge>
                  <span className="text-muted-foreground font-normal">{formatDistanceToNow(selectedChange.detected_at)}</span>
                </span>
              ) : "Select a change to view diff"}
            </CardTitle>
          </CardHeader>
          <CardContent>
            {!selectedChange ? (
              <p className="text-sm text-muted-foreground">No change selected.</p>
            ) : diffLoading ? (
              <div className="space-y-2">{Array.from({ length: 8 }).map((_, i) => <Skeleton key={i} className="h-4 w-full" />)}</div>
            ) : diff ? (
              <DiffViewer diff={diff} />
            ) : null}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

function DiffViewer({ diff }: { diff: Diff }) {
  const oldLines = (diff.old_content || "").split("\n");
  const newLines = (diff.new_content || "").split("\n");

  // Build a simple line-by-line comparison
  const maxLen = Math.max(oldLines.length, newLines.length);
  const rows = Array.from({ length: Math.min(maxLen, 200) }, (_, i) => ({
    old: oldLines[i] ?? null,
    new: newLines[i] ?? null,
    changed: oldLines[i] !== newLines[i],
  }));

  const changed = rows.filter((r) => r.changed);

  if (changed.length === 0) {
    return <p className="text-sm text-muted-foreground">Content hash changed but no textual diff found.</p>;
  }

  return (
    <div className="space-y-4">
      {/* Summary */}
      {diff.diff_summary && (
        <div className="rounded-md bg-muted p-3 font-mono text-xs text-muted-foreground whitespace-pre-wrap">
          {diff.diff_summary}
        </div>
      )}

      {/* Side-by-side for changed lines only */}
      <div className="overflow-x-auto rounded-md border border-border">
        <table className="w-full text-xs font-mono">
          <thead>
            <tr className="border-b border-border bg-muted/50">
              <th className="px-3 py-2 text-left text-muted-foreground font-normal w-1/2">Before</th>
              <th className="px-3 py-2 text-left text-muted-foreground font-normal w-1/2">After</th>
            </tr>
          </thead>
          <tbody>
            {changed.slice(0, 50).map((row, i) => (
              <tr key={i} className="border-b border-border last:border-0">
                <td className={`px-3 py-1.5 align-top ${row.old !== null && row.old !== row.new ? "bg-red-950/30 text-red-300" : "text-muted-foreground"}`}>
                  {row.old ?? <span className="opacity-30">—</span>}
                </td>
                <td className={`px-3 py-1.5 align-top ${row.new !== null && row.old !== row.new ? "bg-green-950/30 text-green-300" : "text-muted-foreground"}`}>
                  {row.new ?? <span className="opacity-30">—</span>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {changed.length > 50 && (
          <p className="text-xs text-muted-foreground text-center py-2">
            Showing 50 of {changed.length} changed lines
          </p>
        )}
      </div>
    </div>
  );
}
