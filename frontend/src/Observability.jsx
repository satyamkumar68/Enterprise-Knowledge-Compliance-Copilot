
import { useCallback, useEffect, useState } from "react";
import {
    Activity,
    AlertTriangle,
    CheckCircle2,
    Clock3,
    RefreshCw,
    Server,
    ShieldAlert,
    XCircle,
} from "lucide-react";
import "./Observability.css";

function readCsrfToken() {
    const cookie = document.cookie
        .split("; ")
        .find((item) => item.startsWith("kc_csrf="));

    if (!cookie) return "";

    try {
        return decodeURIComponent(cookie.slice("kc_csrf=".length));
    } catch {
        return cookie.slice("kc_csrf=".length);
    }
}

function formatDate(value) {
    if (!value) return "—";
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? "—" : date.toLocaleString();
}

function formatDuration(value) {
    return value == null ? "N/A" : `${Number(value).toFixed(2)} ms`;
}

function MetricCard({ icon: Icon, label, value, description, variant }) {
    return (
        <article className="obs-metric-card">
            <div className={`obs-metric-icon ${variant || ""}`}>
                <Icon size={19} />
            </div>
            <span className="obs-metric-label">{label}</span>
            <strong className="obs-metric-value">{value}</strong>
            <span className="obs-metric-description">{description}</span>
        </article>
    );
}

