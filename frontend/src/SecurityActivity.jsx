
import {
    useCallback,
    useEffect,
    useMemo,
    useState,
} from "react";

import {
    Activity,
    AlertCircle,
    CheckCircle2,
    Clock3,
    RefreshCw,
    ShieldCheck,
    ShieldAlert,
    ChevronDown,
    FileText,
    LogIn,
    LockKeyhole,
    Search,
    Download,
    FilterX,
    ChevronLeft,
    ChevronRight,
} from "lucide-react";

import "./SecurityActivity.css";

const PAGE_SIZE = 10;

function formatDate(value) {
    if (!value) return "Unknown time";

    const date = new Date(value);

    if (Number.isNaN(date.getTime())) {
        return String(value);
    }

    return new Intl.DateTimeFormat(undefined, {
        year: "numeric",
        month: "short",
        day: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
    }).format(date);
}

function humanize(value) {
    return String(value || "unknown")
        .replaceAll("_", " ")
        .replace(/\s+/g, " ")
        .replace(/\b\w/g, (character) => character.toUpperCase());
}

function outcomeIsSuccess(outcome) {
    return String(outcome || "").toLowerCase() === "success";
}

function eventIcon(eventType) {
    const value = String(eventType || "").toLowerCase();

    if (value.includes("auth")) return LogIn;

    if (
        value.includes("restricted") ||
        value.includes("permission")
    ) {
        return ShieldAlert;
    }

    if (
        value.includes("document") ||
        value.includes("upload") ||
        value.includes("delete")
    ) {
        return FileText;
    }

    return Activity;
}

function csvEscape(value) {
    let text = "";

    if (value === null || value === undefined) {
        text = "";
    } else if (typeof value === "object") {
        text = JSON.stringify(value);
    } else {
        text = String(value);
    }

    // Protect against spreadsheet formula injection.
    if (/^[\s]*[=+\-@]/.test(text)) {
        text = `'${text}`;
    }

    return `"${text.replace(/"/g, '""')}"`;
}

function downloadCsv(events) {
    const columns = [
        ["Event ID", "id"],
        ["Timestamp", "created_at"],
        ["Event Type", "event_type"],
        ["Outcome", "outcome"],
        ["Account", "principal_id"],
        ["Details", "details"],
    ];

    const rows = [
        columns.map(([label]) => csvEscape(label)).join(","),
        ...events.map((event) =>
            columns
                .map(([, key]) => csvEscape(event[key]))
                .join(",")
        ),
    ];

    const csv = "\uFEFF" + rows.join("\r\n");
    const blob = new Blob([csv], {
        type: "text/csv;charset=utf-8;",
    });

    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");

    link.href = url;
    link.download = `security-activity-${new Date()
        .toISOString()
        .replace(/[:.]/g, "-")}.csv`;

    document.body.appendChild(link);
    link.click();
    link.remove();

    URL.revokeObjectURL(url);
}

