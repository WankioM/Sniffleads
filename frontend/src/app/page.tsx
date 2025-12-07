"use client";

import { Header } from "@/components/layout/header";
import { SourceCard } from "@/components/sources/source-card";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { useSources, useTriggerCrawl, useToggleSourceEnabled } from "@/hooks/use-sources";
import { Plus } from "lucide-react";
import { toast } from "sonner";

export default function SourcesPage() {
  const { data, isLoading } = useSources();
  const triggerCrawl = useTriggerCrawl();
  const toggleEnabled = useToggleSourceEnabled();

  const handleTriggerCrawl = async (id: number, name: string) => {
    try {
      await triggerCrawl.mutateAsync(id);
      toast.success("Crawl started", { description: `Started crawling ${name}` });
    } catch {
      toast.error("Error", { description: "Failed to start crawl" });
    }
  };

  const handleToggleEnabled = async (id: number, enabled: boolean) => {
    try {
      await toggleEnabled.mutateAsync({ id, enabled });
      toast.success(enabled ? "Source enabled" : "Source disabled");
    } catch {
      toast.error("Error", { description: "Failed to update source" });
    }
  };

  return (
    <>
      <Header
        title="Sources"
        description="Configure crawl sources and schedules"
        actions={
          <Button>
            <Plus className="h-4 w-4 mr-2" />
            Add Source
          </Button>
        }
      />

      <div className="p-6">
        {isLoading ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {[...Array(6)].map((_, i) => (
              <div key={i} className="rounded-lg border bg-white p-6">
                <Skeleton className="h-6 w-32 mb-2" />
                <Skeleton className="h-4 w-48 mb-4" />
                <Skeleton className="h-8 w-full" />
              </div>
            ))}
          </div>
        ) : data?.results.length === 0 ? (
          <div className="text-center py-12">
            <p className="text-zinc-500">No sources configured yet</p>
            <Button className="mt-4">
              <Plus className="h-4 w-4 mr-2" />
              Add Your First Source
            </Button>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {data?.results.map((source) => (
              <SourceCard
                key={source.id}
                source={source}
                onTriggerCrawl={() => handleTriggerCrawl(source.id, source.name)}
                onToggleEnabled={(enabled) => handleToggleEnabled(source.id, enabled)}
                isCrawling={triggerCrawl.isPending}
              />
            ))}
          </div>
        )}
      </div>
    </>
  );
}