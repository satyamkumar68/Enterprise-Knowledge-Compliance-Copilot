
import { useCallback, useEffect, useState } from "react";
import {
    Activity,
    ArrowRight,
    BrainCircuit,
    CheckCircle2,
    Clock3,
    FileText,
    Files,
    RefreshCw,
    ShieldCheck,
    Upload,
    AlertCircle,
} from "lucide-react";
import "./Workplace.css";

function formatDate(value) {
    if (!value) return "Date unavailable";

    const date = new Date(value);

    if (Number.isNaN(date.getTime())) return "Date unavailable";

    return date.toLocaleDateString(undefined, {
        day: "numeric",
        month: "short",
        year: "numeric",
    });
}

function Workplace({ apiBaseUrl, currentUser, onNavigate }) {
    const [documents, setDocuments] = useState([]);
    const [loading, setLoading] = useState(true);
    const [refreshing, setRefreshing] = useState(false);
    const [error, setError] = useState("");
    const [lastUpdated, setLastUpdated] = useState(null);

    const loadWorkspace = useCallback(async (manual = false) => {
        if (manual) {
            setError("");
            setRefreshing(true);
        }

        try {
            const response = await fetch(
                `${apiBaseUrl}/api/v1/documents`,
                {
                    method: "GET",
                    credentials: "include",
                    headers: {
                        Accept: "application/json",
                    },
                }
            );

            if (!response.ok) {
                if (response.status === 401) {
                    throw new Error(
                        "Your session has expired. Please sign in again."
                    );
                }

                if (response.status === 403) {
                    throw new Error(
                        "You do not have permission to view this workspace."
                    );
                }

                throw new Error(
                    `Unable to load workspace documents (HTTP ${response.status}).`
                );
            }

            const data = await response.json();
            const rows = Array.isArray(data.documents)
                ? data.documents
                : [];

            setDocuments(rows);
            setLastUpdated(new Date());
        } catch (err) {
            setError(
                err instanceof Error
                    ? err.message
                    : "An unexpected error occurred."
            );
        } finally {
            setLoading(false);
            setRefreshing(false);
        }
    }, [apiBaseUrl]);

    useEffect(() => {
        loadWorkspace();
    }, [loadWorkspace]);

    const indexedCount = documents.filter(
        (doc) => String(doc.status || "").toLowerCase() === "indexed"
    ).length;

    const pendingCount = documents.filter((doc) => {
        const status = String(doc.status || "").toLowerCase();
        return !["indexed", "failed", "error"].includes(status);
    }).length;

    const failedCount = documents.filter((doc) => {
        const status = String(doc.status || "").toLowerCase();
        return status === "failed" || status === "error";
    }).length;

    const recentDocuments = [...documents]
        .sort((a, b) => {
            const dateA = new Date(
                a.created_at || a.uploaded_at || 0
            ).getTime();

            const dateB = new Date(
                b.created_at || b.uploaded_at || 0
            ).getTime();

            return dateB - dateA;
        })
        .slice(0, 5);

    const displayName =
        currentUser?.principal_id || "Employee";

    return (
        <section className="workplace-page">
            <div className="workplace-heading">
                <div>
                    <span className="workplace-eyebrow">
                        YOUR WORKSPACE
                    </span>

                    <h1>Welcome back, {displayName}</h1>

                    <p>
                        Your starting point for company knowledge,
                        document discovery, and secure answers.
                    </p>
                </div>

                <button
                    type="button"
                    className="workplace-refresh"
                    onClick={() => loadWorkspace(true)}
                    disabled={loading || refreshing}
                >
                    <RefreshCw
                        size={16}
                        className={refreshing ? "workplace-spinning" : ""}
                    />
                    {refreshing ? "Refreshing..." : "Refresh"}
                </button>
            </div>

            <div className="workplace-banner">
                <div className="workplace-banner-icon">
                    <BrainCircuit size={27} />
                </div>

                <div className="workplace-banner-copy">
                    <span className="workplace-eyebrow">
                        KNOWLEDGE COPILOT
                    </span>

                    <h2>Find the information you need.</h2>

                    <p>
                        Ask questions and receive answers grounded in
                        documents your account is allowed to access.
                    </p>
                </div>

                <button
                    type="button"
                    className="workplace-banner-button"
                    onClick={() => onNavigate("AI Assistant")}
                >
                    Ask a question
                    <ArrowRight size={17} />
                </button>
            </div>

            {error && (
                <div className="workplace-error" role="alert">
                    <AlertCircle size={18} />
                    <span>{error}</span>

                    <button
                        type="button"
                        onClick={() => loadWorkspace(true)}
                    >
                        Retry
                    </button>
                </div>
            )}

            <div className="workplace-section-heading">
                <div>
                    <h2>Knowledge overview</h2>
                    <p>Your accessible document library at a glance.</p>
                </div>

                {lastUpdated && (
                    <span className="workplace-updated">
                        Updated {lastUpdated.toLocaleTimeString([], {
                            hour: "2-digit",
                            minute: "2-digit",
                        })}
                    </span>
                )}
            </div>

            <div className="workplace-stat-grid">
                <article className="workplace-stat-card">
                    <div className="workplace-stat-top">
                        <span>Total documents</span>
                        <div className="workplace-stat-icon blue">
                            <Files size={19} />
                        </div>
                    </div>

                    <strong>
                        {loading ? "—" : documents.length}
                    </strong>

                    <p>Documents available to your account</p>
                </article>

                <article className="workplace-stat-card">
                    <div className="workplace-stat-top">
                        <span>Indexed documents</span>
                        <div className="workplace-stat-icon green">
                            <CheckCircle2 size={19} />
                        </div>
                    </div>

                    <strong>{loading ? "—" : indexedCount}</strong>

                    <p>Marked as indexed by the backend</p>
                </article>

                <article className="workplace-stat-card">
                    <div className="workplace-stat-top">
                        <span>Processing</span>
                        <div className="workplace-stat-icon amber">
                            <Clock3 size={19} />
                        </div>
                    </div>

                    <strong>{loading ? "—" : pendingCount}</strong>

                    <p>Documents not yet marked indexed or failed</p>
                </article>

                <article className="workplace-stat-card">
                    <div className="workplace-stat-top">
                        <span>Failed documents</span>
                        <div className="workplace-stat-icon red">
                            <Activity size={19} />
                        </div>
                    </div>

                    <strong>{loading ? "—" : failedCount}</strong>

                    <p>Documents with a failed or error status</p>
                </article>
            </div>

            <div className="workplace-content-grid">
                <section className="workplace-panel">
                    <div className="workplace-panel-heading">
                        <div>
                            <h2>Recent documents</h2>
                            <p>Recently added accessible documents</p>
                        </div>

                        <button
                            type="button"
                            className="workplace-text-button"
                            onClick={() => onNavigate("Knowledge Base")}
                        >
                            View all
                            <ArrowRight size={15} />
                        </button>
                    </div>

                    {loading ? (
                        <div className="workplace-empty">
                            Loading your documents...
                        </div>
                    ) : recentDocuments.length === 0 ? (
                        <div className="workplace-empty">
                            <Files size={27} />

                            <strong>No documents available yet</strong>

                            <p>
                                Add an authorized document to start building
                                your knowledge base.
                            </p>

                            <button
                                type="button"
                                className="workplace-primary-button"
                                onClick={() => onNavigate("Knowledge Base")}
                            >
                                <Upload size={16} />
                                Open Knowledge Base
                            </button>
                        </div>
                    ) : (
                        <div className="workplace-document-list">
                            {recentDocuments.map((doc, index) => {
                                const status = String(
                                    doc.status || "unknown"
                                ).toLowerCase();

                                return (
                                    <div
                                        className="workplace-document-row"
                                        key={doc.document_id ?? `${doc.filename}-${index}`}
                                    >
                                        <div className="workplace-document-icon">
                                            <FileText size={19} />
                                        </div>

                                        <div className="workplace-document-info">
                                            <strong title={doc.filename || "Untitled document"}>
                                                {doc.filename || "Untitled document"}
                                            </strong>

                                            <span>
                                                {formatDate(
                                                    doc.created_at || doc.uploaded_at
                                                )}
                                            </span>
                                        </div>

                                        <span
                                            className={`workplace-status workplace-status-${status.replace(
                                                /[^a-z0-9_-]/g,
                                                ""
                                            )}`}
                                        >
                                            {status}
                                        </span>
                                    </div>
                                );
                            })}
                        </div>
                    )}
                </section>

                <section className="workplace-panel">
                    <div className="workplace-panel-heading">
                        <div>
                            <h2>Quick actions</h2>
                            <p>Jump straight into your work</p>
                        </div>
                    </div>

                    <div className="workplace-action-list">
                        <button
                            type="button"
                            className="workplace-action"
                            onClick={() => onNavigate("AI Assistant")}
                        >
                            <div className="workplace-action-icon blue">
                                <BrainCircuit size={20} />
                            </div>

                            <div>
                                <strong>Ask the AI Assistant</strong>
                                <span>Find answers in authorized documents</span>
                            </div>

                            <ArrowRight size={17} />
                        </button>

                        <button
                            type="button"
                            className="workplace-action"
                            onClick={() => onNavigate("Knowledge Base")}
                        >
                            <div className="workplace-action-icon purple">
                                <Upload size={20} />
                            </div>

                            <div>
                                <strong>Manage documents</strong>
                                <span>Upload, review, or remove documents</span>
                            </div>

                            <ArrowRight size={17} />
                        </button>

                        <button
                            type="button"
                            className="workplace-action"
                            onClick={() => onNavigate("Security & Activity")}
                        >
                            <div className="workplace-action-icon green">
                                <ShieldCheck size={20} />
                            </div>

                            <div>
                                <strong>Security &amp; Activity</strong>
                                <span>Review your available security activity</span>
                            </div>

                            <ArrowRight size={17} />
                        </button>
                    </div>

                    <div className="workplace-security-note">
                        <ShieldCheck size={17} />

                        <p>
                            <strong>Your access stays protected.</strong>
                            <span>
                                This dashboard uses your signed-in session and
                                the existing document-permission API.
                            </span>
                        </p>
                    </div>
                </section>
            </div>
        </section>
    );
}

export default Workplace;