export default function SecurityActivity({ apiBaseUrl }) {
    const [events, setEvents] = useState([]);
    const [total, setTotal] = useState(0);
    const [loading, setLoading] = useState(true);
    const [refreshing, setRefreshing] = useState(false);
    const [error, setError] = useState("");
    const [expandedId, setExpandedId] = useState(null);

    const [search, setSearch] = useState("");
    const [eventTypeFilter, setEventTypeFilter] = useState("all");
    const [outcomeFilter, setOutcomeFilter] = useState("all");
    const [page, setPage] = useState(1);

    const loadEvents = useCallback(
        async ({ quiet = false } = {}) => {
            if (quiet) {
                setRefreshing(true);
            } else {
                setLoading(true);
            }

            setError("");

            try {
                const response = await fetch(
                    `${apiBaseUrl}/api/v1/audit-events?limit=100&offset=0`,
                    {
                        method: "GET",
                        credentials: "include",
                        headers: {
                            Accept: "application/json",
                        },
                    }
                );

                if (!response.ok) {
                    let detail = "";

                    try {
                        const body = await response.json();

                        if (typeof body.detail === "string") {
                            detail = body.detail;
                        }
                    } catch {
                        // Use a generic message if the response isn't JSON.
                    }

                    if (response.status === 401) {
                        throw new Error(
                            "Your session has expired. Please sign in again."
                        );
                    }

                    if (response.status === 403) {
                        throw new Error(
                            "Your account is not allowed to view these events."
                        );
                    }

                    throw new Error(
                        detail ||
                        `The audit service returned HTTP ${response.status}.`
                    );
                }

                const data = await response.json();

                setEvents(
                    Array.isArray(data.events) ? data.events : []
                );

                setTotal(
                    Number.isFinite(data.total) ? data.total : 0
                );

                setPage(1);
                setExpandedId(null);
            } catch (loadError) {
                setError(
                    loadError instanceof Error
                        ? loadError.message
                        : "Unable to load security activity."
                );
            } finally {
                setLoading(false);
                setRefreshing(false);
            }
        },
        [apiBaseUrl]
    );

    useEffect(() => {
        loadEvents();
    }, [loadEvents]);

    const eventTypes = useMemo(() => {
        return [
            ...new Set(
                events.map((event) =>
                    String(event.event_type || "unknown")
                )
            ),
        ].sort((a, b) => a.localeCompare(b));
    }, [events]);

    const filteredEvents = useMemo(() => {
        const query = search.trim().toLowerCase();

        return events.filter((event) => {
            const searchableText = [
                event.id,
                event.event_type,
                event.outcome,
                event.principal_id,
                event.created_at,
                JSON.stringify(event.details || {}),
            ]
                .join(" ")
                .toLowerCase();

            const matchesSearch =
                !query || searchableText.includes(query);

            const matchesType =
                eventTypeFilter === "all" ||
                String(event.event_type || "unknown") === eventTypeFilter;

            const matchesOutcome =
                outcomeFilter === "all" ||
                (
                    outcomeFilter === "success" &&
                    outcomeIsSuccess(event.outcome)
                ) ||
                (
                    outcomeFilter === "failure" &&
                    !outcomeIsSuccess(event.outcome)
                );

            return matchesSearch && matchesType && matchesOutcome;
        });
    }, [events, search, eventTypeFilter, outcomeFilter]);

    const pageCount = Math.max(
        1,
        Math.ceil(filteredEvents.length / PAGE_SIZE)
    );

    const currentPage = Math.min(page, pageCount);

    const paginatedEvents = useMemo(() => {
        const start = (currentPage - 1) * PAGE_SIZE;
        return filteredEvents.slice(start, start + PAGE_SIZE);
    }, [filteredEvents, currentPage]);

    const stats = useMemo(() => {
        const successful = events.filter((event) =>
            outcomeIsSuccess(event.outcome)
        ).length;

        const failures = events.length - successful;

        const restricted = events.filter((event) =>
            String(event.event_type || "")
                .toLowerCase()
                .includes("restricted")
        ).length;

        return {
            successful,
            failures,
            restricted,
        };
    }, [events]);

    function resetFilters() {
        setSearch("");
        setEventTypeFilter("all");
        setOutcomeFilter("all");
        setPage(1);
    }

    function handleSearchChange(value) {
        setSearch(value);
        setPage(1);
    }

    function handleEventTypeChange(value) {
        setEventTypeFilter(value);
        setPage(1);
    }

    function handleOutcomeChange(value) {
        setOutcomeFilter(value);
        setPage(1);
    }

    return (
        <section className="security-workspace">
            <div className="security-page-heading">
                <div>
                    <span className="security-eyebrow">
                        SECURITY CENTER
                    </span>

                    <h1>Security &amp; Activity</h1>

                    <p>
                        Review recent security events recorded for your
                        authenticated account.
                    </p>
                </div>

                <button
                    className="security-refresh-button"
                    type="button"
                    onClick={() => loadEvents({ quiet: true })}
                    disabled={loading || refreshing}
                >
                    <RefreshCw
                        size={16}
                        className={refreshing ? "security-spin" : ""}
                    />

                    {refreshing ? "Refreshing…" : "Refresh"}
                </button>
            </div>

            <div className="security-notice">
                <ShieldCheck size={19} />

                <div>
                    <strong>Account-scoped activity</strong>

                    <p>
                        This view shows events associated with the account
                        currently authenticated to the API. It does not display
                        other employees' audit records.
                    </p>
                </div>
            </div>

            <div className="security-stat-grid">
                <article className="security-stat-card">
                    <div className="security-stat-icon">
                        <Activity size={19} />
                    </div>

                    <span className="security-stat-label">
                        Events loaded
                    </span>

                    <strong>{loading ? "—" : events.length}</strong>

                    <small>
                        {total} total event{total === 1 ? "" : "s"} recorded
                    </small>
                </article>

                <article className="security-stat-card">
                    <div className="security-stat-icon security-stat-success">
                        <CheckCircle2 size={19} />
                    </div>

                    <span className="security-stat-label">
                        Successful events
                    </span>

                    <strong>{loading ? "—" : stats.successful}</strong>

                    <small>Within the loaded results</small>
                </article>

                <article className="security-stat-card">
                    <div className="security-stat-icon security-stat-warning">
                        <ShieldAlert size={19} />
                    </div>

                    <span className="security-stat-label">
                        Non-success events
                    </span>

                    <strong>{loading ? "—" : stats.failures}</strong>

                    <small>Review details for context</small>
                </article>

                <article className="security-stat-card">
                    <div className="security-stat-icon">
                        <LockKeyhole size={19} />
                    </div>

                    <span className="security-stat-label">
                        Restricted matches
                    </span>

                    <strong>{loading ? "—" : stats.restricted}</strong>

                    <small>Within the loaded results</small>
                </article>
            </div>

            <div className="security-events-panel">
                <div className="security-panel-heading">
                    <div>
                        <h2>Recent activity</h2>
                        <p>Newest events appear first.</p>
                    </div>

                    <span className="security-live-label">
                        <span />
                        API connected when loaded
                    </span>
                </div>

                <div className="security-filters">
                    <label className="security-search">
                        <Search size={17} />

                        <input
                            type="search"
                            value={search}
                            onChange={(event) =>
                                handleSearchChange(event.target.value)
                            }
                            placeholder="Search events, account, or details..."
                            aria-label="Search security events"
                        />
                    </label>

                    <label className="security-filter-control">
                        <span>Event type</span>

                        <select
                            value={eventTypeFilter}
                            onChange={(event) =>
                                handleEventTypeChange(event.target.value)
                            }
                            aria-label="Filter by event type"
                        >
                            <option value="all">All event types</option>

                            {eventTypes.map((type) => (
                                <option key={type} value={type}>
                                    {humanize(type)}
                                </option>
                            ))}
                        </select>
                    </label>

                    <label className="security-filter-control">
                        <span>Outcome</span>

                        <select
                            value={outcomeFilter}
                            onChange={(event) =>
                                handleOutcomeChange(event.target.value)
                            }
                            aria-label="Filter by outcome"
                        >
                            <option value="all">All outcomes</option>
                            <option value="success">Success</option>
                            <option value="failure">Non-success</option>
                        </select>
                    </label>

                    <button
                        type="button"
                        className="security-tool-button"
                        onClick={resetFilters}
                        disabled={
                            !search &&
                            eventTypeFilter === "all" &&
                            outcomeFilter === "all"
                        }
                    >
                        <FilterX size={16} />
                        Clear
                    </button>

                    <button
                        type="button"
                        className="security-tool-button security-export-button"
                        onClick={() => downloadCsv(filteredEvents)}
                        disabled={filteredEvents.length === 0}
                        title="Export all currently filtered events"
                    >
                        <Download size={16} />
                        Export CSV
                    </button>
                </div>

                <div className="security-filter-summary">
                    Showing {filteredEvents.length} of {events.length} loaded events
                </div>

                {error && (
                    <div className="security-error" role="alert">
                        <AlertCircle size={18} />

                        <div>
                            <strong>Couldn't load activity</strong>

                            <p>{error}</p>

                            <button
                                type="button"
                                onClick={() => loadEvents()}
                                disabled={loading}
                            >
                                Try again
                            </button>
                        </div>
                    </div>
                )}

                {loading && !error ? (
                    <div className="security-state" role="status">
                        <span className="security-loader" />
                        <p>Loading audit events…</p>
                    </div>
                ) : !error && filteredEvents.length === 0 ? (
                    <div className="security-state">
                        <div className="security-empty-icon">
                            <Clock3 size={23} />
                        </div>

                        <h3>
                            {events.length === 0
                                ? "No activity yet"
                                : "No matching events"}
                        </h3>

                        <p>
                            {events.length === 0
                                ? "No audit events were returned for this account. Events will appear here when the backend records them."
                                : "Try changing your search or filters."}
                        </p>

                        {events.length > 0 && (
                            <button
                                type="button"
                                className="security-tool-button"
                                onClick={resetFilters}
                            >
                                <FilterX size={16} />
                                Clear filters
                            </button>
                        )}
                    </div>
                ) : (
                    !error && (
                        <>
                            <div className="security-event-list">
                                {paginatedEvents.map((event, index) => {
                                    const EventIcon = eventIcon(event.event_type);

                                    const eventId =
                                        event.id ??
                                        `${event.event_type}-${index}`;

                                    const expanded = expandedId === eventId;
                                    const success = outcomeIsSuccess(event.outcome);

                                    const details =
                                        event.details &&
                                            typeof event.details === "object" &&
                                            !Array.isArray(event.details)
                                            ? event.details
                                            : {};

                                    const detailSummary = Object.entries(details)
                                        .slice(0, 2)
                                        .map(([key, value]) => {
                                            const displayValue =
                                                typeof value === "string"
                                                    ? value
                                                    : JSON.stringify(value);

                                            return `${humanize(key)}: ${displayValue}`;
                                        })
                                        .join(" · ");

                                    return (
                                        <article
                                            className="security-event"
                                            key={eventId}
                                        >
                                            <div
                                                className={`security-event-icon ${success
                                                        ? "is-success"
                                                        : "is-warning"
                                                    }`}
                                            >
                                                <EventIcon size={18} />
                                            </div>

                                            <div className="security-event-main">
                                                <div className="security-event-title-row">
                                                    <h3>
                                                        {humanize(event.event_type)}
                                                    </h3>

                                                    <span
                                                        className={`security-outcome ${success
                                                                ? "is-success"
                                                                : "is-warning"
                                                            }`}
                                                    >
                                                        {humanize(event.outcome)}
                                                    </span>
                                                </div>

                                                <p className="security-event-summary">
                                                    {detailSummary ||
                                                        "No additional details recorded."}
                                                </p>

                                                <div className="security-event-meta">
                                                    <span>
                                                        {formatDate(event.created_at)}
                                                    </span>

                                                    {event.principal_id && (
                                                        <span>
                                                            Account: {event.principal_id}
                                                        </span>
                                                    )}

                                                    <span>
                                                        Event ID: {event.id ?? "—"}
                                                    </span>
                                                </div>

                                                <button
                                                    type="button"
                                                    className="security-details-toggle"
                                                    onClick={() =>
                                                        setExpandedId(
                                                            expanded ? null : eventId
                                                        )
                                                    }
                                                    aria-expanded={expanded}
                                                >
                                                    {expanded
                                                        ? "Hide details"
                                                        : "View details"}

                                                    <ChevronDown
                                                        size={14}
                                                        className={
                                                            expanded
                                                                ? "is-expanded"
                                                                : ""
                                                        }
                                                    />
                                                </button>

                                                {expanded && (
                                                    <pre className="security-event-details">
                                                        {JSON.stringify(details, null, 2)}
                                                    </pre>
                                                )}
                                            </div>
                                        </article>
                                    );
                                })}
                            </div>

                            <div className="security-pagination">
                                <span>
                                    Page {currentPage} of {pageCount}
                                </span>

                                <div>
                                    <button
                                        type="button"
                                        className="security-tool-button"
                                        onClick={() =>
                                            setPage((value) =>
                                                Math.max(1, value - 1)
                                            )
                                        }
                                        disabled={currentPage <= 1}
                                        aria-label="Previous page"
                                    >
                                        <ChevronLeft size={16} />
                                        Previous
                                    </button>

                                    <button
                                        type="button"
                                        className="security-tool-button"
                                        onClick={() =>
                                            setPage((value) =>
                                                Math.min(pageCount, value + 1)
                                            )
                                        }
                                        disabled={currentPage >= pageCount}
                                        aria-label="Next page"
                                    >
                                        Next
                                        <ChevronRight size={16} />
                                    </button>
                                </div>
                            </div>
                        </>
                    )
                )}
            </div>

            <p className="security-footnote">
                <ShieldCheck size={14} />
                Audit records are displayed as returned by the backend.
                This page does not modify or delete audit history.
            </p>
        </section>
    );
}
