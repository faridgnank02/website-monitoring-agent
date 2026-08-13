"use client";

import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { api, streamChanges } from "@/lib/api";
import type { Stats, Change } from "@/lib/types";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Globe, AlertTriangle, Bell, TrendingUp, ArrowRight } from "lucide-react";
import { formatDistanceToNow } from "@/lib/utils";

interface FeedEvent {
  type: string;
  site_id?: number;
  change_score?: number;
  alert_sent?: boolean;
  timestamp?: string;
}

export default function OverviewPage() {
  const router = useRouter();
  const [stats, setStats] = useState<Stats | null>(null);
  const [changes, setChanges] = useState<Change[]>([]);
  const [feed, setFeed] = useState<FeedEvent[]>([]);
  const [loading, setLoading] = useState(true);

  const loadData = useCallback(async () => {
    try {
      const [s, c] = await Promise.all([api.getStats(), api.listChanges(10)]);
      setStats(s);
      setChanges(c);
    } catch {
      router.replace("/login");
    } finally {
      setLoading(false);
    }
  }, [router]);

  useEffect(() => {
    loadData();
    // Subscribe to SSE
    const unsub = streamChanges((data) => {
      const event = data as FeedEvent;
      if (event.type === "change_detected") {
        setFeed((prev) => [event, ...prev].slice(0, 20));
        loadData(); // refresh stats
      }
    });
    return unsub;
  }, [loadData]);

  const scoreColor = (score: number) => {
    if (score >= 30) return "destructive";
    if (score >= 15) return "secondary";
    if (score >= 5) return "outline";
    return "outline";
  };

  return (
    <div className="p-6 space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-foreground">Overview</h1>
        <p className="text-sm text-muted-foreground">Real-time change monitoring across all your sites</p>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {loading ? (
          Array.from({ length: 4 }).map((_, i) => (
            <Card key={i}><CardContent className="p-4"><Skeleton className="h-12 w-full" /></CardContent></Card>
          ))
        ) : (
          <>
            <KpiCard
              icon={<Globe className="h-4 w-4" />}
              label="Sites Monitored"
              value={stats?.total_sites ?? 0}
              sub={`${stats?.active_sites ?? 0} active`}
            />
            <KpiCard
              icon={<AlertTriangle className="h-4 w-4" />}
              label="Changes This Week"
              value={stats?.changes_this_week ?? 0}
              sub={`avg ${stats?.avg_change_score ?? 0}% change`}
            />
            <KpiCard
              icon={<Bell className="h-4 w-4" />}
              label="Alerts Sent"
              value={stats?.alerts_sent_this_week ?? 0}
              sub="this week"
            />
            <KpiCard
              icon={<TrendingUp className="h-4 w-4" />}
              label="Top Use Case"
              value={
                Object.entries(stats?.use_case_breakdown ?? {}).sort((a, b) => b[1] - a[1])[0]?.[0] ?? "—"
              }
              sub={`${Object.keys(stats?.use_case_breakdown ?? {}).length} categories`}
            />
          </>
        )}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Recent Changes */}
        <Card className="lg:col-span-2">
          <CardHeader className="flex flex-row items-center justify-between pb-3">
            <CardTitle className="text-sm font-medium">Recent Changes</CardTitle>
            <Link href="/sites" className="text-xs text-muted-foreground hover:text-foreground flex items-center gap-1">
              All sites <ArrowRight className="h-3 w-3" />
            </Link>
          </CardHeader>
          <CardContent className="space-y-2">
            {loading ? (
              Array.from({ length: 5 }).map((_, i) => <Skeleton key={i} className="h-10 w-full" />)
            ) : changes.length === 0 ? (
              <p className="text-sm text-muted-foreground py-4 text-center">No changes detected yet</p>
            ) : (
              changes.map((c) => (
                <div key={c.id} className="flex items-center justify-between py-2 border-b border-border last:border-0">
                  <div className="flex items-center gap-3">
                    <Badge variant={scoreColor(c.change_score)} className="font-mono text-xs w-14 justify-center">
                      {c.change_score.toFixed(1)}%
                    </Badge>
                    <div>
                      <p className="text-xs text-muted-foreground">
                        +{c.added_lines} −{c.removed_lines} lines
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    {c.alert_sent && <Badge variant="outline" className="text-xs">Alert sent</Badge>}
                    <span className="text-xs text-muted-foreground">{formatDistanceToNow(c.detected_at)}</span>
                  </div>
                </div>
              ))
            )}
          </CardContent>
        </Card>

        {/* Live Feed */}
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium flex items-center gap-2">
              <span className="inline-block w-2 h-2 rounded-full bg-green-500 animate-pulse" />
              Live Feed
            </CardTitle>
          </CardHeader>
          <CardContent>
            {feed.length === 0 ? (
              <p className="text-xs text-muted-foreground">Waiting for changes…</p>
            ) : (
              <ul className="space-y-2">
                {feed.map((ev, i) => (
                  <li key={i} className="text-xs text-muted-foreground border-l-2 border-primary pl-2">
                    Site #{ev.site_id} — {ev.change_score?.toFixed(1)}% change
                    {ev.alert_sent && " · alert sent"}
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

function KpiCard({ icon, label, value, sub }: { icon: React.ReactNode; label: string; value: string | number; sub: string }) {
  return (
    <Card>
      <CardContent className="p-4">
        <div className="flex items-center gap-2 text-muted-foreground mb-3">{icon}<span className="text-xs">{label}</span></div>
        <p className="text-2xl font-semibold text-foreground font-mono">{value}</p>
        <p className="text-xs text-muted-foreground mt-1">{sub}</p>
      </CardContent>
    </Card>
  );
}
