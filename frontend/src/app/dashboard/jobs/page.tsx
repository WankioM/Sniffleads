"use client";

import { useState } from "react";
import Link from "next/link";
import { Header } from "@/components/layout/header";
import { JobStatusBadge } from "@/components/jobs/job-status-badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { useJobs } from "@/hooks/use-jobs";
import { formatDateTime, formatDuration } from "@/lib/utils";
import type { JobFilters } from "@/lib/api/jobs";

const statusOptions = [
  { value: "", label: "All Statuses" },
  { value: "running", label: "Running" },
  { value: "completed", label: "Completed" },
  { value: "failed", label: "Failed" },
  { value: "pending", label: "Pending" },
];

export default function JobsPage() {
  const [filters, setFilters] = useState<JobFilters>({
    ordering: "-created_at",
  });

  const { data, isLoading } = useJobs(filters);

  return (
    <>
      <Header title="Jobs" description="Monitor crawl job execution" />

      <div className="p-6 space-y-4">
        <div className="flex items-center gap-3">
          <Select
            value={filters.status ?? ""}
            onValueChange={(value) =>
              setFilters((f) => ({ ...f, status: value || undefined }))
            }
          >
            <SelectTrigger className="w-[160px]">
              <SelectValue placeholder="Status" />
            </SelectTrigger>
            <SelectContent>
              {statusOptions.map((opt) => (
                <SelectItem key={opt.value} value={opt.value}>
                  {opt.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <div className="rounded-lg border bg-white">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>ID</TableHead>
                <TableHead>Source</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Started</TableHead>
                <TableHead>Duration</TableHead>
                <TableHead>Leads Found</TableHead>
                <TableHead>Errors</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {isLoading ? (
                [...Array(5)].map((_, i) => (
                  <TableRow key={i}>
                    <TableCell><Skeleton className="h-4 w-12" /></TableCell>
                    <TableCell><Skeleton className="h-4 w-32" /></TableCell>
                    <TableCell><Skeleton className="h-5 w-20" /></TableCell>
                    <TableCell><Skeleton className="h-4 w-28" /></TableCell>
                    <TableCell><Skeleton className="h-4 w-16" /></TableCell>
                    <TableCell><Skeleton className="h-4 w-12" /></TableCell>
                    <TableCell><Skeleton className="h-4 w-12" /></TableCell>
                  </TableRow>
                ))
              ) : data?.results.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={7} className="text-center py-8 text-zinc-500">
                    No jobs found
                  </TableCell>
                </TableRow>
              ) : (
                data?.results.map((job) => (
                  <TableRow key={job.id} className="hover:bg-zinc-50">
                    <TableCell>
                      <Link href={`/jobs/${job.id}`} className="font-mono text-sm text-zinc-900 hover:underline">
                        #{job.id}
                      </Link>
                    </TableCell>
                    <TableCell className="font-medium">{job.site_config_name}</TableCell>
                    <TableCell><JobStatusBadge status={job.status} /></TableCell>
                    <TableCell className="text-zinc-500 text-sm">
                      {job.started_at ? formatDateTime(job.started_at) : "-"}
                    </TableCell>
                    <TableCell className="text-zinc-500 text-sm">
                      {formatDuration(job.duration_seconds)}
                    </TableCell>
                    <TableCell className="font-medium">{job.stats.leads_found}</TableCell>
                    <TableCell className={job.stats.error_count > 0 ? "text-red-600" : "text-zinc-500"}>
                      {job.stats.error_count}
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </div>
      </div>
    </>
  );
}