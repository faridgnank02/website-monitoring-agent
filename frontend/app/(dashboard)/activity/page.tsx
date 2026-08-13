"use client";

import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { api } from "@/lib/api";
import type { Change } from "@/lib/types";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { ArrowRight, Bell } from "lucide-react";
import { formatDistanceToNow } from "@/lib/utils";

export default function ActivityPage() {
  const router = useRouter();
  const [changes, setChanges] = useState<Change[]>([]);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    try {
      const data = await api.listChanges(100);
      setChanges(data);
    } catch {
      router.replace("/login");
    } finally {
      setLoading(false);
    }
  }, [router]);

  useEffect(() => { load(); }, [load]);

  const scoreVariant = (score: number) => {
    if (score >= 30) return "destructive" as const;
    if (score >= 15) return "secondary" as const;
    return "outline" as const;
  };

  return (
    <div className="p-6 space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-foreground">Activity</h1>
        <p className="text-sm text-muted-foreground">All detected changes across your monitored sites</p>
      </div>

      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-sm font-medium flex items-center gap-2">
            <Bell className="h-4 w-4" />
            Change Log
            <span className="text-muted-foreground font-normal">({changes.length})</span>
          </CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          {loading ? (
            <div className="p-4 space-y-3">
              {Array.from({ length: 8 }).map((_, i) => (
                <Skeleton key={i} className="h-12 w-full" />
              ))}
            </div>
          ) : changes.length === 0 ? (
            <p className="text-sm text-muted-foreground p-8 text-center">
              No changes detected yet. Add sites and run checks to see activity.
            </p>
          ) : (
            <div className="divide-y divide-border">
              {changes.map((c) => (
                <div key={c.id} className="flex items-center justify-between px-4 py-3 hover:bg-accent/30 transition-colors">
                  <div className="flex items-center gap-3">
                    <Badge variant={scoreVariant(c.change_score)} className="font-mono text-xs w-16 justify-center shrink-0">
                      {c.change_score.toFixed(1)}%
                    </Badge>
                    <div>
                      <div className="flex items-center gap-2 text-xs">
                        <span className="text-green-400">+{c.added_lines}</span>
                        <span className="text-red-400">−{c.removed_lines}</span>
                        <span className="text-muted-foreground">~{c.modified_lines} modified</span>
                        {c.alert_sent && (
                          <Badge variant="outline" className="text-xs py-0">
                            <Bell className="h-2.5 w-2.5 mr-1" />Alert sent
                          </Badge>
                        )}
                      </div>
                      {c.diff_summary && (
                        <p className="text-xs text-muted-foreground mt-0.5 line-clamp-1">{c.diff_summary.split("\n")[0]}</p>
                      )}
                    </div>
                  </div>
                  <div className="flex items-center gap-3 shrink-0">
                    <span className="text-xs text-muted-foreground">{formatDistanceToNow(c.detected_at)}</span>
                    {c.new_snapshot_id && (
                      <Link
                        href={`/sites/${c.id}`}
                        className="text-muted-foreground hover:text-foreground transition-colors"
                      >
                        <ArrowRight className="h-4 w-4" />
                      </Link>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
