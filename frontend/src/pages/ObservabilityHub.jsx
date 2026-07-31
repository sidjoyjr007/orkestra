import React, { useState, useEffect } from "react"
import { Activity, Clock, Cpu, BarChart3, ShieldAlert } from "lucide-react"
import { PageHeader } from "@/components/PageHeader"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { API_BASE_URL } from "@/config"

export function ObservabilityHub() {
  const [runs, setRuns] = useState([])
  const [loading, setLoading] = useState(true)

  const fetchRuns = async () => {
    try {
      const res = await fetch(`${API_BASE_URL}/api/telemetry/runs`, { credentials: "include" })
      if (res.ok) {
        const data = await res.json()
        setRuns(data.items || [])
      }
    } catch (e) {
      console.error(e)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchRuns()
    const interval = setInterval(fetchRuns, 5000)
    return () => clearInterval(interval)
  }, [])

  return (
    <div className="space-y-6 w-full text-left">
      <PageHeader
        icon={<Activity className="h-4 w-4" />}
        title="Observability Hub"
        description="Monitor live telemetry, token usage, and events from isolated agent containers."
      />

      {/* High-level stats */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <StatCard title="Active Executions" value={runs.filter(r => r.status === "IN_PROGRESS").length} icon={<Cpu />} />
        <StatCard title="Total Runs" value={runs.length} icon={<Activity />} />
        <StatCard 
          title="Tokens Consumed" 
          value={runs.reduce((acc, r) => acc + (r.total_tokens || 0), 0)} 
          icon={<BarChart3 />} 
        />
        <StatCard title="Failed Executions" value={runs.filter(r => r.status === "FAILED").length} icon={<ShieldAlert />} />
      </div>

      {/* Runs Table */}
      <Card>
        <CardHeader>
          <CardTitle className="text-sm font-semibold uppercase tracking-wider text-muted-foreground">Recent Agent Executions</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="relative w-full overflow-auto">
            <table className="w-full caption-bottom text-sm">
              <thead className="[&_tr]:border-b">
                <tr className="border-b transition-colors hover:bg-muted/50 data-[state=selected]:bg-muted">
                  <th className="h-12 px-4 text-left align-middle font-medium text-muted-foreground">Status</th>
                  <th className="h-12 px-4 text-left align-middle font-medium text-muted-foreground">Agent ID</th>
                  <th className="h-12 px-4 text-left align-middle font-medium text-muted-foreground">Session</th>
                  <th className="h-12 px-4 text-left align-middle font-medium text-muted-foreground">Started</th>
                  <th className="h-12 px-4 text-right align-middle font-medium text-muted-foreground">Tokens</th>
                </tr>
              </thead>
              <tbody className="[&_tr:last-child]:border-0">
                {loading && runs.length === 0 ? (
                  <tr>
                    <td colSpan={5} className="p-4 text-center text-muted-foreground">Loading telemetry...</td>
                  </tr>
                ) : runs.length === 0 ? (
                  <tr>
                    <td colSpan={5} className="p-4 text-center text-muted-foreground">No telemetry data available.</td>
                  </tr>
                ) : (
                  runs.map(run => (
                    <tr key={run.id} className="border-b transition-colors hover:bg-muted/50">
                      <td className="p-4 align-middle">
                        <Badge variant={run.status === 'COMPLETED' ? 'default' : run.status === 'FAILED' ? 'destructive' : 'secondary'} className="text-[10px]">
                          {run.status}
                        </Badge>
                      </td>
                      <td className="p-4 align-middle font-mono text-xs">{run.agent_id.substring(0, 8)}...</td>
                      <td className="p-4 align-middle font-mono text-xs text-muted-foreground">{run.session_id}</td>
                      <td className="p-4 align-middle text-xs">
                        <div className="flex items-center gap-1.5">
                          <Clock className="h-3 w-3 text-muted-foreground" />
                          {new Date(run.start_time).toLocaleTimeString()}
                        </div>
                      </td>
                      <td className="p-4 align-middle text-right font-mono text-xs">{run.total_tokens}</td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}

function StatCard({ title, value, icon }) {
  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
        <CardTitle className="text-sm font-medium">{title}</CardTitle>
        <div className="h-4 w-4 text-muted-foreground">{icon}</div>
      </CardHeader>
      <CardContent>
        <div className="text-2xl font-bold">{value}</div>
      </CardContent>
    </Card>
  )
}