export default function Observability({ apiBaseUrl = "" }) {
    const [summary, setSummary] = useState(null);
    const [events, setEvents] = useState([]);
    const [total, setTotal] = useState(0);
    const [severity, setSeverity] = useState("ALL");
    const [loading, setLoading] = useState(true);
    const [refreshing, setRefreshing] = useState(false);
    const [error, setError] = useState("");
    const [lastUpdated, setLastUpdated] = useState(null);

    const apiUrl = useCallback(
        (path) => `${apiBaseUrl.replace(/\/$/, "")}${path}`,
        [apiBaseUrl]
    );

    const request = useCallback(
        async (path) => {
            const headers = { Accept: "application/json" };
            const csrfToken = readCsrfToken();

            if (csrfToken) headers["X-CSRF-Token"] = csrfToken;

            let response;

            try {
                response = await fetch(apiUrl(path), {
                    method: "GET",
                    credentials: "include",
                    headers,
                });
            } catch {
                throw new Error("Cannot connect to the backend.");
            }

            if (response.status === 401) {
                throw new Error("Your session has expired. Sign in again.");
            }

            const data = await response.json().catch(() => ({}));

            if (!response.ok) {
                throw new Error(
                    typeof data.detail === "string"
                        ? data.detail
                        : `Request failed (HTTP ${response.status}).`
                );
            }

            return data;
        },
        [apiUrl]
    );

    const loadData = useCallback(
        async (isRefresh = false) => {
            setError("");

            if (isRefresh) setRefreshing(true);
            else setLoading(true);

            try {
                const eventPath =
                    "/api/v1/observability/events?limit=50&offset=0" +
                    (severity !== "ALL"
                        ? `&severity=${encodeURIComponent(severity)}`
                        : "");

                const [summaryData, eventData] = await Promise.all([
                    request("/api/v1/observability/summary"),
                    request(eventPath),
                ]);

                setSummary(summaryData);
                setEvents(Array.isArray(eventData.events) ? eventData.events : []);
                setTotal(Number(eventData.total || 0));
                setLastUpdated(new Date());
            } catch (err) {
                setError(err.message || "Unable to load observability data.");
            } finally {
                setLoading(false);
                setRefreshing(false);
            }
        },
        [request, severity]
    );

    useEffect(() => {
        loadData();
    }, [loadData]);

    const eventCounts = Array.isArray(summary?.event_counts)
        ? summary.event_counts
        : [];

    return (
        <main className="observability-page">
            <header className="obs-header">
                <div>
                    <div className="obs-eyebrow">SYSTEM HEALTH & PERFORMANCE</div>
                    <h1>Observability</h1>
                    <p>
                        Monitor recorded RAG requests, operational errors, and
                        response latency for your account.
                    </p>
                </div>

                <button
                    className="obs-refresh-button"
                    type="button"
                    onClick={() => loadData(true)}
                    disabled={loading || refreshing}
                >
                    <RefreshCw
                        size={16}
                        className={refreshing ? "obs-spinning" : ""}
                    />
                    {refreshing ? "Refreshing…" : "Refresh"}
                </button>
            </header>

            <div className="obs-window-row">
                <span className="obs-window-label">
                    <Activity size={15} />
                    Reporting window: last 24 hours
                </span>

                <span className="obs-updated">
                    Last updated: {lastUpdated ? lastUpdated.toLocaleTimeString() : "—"}
                </span>
            </div>

            {error && (
                <div className="obs-alert" role="alert">
                    <AlertTriangle size={18} />
                    <span>{error}</span>
                    <button type="button" onClick={() => loadData(true)}>
                        Retry
                    </button>
                </div>
            )}

            {loading && !summary ? (
                <div className="obs-loading">
                    <RefreshCw size={22} className="obs-spinning" />
                    <p>Loading observability metrics…</p>
                </div>
            ) : (
                <>
                    <section className="obs-metrics-grid">
                        <MetricCard
                            icon={Activity}
                            label="Recorded events"
                            value={summary?.total_events ?? "—"}
                            description="Events recorded in 24 hours"
                        />
                        <MetricCard
                            icon={XCircle}
                            label="Errors"
                            value={summary?.error_count ?? "—"}
                            description="Events with ERROR severity"
                            variant="danger"
                        />
                        <MetricCard
                            icon={AlertTriangle}
                            label="Warnings"
                            value={summary?.warning_count ?? "—"}
                            description="Events with WARNING severity"
                            variant="warning"
                        />
                        <MetricCard
                            icon={Server}
                            label="Server errors"
                            value={summary?.server_error_count ?? "—"}
                            description="Recorded responses with HTTP 5xx"
                            variant="danger"
                        />
                        <MetricCard
                            icon={Clock3}
                            label="Average latency"
                            value={formatDuration(summary?.average_latency_ms)}
                            description="Across recorded events with timing"
                        />
                        <MetricCard
                            icon={Activity}
                            label="P95 latency"
                            value={formatDuration(summary?.p95_latency_ms)}
                            description="95th percentile recorded latency"
                            variant="accent"
                        />
                    </section>

                    <section className="obs-panel">
                        <div className="obs-panel-header">
                            <div>
                                <h2>Event distribution</h2>
                                <p>Most frequent event types in the last 24 hours.</p>
                            </div>
                        </div>

                        {eventCounts.length === 0 ? (
                            <div className="obs-empty">
                                No observability events have been recorded yet.
                                Submit a question in AI Assistant to record a RAG event.
                            </div>
                        ) : (
                            <div className="obs-distribution">
                                {eventCounts.map((item) => {
                                    const maxCount = Math.max(
                                        ...eventCounts.map((entry) => Number(entry.count || 0)),
                                        1
                                    );
                                    const count = Number(item.count || 0);
                                    const width = (count / maxCount) * 100;

                                    return (
                                        <div
                                            className="obs-distribution-row"
                                            key={item.event_type}
                                        >
                                            <div className="obs-distribution-label">
                                                <span>{item.event_type}</span>
                                                <strong>{count}</strong>
                                            </div>
                                            <div className="obs-bar-track">
                                                <div
                                                    className="obs-bar-fill"
                                                    style={{ width: `${width}%` }}
                                                />
                                            </div>
                                        </div>
                                    );
                                })}
                            </div>
                        )}
                    </section>

                    <section className="obs-panel obs-events-panel">
                        <div className="obs-panel-header obs-events-header">
                            <div>
                                <h2>Recent operational events</h2>
                                <p>
                                    {total} matching events. Only events belonging to your
                                    authenticated account are shown.
                                </p>
                            </div>

                            <select
                                aria-label="Filter event severity"
                                value={severity}
                                onChange={(event) => setSeverity(event.target.value)}
                            >
                                <option value="ALL">All severities</option>
                                <option value="INFO">Info</option>
                                <option value="WARNING">Warning</option>
                                <option value="ERROR">Error</option>
                            </select>
                        </div>

                        {events.length === 0 ? (
                            <div className="obs-empty">
                                <ShieldAlert size={23} />
                                <strong>No matching events</strong>
                                <span>
                                    Events will appear here as instrumented operations run.
                                </span>
                            </div>
                        ) : (
                            <div className="obs-table-wrap">
                                <table className="obs-table">
                                    <thead>
                                        <tr>
                                            <th>Event</th>
                                            <th>Severity</th>
                                            <th>Duration</th>
                                            <th>Status</th>
                                            <th>Time</th>
                                            <th>Details</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {events.map((event) => (
                                            <tr key={event.id}>
                                                <td>
                                                    <span className="obs-event-name">
                                                        {event.event_type}
                                                    </span>
                                                    <span className="obs-event-id">
                                                        ID {event.id}
                                                    </span>
                                                </td>
                                                <td>
                                                    <span
                                                        className={`obs-severity obs-severity-${event.severity?.toLowerCase()}`}
                                                    >
                                                        {event.severity}
                                                    </span>
                                                </td>
                                                <td>{formatDuration(event.duration_ms)}</td>
                                                <td>
                                                    {event.status_code ?? "—"}
                                                </td>
                                                <td className="obs-time-cell">
                                                    {formatDate(event.created_at)}
                                                </td>
                                                <td>
                                                    <details className="obs-details">
                                                        <summary>View</summary>
                                                        <pre>
                                                            {JSON.stringify(event.details || {}, null, 2)}
                                                        </pre>
                                                    </details>
                                                </td>
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                            </div>
                        )}
                    </section>

                    <div className="obs-data-note">
                        <CheckCircle2 size={16} />
                        <span>
                            Metrics reflect events recorded by the current instrumentation.
                            They do not represent all server traffic or system-wide health.
                        </span>
                    </div>
                </>
            )}
        </main>
    );
}
