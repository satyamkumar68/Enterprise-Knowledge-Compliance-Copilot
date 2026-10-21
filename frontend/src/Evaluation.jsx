import { useCallback, useEffect, useState } from "react";
import {
    Activity,
    AlertCircle,
    BarChart3,
    Check,
    CheckCircle2,
    Clock,
    Copy,
    FileJson,
    FileSpreadsheet,
    Filter,
    GitCompare,
    Plus,
    RefreshCw,
    Search,
    Shield,
    Sparkles,
    Trash2,
    X,
    XCircle,
} from "lucide-react";
import "./Evaluation.css";

function readCsrfToken() {
    const cookie = document.cookie
        .split("; ")
        .find((item) => item.startsWith("kc_csrf="));

    if (!cookie) return "";

    const value = cookie.substring("kc_csrf=".length);

    try {
        return decodeURIComponent(value);
    } catch {
        return value;
    }
}

function formatDate(value) {
    if (!value) return "—";

    const date = new Date(value);

    return Number.isNaN(date.getTime())
        ? "—"
        : date.toLocaleString();
}

function formatPercent(value) {
    if (value === null || value === undefined) return "N/A";
    return `${(Number(value) * 100).toFixed(1)}%`;
}

function formatLatency(value) {
    if (value === null || value === undefined) return "N/A";
    return `${Number(value).toFixed(2)} ms`;
}

// ---------------------------------------------------------------------------
// 4.1 Donut / Circular Gauge Chart Card
// ---------------------------------------------------------------------------
function DonutGaugeCard({
    label,
    value,
    percent,
    description,
    color = "accent",
    icon: Icon,
}) {
    const validPercent =
        typeof percent === "number" && !Number.isNaN(percent)
            ? Math.max(0, Math.min(1, percent))
            : null;

    const radius = 24;
    const circumference = 2 * Math.PI * radius;
    const strokeDashoffset =
        validPercent !== null
            ? circumference * (1 - validPercent)
            : circumference;

    return (
        <article className={`eval-metric-card eval-gauge-card color-${color}`}>
            <div className="eval-gauge-header">
                <span className="eval-metric-label">{label}</span>
                {Icon && <Icon size={16} className="eval-metric-icon" />}
            </div>

            <div className="eval-gauge-body">
                <div className="eval-donut-container" aria-hidden="true">
                    <svg
                        className="eval-donut-svg"
                        width="64"
                        height="64"
                        viewBox="0 0 64 64"
                    >
                        <circle
                            className="eval-donut-bg"
                            cx="32"
                            cy="32"
                            r={radius}
                            fill="transparent"
                            strokeWidth="5"
                        />
                        <circle
                            className={`eval-donut-progress color-${color}`}
                            cx="32"
                            cy="32"
                            r={radius}
                            fill="transparent"
                            strokeWidth="5"
                            strokeDasharray={circumference}
                            strokeDashoffset={strokeDashoffset}
                            strokeLinecap="round"
                            transform="rotate(-90 32 32)"
                        />
                    </svg>
                    <div className="eval-donut-center">
                        {validPercent !== null
                            ? `${Math.round(validPercent * 100)}%`
                            : "—"}
                    </div>
                </div>

                <div className="eval-gauge-content">
                    <strong className="eval-metric-value">{value}</strong>
                    <span className="eval-metric-description">{description}</span>
                </div>
            </div>
        </article>
    );
}

// ---------------------------------------------------------------------------
// 4.2 Latency Distribution & Sparkline/Bar Chart
// ---------------------------------------------------------------------------
function LatencyDistributionChart({ results, onSelectCase }) {
    if (!results || results.length === 0) return null;

    const validLatencies = results
        .map((r) => r.latency_ms || 0)
        .filter((l) => l > 0);

    if (validLatencies.length === 0) return null;

    const minLat = Math.min(...validLatencies);
    const maxLat = Math.max(...validLatencies);
    const avgLat =
        validLatencies.reduce((a, b) => a + b, 0) / validLatencies.length;

    const sorted = [...validLatencies].sort((a, b) => a - b);
    const p95Index = Math.min(
        sorted.length - 1,
        Math.floor(sorted.length * 0.95)
    );
    const p95Lat = sorted[p95Index];

    return (
        <div className="eval-latency-distribution">
            <div className="eval-chart-header">
                <div>
                    <h3 className="eval-chart-title">
                        <BarChart3 size={17} />
                        <span>Latency Distribution</span>
                    </h3>
                    <p className="eval-chart-subtitle">
                        Per-case response latency across this evaluation run
                    </p>
                </div>

                <div className="eval-latency-stats-strip">
                    <div className="latency-stat">
                        <span>Min</span>
                        <strong>{minLat.toFixed(0)} ms</strong>
                    </div>
                    <div className="latency-stat">
                        <span>Avg</span>
                        <strong>{avgLat.toFixed(0)} ms</strong>
                    </div>
                    <div className="latency-stat">
                        <span>p95</span>
                        <strong>{p95Lat.toFixed(0)} ms</strong>
                    </div>
                    <div className="latency-stat">
                        <span>Max</span>
                        <strong>{maxLat.toFixed(0)} ms</strong>
                    </div>
                </div>
            </div>

            <div className="eval-latency-bars-scroll">
                <div className="eval-latency-bars">
                    {results.map((r, i) => {
                        const lat = r.latency_ms || 0;
                        const heightPct =
                            maxLat > 0
                                ? Math.max(10, (lat / maxLat) * 100)
                                : 10;

                        const statusClass =
                            r.status === "error"
                                ? "bar-error"
                                : r.abstained
                                  ? "bar-abstained"
                                  : lat < 2000
                                    ? "bar-fast"
                                    : lat < 5000
                                      ? "bar-medium"
                                      : "bar-slow";

                        return (
                            <button
                                key={`bar-${r.case_id || i}`}
                                type="button"
                                className={`latency-bar-btn ${statusClass}`}
                                style={{ height: `${heightPct}%` }}
                                onClick={() =>
                                    onSelectCase && onSelectCase(r.case_id)
                                }
                                aria-label={`Case #${r.case_id}: ${lat.toFixed(0)} ms`}
                            >
                                <span className="latency-bar-tooltip">
                                    <strong>Case #{r.case_id}</strong>:{" "}
                                    {lat.toFixed(0)} ms
                                    <small>
                                        {r.status === "error"
                                            ? "Error"
                                            : r.abstained
                                              ? "Abstained"
                                              : "Answered"}
                                    </small>
                                </span>
                            </button>
                        );
                    })}
                </div>

                <div className="eval-latency-x-axis">
                    <span>Case #1</span>
                    <span>Cases ({results.length})</span>
                    <span>
                        Case #{results[results.length - 1]?.case_id || results.length}
                    </span>
                </div>
            </div>
        </div>
    );
}

// ---------------------------------------------------------------------------
// 4.6 Retrieval Overlap Visualization
// ---------------------------------------------------------------------------
function RetrievalOverlapVisualizer({ expectedIds = [], retrievedIds = [] }) {
    const expSet = new Set(expectedIds);
    const retSet = new Set(retrievedIds);

    const matches = expectedIds.filter((id) => retSet.has(id));
    const misses = expectedIds.filter((id) => !retSet.has(id));
    const extras = retrievedIds.filter((id) => !expSet.has(id));

    if (expectedIds.length === 0 && retrievedIds.length === 0) {
        return (
            <div className="overlap-pill-group empty">
                <span className="overlap-note">
                    No expected or retrieved document IDs configured.
                </span>
            </div>
        );
    }

    if (expectedIds.length === 0) {
        return (
            <div className="overlap-container">
                <div className="overlap-legend">
                    <span className="overlap-label">
                        Retrieved documents (no expected IDs configured):
                    </span>
                </div>
                <div className="overlap-pill-group">
                    {retrievedIds.map((id) => (
                        <span key={`ret-${id}`} className="overlap-pill pill-neutral">
                            Doc #{id}
                        </span>
                    ))}
                </div>
            </div>
        );
    }

    return (
        <div className="overlap-container">
            <div className="overlap-summary-bar">
                <span className="overlap-stat match-stat">
                    <CheckCircle2 size={13} /> {matches.length} Matched
                </span>
                {misses.length > 0 && (
                    <span className="overlap-stat miss-stat">
                        <XCircle size={13} /> {misses.length} Missed
                    </span>
                )}
                {extras.length > 0 && (
                    <span className="overlap-stat extra-stat">
                        <Plus size={13} /> {extras.length} Additional
                    </span>
                )}
            </div>

            <div className="overlap-pill-group">
                {matches.map((id) => (
                    <span
                        key={`match-${id}`}
                        className="overlap-pill pill-match"
                        title="Expected and successfully retrieved"
                    >
                        <Check size={12} /> Doc #{id} (Match)
                    </span>
                ))}
                {misses.map((id) => (
                    <span
                        key={`miss-${id}`}
                        className="overlap-pill pill-miss"
                        title="Expected in ground truth but not retrieved"
                    >
                        <X size={12} /> Doc #{id} (Missed)
                    </span>
                ))}
                {extras.map((id) => (
                    <span
                        key={`extra-${id}`}
                        className="overlap-pill pill-extra"
                        title="Retrieved from knowledge base but not listed in expected IDs"
                    >
                        Doc #{id} (Extra)
                    </span>
                ))}
            </div>
        </div>
    );
}

// ---------------------------------------------------------------------------
// 4.8 Answer Diff View (Side-by-side & Keyword Comparison)
// ---------------------------------------------------------------------------
function AnswerDiffView({ generatedAnswer, expectedAnswer }) {
    const [viewMode, setViewMode] = useState("split");
    const [copied, setCopied] = useState(false);

    if (!expectedAnswer) {
        return (
            <div className="answer-view-single">
                <div className="answer-block generated">
                    <h4>Generated answer</h4>
                    <p className="eval-answer-text">
                        {generatedAnswer || "No answer generated."}
                    </p>
                </div>
            </div>
        );
    }

    function copyAnswer() {
        if (navigator.clipboard) {
            navigator.clipboard.writeText(generatedAnswer || "");
            setCopied(true);
            setTimeout(() => setCopied(false), 2000);
        }
    }

    const genWords = (generatedAnswer || "")
        .toLowerCase()
        .replace(/[^\w\s]/g, "")
        .split(/\s+/)
        .filter(Boolean);

    const expWords = (expectedAnswer || "")
        .toLowerCase()
        .replace(/[^\w\s]/g, "")
        .split(/\s+/)
        .filter(Boolean);

    const expWordSet = new Set(expWords);
    const genWordSet = new Set(genWords);

    const commonWords = genWords.filter((w) => expWordSet.has(w));
    const termOverlap =
        expWords.length > 0
            ? Math.round(
                  (new Set(commonWords).size / new Set(expWords).size) * 100
              )
            : 0;

    return (
        <div className="answer-diff-container">
            <div className="diff-header-bar">
                <div className="diff-badges">
                    <span
                        className="overlap-score-badge"
                        title="Key vocabulary overlap between generated and reference answers"
                    >
                        <Sparkles size={13} /> {termOverlap}% Term Overlap
                    </span>
                </div>

                <div className="diff-actions">
                    <div className="diff-toggle-group">
                        <button
                            type="button"
                            className={`diff-toggle-btn ${
                                viewMode === "split" ? "active" : ""
                            }`}
                            onClick={() => setViewMode("split")}
                        >
                            Side-by-side
                        </button>
                        <button
                            type="button"
                            className={`diff-toggle-btn ${
                                viewMode === "diff" ? "active" : ""
                            }`}
                            onClick={() => setViewMode("diff")}
                        >
                            Highlighted diff
                        </button>
                    </div>

                    <button
                        type="button"
                        className="eval-copy-btn"
                        onClick={copyAnswer}
                        title="Copy generated answer"
                    >
                        {copied ? <Check size={13} /> : <Copy size={13} />}
                        <span>{copied ? "Copied" : "Copy"}</span>
                    </button>
                </div>
            </div>

            {viewMode === "split" ? (
                <div className="diff-split-grid">
                    <div className="diff-column generated-col">
                        <div className="column-title">
                            <span className="col-indicator green" /> Generated answer
                        </div>
                        <p className="eval-answer-text">
                            {generatedAnswer || "No answer returned."}
                        </p>
                    </div>
                    <div className="diff-column expected-col">
                        <div className="column-title">
                            <span className="col-indicator blue" /> Reference answer
                        </div>
                        <p className="eval-answer-text">{expectedAnswer}</p>
                    </div>
                </div>
            ) : (
                <div className="diff-highlight-view">
                    <div className="highlight-section">
                        <div className="column-title">
                            Generated answer (matching key terms highlighted)
                        </div>
                        <p className="eval-answer-text diff-words">
                            {(generatedAnswer || "")
                                .split(/(\s+)/)
                                .map((segment, idx) => {
                                    const clean = segment
                                        .toLowerCase()
                                        .replace(/[^\w]/g, "");
                                    const isMatch =
                                        clean && expWordSet.has(clean);
                                    return isMatch ? (
                                        <mark
                                            key={`g-${idx}`}
                                            className="word-match"
                                        >
                                            {segment}
                                        </mark>
                                    ) : (
                                        <span key={`g-${idx}`}>{segment}</span>
                                    );
                                })}
                        </p>
                    </div>

                    <div className="highlight-section">
                        <div className="column-title">
                            Reference answer (missing key terms highlighted)
                        </div>
                        <p className="eval-answer-text diff-words">
                            {(expectedAnswer || "")
                                .split(/(\s+)/)
                                .map((segment, idx) => {
                                    const clean = segment
                                        .toLowerCase()
                                        .replace(/[^\w]/g, "");
                                    const isMissing =
                                        clean && !genWordSet.has(clean);
                                    return isMissing ? (
                                        <mark
                                            key={`e-${idx}`}
                                            className="word-missing"
                                        >
                                            {segment}
                                        </mark>
                                    ) : (
                                        <span key={`e-${idx}`}>{segment}</span>
                                    );
                                })}
                        </p>
                    </div>
                </div>
            )}
        </div>
    );
}

// ---------------------------------------------------------------------------
// 4.3 Run Comparison View
// ---------------------------------------------------------------------------
function RunComparisonView({
    currentRun,
    comparisonRun,
    runs = [],
    onSelectComparisonRun,
    onClose,
}) {
    if (!currentRun) return null;

    const curMetrics = currentRun.metrics || {};
    const compMetrics = comparisonRun?.metrics || {};

    function calcDelta(cur, comp, isPercent = true, lowerIsBetter = false) {
        if (
            cur === null ||
            cur === undefined ||
            comp === null ||
            comp === undefined
        )
            return null;

        const diff = isPercent ? (cur - comp) * 100 : cur - comp;
        const formatted = `${diff >= 0 ? "+" : ""}${diff.toFixed(1)}${
            isPercent ? "%" : ""
        }`;
        const isPositive = diff > 0.001;
        const isNegative = diff < -0.001;

        let quality = "neutral";
        if (isPositive) quality = lowerIsBetter ? "worse" : "better";
        if (isNegative) quality = lowerIsBetter ? "better" : "worse";

        return { diff, formatted, quality };
    }

    const answerRateDelta = calcDelta(
        curMetrics.answer_rate,
        compMetrics.answer_rate,
        true,
        false
    );
    const hitRateDelta = calcDelta(
        curMetrics.retrieval_hit_rate,
        compMetrics.retrieval_hit_rate,
        true,
        false
    );
    const latencyDelta = calcDelta(
        curMetrics.average_latency_ms,
        compMetrics.average_latency_ms,
        false,
        true
    );
    const abstentionDelta = calcDelta(
        curMetrics.abstention_rate,
        compMetrics.abstention_rate,
        true,
        true
    );

    return (
        <section className="eval-comparison-panel">
            <div className="comparison-header">
                <div className="comparison-title-wrap">
                    <GitCompare size={19} className="comparison-icon" />
                    <div>
                        <h2>Run Comparison</h2>
                        <p>
                            Compare current Run #{currentRun.run_id} against another
                            evaluation run
                        </p>
                    </div>
                </div>

                <div className="comparison-actions">
                    <label htmlFor="compare-select" className="compare-label">
                        Baseline:
                    </label>
                    <select
                        id="compare-select"
                        className="eval-select"
                        value={comparisonRun?.run_id || ""}
                        onChange={(e) =>
                            onSelectComparisonRun(Number(e.target.value))
                        }
                    >
                        <option value="">Choose baseline run...</option>
                        {runs
                            .filter((r) => r.run_id !== currentRun.run_id)
                            .map((r) => (
                                <option key={r.run_id} value={r.run_id}>
                                    Run #{r.run_id} ({formatDate(r.created_at)})
                                </option>
                            ))}
                    </select>

                    <button
                        type="button"
                        className="eval-secondary-button"
                        onClick={onClose}
                    >
                        Close comparison
                    </button>
                </div>
            </div>

            {comparisonRun ? (
                <div className="comparison-content">
                    <div className="comparison-metrics-grid">
                        <div className="comparison-metric-card">
                            <span className="comp-label">Answer Rate</span>
                            <div className="comp-values">
                                <span className="comp-val-base">
                                    Base #{comparisonRun.run_id}:{" "}
                                    {formatPercent(compMetrics.answer_rate)}
                                </span>
                                <span className="comp-arrow">→</span>
                                <span className="comp-val-cur">
                                    Run #{currentRun.run_id}:{" "}
                                    {formatPercent(curMetrics.answer_rate)}
                                </span>
                            </div>
                            {answerRateDelta && (
                                <span
                                    className={`comp-delta delta-${answerRateDelta.quality}`}
                                >
                                    {answerRateDelta.formatted}
                                </span>
                            )}
                        </div>

                        <div className="comparison-metric-card">
                            <span className="comp-label">Retrieval Hit Rate</span>
                            <div className="comp-values">
                                <span className="comp-val-base">
                                    Base #{comparisonRun.run_id}:{" "}
                                    {formatPercent(compMetrics.retrieval_hit_rate)}
                                </span>
                                <span className="comp-arrow">→</span>
                                <span className="comp-val-cur">
                                    Run #{currentRun.run_id}:{" "}
                                    {formatPercent(curMetrics.retrieval_hit_rate)}
                                </span>
                            </div>
                            {hitRateDelta && (
                                <span
                                    className={`comp-delta delta-${hitRateDelta.quality}`}
                                >
                                    {hitRateDelta.formatted}
                                </span>
                            )}
                        </div>

                        <div className="comparison-metric-card">
                            <span className="comp-label">Average Latency</span>
                            <div className="comp-values">
                                <span className="comp-val-base">
                                    {formatLatency(compMetrics.average_latency_ms)}
                                </span>
                                <span className="comp-arrow">→</span>
                                <span className="comp-val-cur">
                                    {formatLatency(curMetrics.average_latency_ms)}
                                </span>
                            </div>
                            {latencyDelta && (
                                <span
                                    className={`comp-delta delta-${latencyDelta.quality}`}
                                >
                                    {latencyDelta.formatted} ms
                                </span>
                            )}
                        </div>

                        <div className="comparison-metric-card">
                            <span className="comp-label">Abstention Rate</span>
                            <div className="comp-values">
                                <span className="comp-val-base">
                                    {formatPercent(compMetrics.abstention_rate)}
                                </span>
                                <span className="comp-arrow">→</span>
                                <span className="comp-val-cur">
                                    {formatPercent(curMetrics.abstention_rate)}
                                </span>
                            </div>
                            {abstentionDelta && (
                                <span
                                    className={`comp-delta delta-${abstentionDelta.quality}`}
                                >
                                    {abstentionDelta.formatted}
                                </span>
                            )}
                        </div>
                    </div>
                </div>
            ) : (
                <div className="comparison-empty">
                    <p>
                        Select a baseline run from the dropdown above to view
                        side-by-side delta metrics.
                    </p>
                </div>
            )}
        </section>
    );
}

// ---------------------------------------------------------------------------
// 4.7 Export Handlers (CSV & JSON)
// ---------------------------------------------------------------------------
function exportRunToCSV(run) {
    if (!run) return;
    const results = run.results || [];
    const headers = [
        "Case ID",
        "Question",
        "Status",
        "Answer",
        "Expected Answer",
        "Retrieval Hit",
        "Latency (ms)",
        "Expected Document IDs",
        "Retrieved Document IDs",
        "Source Count",
        "Confidence Score",
    ];

    const escapeCsv = (val) => {
        if (val === null || val === undefined) return '""';
        const str = String(val).replace(/"/g, '""');
        return `"${str}"`;
    };

    const rows = results.map((r) => [
        escapeCsv(r.case_id),
        escapeCsv(r.question),
        escapeCsv(
            r.status === "error"
                ? "error"
                : r.abstained
                  ? "abstained"
                  : "answered"
        ),
        escapeCsv(r.clean_answer || r.answer || ""),
        escapeCsv(r.expected_answer || ""),
        escapeCsv(
            r.retrieval_hit === null
                ? "N/A"
                : r.retrieval_hit
                  ? "Hit"
                  : "Miss"
        ),
        escapeCsv(r.latency_ms),
        escapeCsv((r.expected_document_ids || []).join("; ")),
        escapeCsv((r.retrieved_document_ids || []).join("; ")),
        escapeCsv(r.source_count ?? 0),
        escapeCsv(
            r.confidence_score !== null && r.confidence_score !== undefined
                ? `${(r.confidence_score * 100).toFixed(1)}%`
                : "N/A"
        ),
    ]);

    const csvContent = [headers.join(","), ...rows.map((r) => r.join(","))].join(
        "\r\n"
    );
    const blob = new Blob([csvContent], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.setAttribute("download", `rag_evaluation_run_${run.run_id}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
}

function exportRunToJSON(run) {
    if (!run) return;
    const jsonStr = JSON.stringify(run, null, 2);
    const blob = new Blob([jsonStr], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.setAttribute("download", `rag_evaluation_run_${run.run_id}.json`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
}

// ---------------------------------------------------------------------------
// Main Evaluation Component
// ---------------------------------------------------------------------------
export default function Evaluation({ apiBaseUrl = "" }) {
    const [cases, setCases] = useState([]);
    const [runs, setRuns] = useState([]);
    const [selectedRun, setSelectedRun] = useState(null);
    const [comparisonRun, setComparisonRun] = useState(null);
    const [showComparison, setShowComparison] = useState(false);

    const [question, setQuestion] = useState("");
    const [expectedAnswer, setExpectedAnswer] = useState("");
    const [expectedDocumentIds, setExpectedDocumentIds] = useState("");

    const [loadingCases, setLoadingCases] = useState(true);
    const [loadingRuns, setLoadingRuns] = useState(true);
    const [savingCase, setSavingCase] = useState(false);
    const [runningEvaluation, setRunningEvaluation] = useState(false);
    const [evalProgressSeconds, setEvalProgressSeconds] = useState(0);
    const [openingRunId, setOpeningRunId] = useState(null);
    const [deletingCaseId, setDeletingCaseId] = useState(null);

    const [filterStatus, setFilterStatus] = useState("all");
    const [searchQuery, setSearchQuery] = useState("");

    const [error, setError] = useState("");
    const [notice, setNotice] = useState("");

    const apiUrl = useCallback(
        (path) => `${apiBaseUrl.replace(/\/$/, "")}${path}`,
        [apiBaseUrl]
    );

    const request = useCallback(
        async (path, options = {}) => {
            const method = (options.method || "GET").toUpperCase();
            const headers = new Headers(options.headers || {});

            if (options.body && !headers.has("Content-Type")) {
                headers.set("Content-Type", "application/json");
            }

            if (!["GET", "HEAD", "OPTIONS"].includes(method)) {
                const csrfToken = readCsrfToken();
                if (csrfToken) {
                    headers.set("X-CSRF-Token", csrfToken);
                }
            }

            const response = await fetch(apiUrl(path), {
                ...options,
                method,
                headers,
                credentials: "include",
            });

            if (response.status === 401) {
                throw new Error(
                    "Your session has expired. Sign in again and reopen Evaluation."
                );
            }

            const contentType = response.headers.get("content-type") || "";
            let data = null;

            if (contentType.includes("application/json")) {
                data = await response.json();
            } else {
                const text = await response.text();
                data = text ? { detail: text } : null;
            }

            if (!response.ok) {
                const detail =
                    typeof data?.detail === "string"
                        ? data.detail
                        : `Request failed (${response.status}).`;

                throw new Error(detail);
            }

            return data;
        },
        [apiUrl]
    );

    const loadCases = useCallback(async () => {
        setLoadingCases(true);
        try {
            const data = await request("/api/v1/evaluation/cases");
            setCases(Array.isArray(data?.cases) ? data.cases : []);
        } catch (err) {
            setError(err.message || "Unable to load evaluation cases.");
        } finally {
            setLoadingCases(false);
        }
    }, [request]);

    const loadRuns = useCallback(async () => {
        setLoadingRuns(true);
        try {
            const data = await request("/api/v1/evaluation/runs?limit=30");
            setRuns(Array.isArray(data?.runs) ? data.runs : []);
        } catch (err) {
            setError(err.message || "Unable to load evaluation history.");
        } finally {
            setLoadingRuns(false);
        }
    }, [request]);

    useEffect(() => {
        loadCases();
        loadRuns();
    }, [loadCases, loadRuns]);

    // Timer effect for 4.5 Progress Indicator
    useEffect(() => {
        if (!runningEvaluation) {
            return;
        }

        const interval = setInterval(() => {
            setEvalProgressSeconds((s) => s + 1);
        }, 1000);

        return () => {
            clearInterval(interval);
        };
    }, [runningEvaluation]);

    async function handleCreateCase(event) {
        event.preventDefault();
        setError("");
        setNotice("");

        const cleanedQuestion = question.trim();

        if (!cleanedQuestion) {
            setError("Enter an evaluation question.");
            return;
        }

        const idParts = expectedDocumentIds.trim()
            ? expectedDocumentIds.split(",").map((part) => part.trim())
            : [];

        if (idParts.some((part) => !/^[1-9]\d*$/.test(part))) {
            setError(
                "Expected document IDs must be positive integers separated by commas."
            );
            return;
        }

        const documentIds = [...new Set(idParts.map(Number))];
        setSavingCase(true);

        try {
            await request("/api/v1/evaluation/cases", {
                method: "POST",
                body: JSON.stringify({
                    question: cleanedQuestion,
                    expected_answer: expectedAnswer.trim(),
                    expected_document_ids: documentIds,
                }),
            });

            setQuestion("");
            setExpectedAnswer("");
            setExpectedDocumentIds("");
            setNotice("Evaluation case added.");
            await loadCases();
        } catch (err) {
            setError(err.message || "Unable to save the evaluation case.");
        } finally {
            setSavingCase(false);
        }
    }

    async function handleDeleteCase(caseId) {
        const confirmed = window.confirm(
            "Delete this evaluation case? This cannot be undone."
        );

        if (!confirmed) return;

        setError("");
        setNotice("");
        setDeletingCaseId(caseId);

        try {
            await request(`/api/v1/evaluation/cases/${caseId}`, {
                method: "DELETE",
            });

            setNotice("Evaluation case deleted.");
            await loadCases();
        } catch (err) {
            setError(err.message || "Unable to delete the evaluation case.");
        } finally {
            setDeletingCaseId(null);
        }
    }

    async function handleRunEvaluation() {
        setError("");
        setNotice("");
        setRunningEvaluation(true);
        setEvalProgressSeconds(0);
        setSelectedRun(null);

        try {
            const result = await request("/api/v1/evaluation/runs", {
                method: "POST",
                body: JSON.stringify({}),
            });

            setSelectedRun(result);
            setNotice(`Evaluation run #${result.run_id} completed successfully.`);
            await loadRuns();
        } catch (err) {
            setError(err.message || "Unable to run the evaluation.");
        } finally {
            setRunningEvaluation(false);
        }
    }

    async function handleOpenRun(runId) {
        setError("");
        setNotice("");
        setOpeningRunId(runId);

        try {
            const result = await request(`/api/v1/evaluation/runs/${runId}`);
            setSelectedRun(result);
        } catch (err) {
            setError(err.message || "Unable to load this evaluation run.");
        } finally {
            setOpeningRunId(null);
        }
    }

    async function handleSelectComparison(runId) {
        if (!runId) {
            setComparisonRun(null);
            return;
        }
        try {
            const result = await request(`/api/v1/evaluation/runs/${runId}`);
            setComparisonRun(result);
        } catch (err) {
            setError(err.message || "Unable to load comparison run.");
        }
    }

    function scrollToCase(caseId) {
        const element = document.getElementById(`case-card-${caseId}`);
        if (element) {
            element.scrollIntoView({ behavior: "smooth", block: "center" });
            element.open = true;
        }
    }

    const metrics = selectedRun?.metrics;
    const allResults = Array.isArray(selectedRun?.results)
        ? selectedRun.results
        : [];

    // Filter and search results
    const filteredResults = allResults.filter((r) => {
        if (filterStatus === "answered" && (r.status !== "completed" || r.abstained))
            return false;
        if (filterStatus === "abstained" && !r.abstained) return false;
        if (filterStatus === "hit" && !r.retrieval_hit) return false;
        if (filterStatus === "miss" && (r.retrieval_hit !== false || r.status === "error"))
            return false;
        if (filterStatus === "error" && r.status !== "error") return false;

        if (searchQuery.trim()) {
            const q = searchQuery.toLowerCase();
            const textMatch =
                (r.question || "").toLowerCase().includes(q) ||
                (r.answer || "").toLowerCase().includes(q) ||
                (r.expected_answer || "").toLowerCase().includes(q) ||
                String(r.case_id).includes(q);
            if (!textMatch) return false;
        }

        return true;
    });

    const answeredCount = allResults.filter(
        (r) => r.status === "completed" && !r.abstained
    ).length;
    const abstainedCount = allResults.filter((r) => r.abstained).length;
    const hitCount = allResults.filter((r) => r.retrieval_hit === true).length;
    const missCount = allResults.filter((r) => r.retrieval_hit === false).length;
    const errorCount = allResults.filter((r) => r.status === "error").length;

    return (
        <main className="evaluation-page">
            <header className="eval-page-header">
                <div>
                    <div className="eval-eyebrow">QUALITY & RELIABILITY</div>
                    <h1>RAG Evaluation</h1>
                    <p>
                        Measure retrieval precision, answer grounding, and latency
                        across your authorized documents with live evaluation runs.
                    </p>
                </div>

                <div className="eval-header-actions">
                    {runs.length > 1 && selectedRun && (
                        <button
                            className="eval-secondary-button"
                            type="button"
                            onClick={() => setShowComparison((v) => !v)}
                        >
                            <GitCompare size={15} />
                            <span>
                                {showComparison
                                    ? "Hide comparison"
                                    : "Compare runs"}
                            </span>
                        </button>
                    )}

                    <button
                        className="eval-primary-button"
                        type="button"
                        onClick={handleRunEvaluation}
                        disabled={runningEvaluation || cases.length === 0}
                    >
                        {runningEvaluation ? (
                            <>
                                <RefreshCw
                                    size={15}
                                    className="eval-spinner-icon"
                                />
                                <span>Running evaluation…</span>
                            </>
                        ) : (
                            <>
                                <Activity size={15} />
                                <span>Run evaluation</span>
                            </>
                        )}
                    </button>
                </div>
            </header>

            {/* 4.5 Progress Indicator during Evaluation */}
            {runningEvaluation && (
                <div
                    className="eval-progress-banner"
                    role="status"
                    aria-live="polite"
                >
                    <div className="eval-progress-info">
                        <div className="eval-progress-title">
                            <Sparkles size={16} className="eval-pulse-icon" />
                            <strong>
                                Evaluating {cases.length} test cases with live RAG
                                pipeline…
                            </strong>
                        </div>
                        <span className="eval-progress-timer">
                            <Clock size={14} /> {evalProgressSeconds}s elapsed
                        </span>
                    </div>
                    <div className="eval-progress-bar-track">
                        <div className="eval-progress-bar-fill" />
                    </div>
                    <p className="eval-progress-hint">
                        Retrieving relevant chunks from pgvector, applying hybrid
                        fusion, verifying citations, and validating grounded answers.
                    </p>
                </div>
            )}

            {error && (
                <div className="eval-alert eval-alert-error" role="alert">
                    <AlertCircle size={18} />
                    <div className="eval-alert-text">
                        <strong>Something went wrong</strong>
                        <span>{error}</span>
                    </div>
                    <button type="button" onClick={() => setError("")}>
                        Dismiss
                    </button>
                </div>
            )}

            {notice && (
                <div className="eval-alert eval-alert-success" role="status">
                    <CheckCircle2 size={18} />
                    <div className="eval-alert-text">
                        <span>{notice}</span>
                    </div>
                    <button type="button" onClick={() => setNotice("")}>
                        Dismiss
                    </button>
                </div>
            )}

            {/* 4.3 Run Comparison View */}
            {showComparison && selectedRun && (
                <RunComparisonView
                    currentRun={selectedRun}
                    comparisonRun={comparisonRun}
                    runs={runs}
                    onSelectComparisonRun={handleSelectComparison}
                    onClose={() => setShowComparison(false)}
                />
            )}

            {/* 4.1 Donut / Circular Gauge Visual Charts */}
            <section className="eval-overview">
                <div className="eval-section-heading">
                    <div>
                        <h2>Evaluation overview</h2>
                        <p>
                            {selectedRun
                                ? `Metrics from run #${selectedRun.run_id} · ${formatDate(
                                      selectedRun.created_at
                                  )}`
                                : "Run an evaluation to populate these quality metrics."}
                        </p>
                    </div>

                    {selectedRun && (
                        <div className="eval-run-badge-wrap">
                            <span className="eval-run-badge">
                                Active Run #{selectedRun.run_id}
                            </span>
                        </div>
                    )}
                </div>

                <div className="eval-metric-grid">
                    <DonutGaugeCard
                        label="Answer rate"
                        value={formatPercent(metrics?.answer_rate)}
                        percent={metrics?.answer_rate}
                        description={`${answeredCount} answered of ${
                            metrics?.completed_cases ?? 0
                        } completed`}
                        color="success"
                        icon={Sparkles}
                    />

                    <DonutGaugeCard
                        label="Retrieval hit rate"
                        value={formatPercent(metrics?.retrieval_hit_rate)}
                        percent={metrics?.retrieval_hit_rate}
                        description={`${hitCount} hits in ${
                            metrics?.retrieval_evaluable_cases ?? 0
                        } evaluable cases`}
                        color="accent"
                        icon={CheckCircle2}
                    />

                    <DonutGaugeCard
                        label="Abstention rate"
                        value={formatPercent(metrics?.abstention_rate)}
                        percent={metrics?.abstention_rate}
                        description={`${abstainedCount} cases gracefully abstained`}
                        color="amber"
                        icon={Shield}
                    />

                    <article className="eval-metric-card eval-gauge-card color-blue">
                        <div className="eval-gauge-header">
                            <span className="eval-metric-label">
                                Average latency
                            </span>
                            <Clock size={16} className="eval-metric-icon" />
                        </div>
                        <div className="eval-gauge-body">
                            <div className="eval-stat-icon-wrap">
                                <Activity size={28} />
                            </div>
                            <div className="eval-gauge-content">
                                <strong className="eval-metric-value">
                                    {formatLatency(metrics?.average_latency_ms)}
                                </strong>
                                <span className="eval-metric-description">
                                    Avg inference time across{" "}
                                    {metrics?.total_cases ?? cases.length} cases
                                </span>
                            </div>
                        </div>
                    </article>
                </div>

                {selectedRun && (
                    <div className="eval-run-summary">
                        <div>
                            <span>Total cases</span>
                            <strong>{metrics?.total_cases ?? 0}</strong>
                        </div>
                        <div>
                            <span>Completed cases</span>
                            <strong>{metrics?.completed_cases ?? 0}</strong>
                        </div>
                        <div>
                            <span>Errors encountered</span>
                            <strong>{metrics?.error_count ?? 0}</strong>
                        </div>
                        <div>
                            <span>Retrieval evaluable</span>
                            <strong>
                                {metrics?.retrieval_evaluable_cases ?? 0}
                            </strong>
                        </div>
                    </div>
                )}

                {/* 4.2 Latency Distribution Chart */}
                {selectedRun && allResults.length > 0 && (
                    <LatencyDistributionChart
                        results={allResults}
                        onSelectCase={scrollToCase}
                    />
                )}
            </section>

            {/* 4.4 Color-Coded Results & 4.7 Export Toolbar */}
            {selectedRun && (
                <section className="eval-panel eval-results-panel">
                    <div className="eval-section-heading eval-results-header">
                        <div>
                            <h2>Evaluation results</h2>
                            <p>
                                Detailed results for Run #{selectedRun.run_id} ·{" "}
                                {formatDate(selectedRun.created_at)}
                            </p>
                        </div>

                        {/* 4.7 Export Actions */}
                        <div className="eval-results-actions">
                            <button
                                className="eval-export-btn"
                                type="button"
                                onClick={() => exportRunToCSV(selectedRun)}
                                title="Download results as CSV"
                            >
                                <FileSpreadsheet size={15} />
                                <span>Export CSV</span>
                            </button>

                            <button
                                className="eval-export-btn"
                                type="button"
                                onClick={() => exportRunToJSON(selectedRun)}
                                title="Download complete run payload as JSON"
                            >
                                <FileJson size={15} />
                                <span>Export JSON</span>
                            </button>

                            <button
                                className="eval-secondary-button"
                                type="button"
                                onClick={() => setSelectedRun(null)}
                            >
                                Close results
                            </button>
                        </div>
                    </div>

                    {/* Filter & Search Bar */}
                    <div className="eval-filter-toolbar">
                        <div className="eval-filter-tabs">
                            <button
                                type="button"
                                className={`filter-tab ${
                                    filterStatus === "all" ? "active" : ""
                                }`}
                                onClick={() => setFilterStatus("all")}
                            >
                                All ({allResults.length})
                            </button>
                            <button
                                type="button"
                                className={`filter-tab tab-success ${
                                    filterStatus === "answered" ? "active" : ""
                                }`}
                                onClick={() => setFilterStatus("answered")}
                            >
                                Answered ({answeredCount})
                            </button>
                            <button
                                type="button"
                                className={`filter-tab tab-amber ${
                                    filterStatus === "abstained" ? "active" : ""
                                }`}
                                onClick={() => setFilterStatus("abstained")}
                            >
                                Abstained ({abstainedCount})
                            </button>
                            <button
                                type="button"
                                className={`filter-tab tab-hit ${
                                    filterStatus === "hit" ? "active" : ""
                                }`}
                                onClick={() => setFilterStatus("hit")}
                            >
                                Hits ({hitCount})
                            </button>
                            {missCount > 0 && (
                                <button
                                    type="button"
                                    className={`filter-tab tab-miss ${
                                        filterStatus === "miss" ? "active" : ""
                                    }`}
                                    onClick={() => setFilterStatus("miss")}
                                >
                                    Misses ({missCount})
                                </button>
                            )}
                            {errorCount > 0 && (
                                <button
                                    type="button"
                                    className={`filter-tab tab-error ${
                                        filterStatus === "error" ? "active" : ""
                                    }`}
                                    onClick={() => setFilterStatus("error")}
                                >
                                    Errors ({errorCount})
                                </button>
                            )}
                        </div>

                        <div className="eval-search-box">
                            <Search size={14} className="search-icon" />
                            <input
                                type="search"
                                placeholder="Search questions or answers…"
                                value={searchQuery}
                                onChange={(e) => setSearchQuery(e.target.value)}
                            />
                            {searchQuery && (
                                <button
                                    type="button"
                                    className="clear-search"
                                    onClick={() => setSearchQuery("")}
                                >
                                    <X size={12} />
                                </button>
                            )}
                        </div>
                    </div>

                    {filteredResults.length === 0 ? (
                        <div className="eval-empty-state">
                            <Filter size={24} />
                            <strong>No matching evaluation results</strong>
                            <span>
                                Try clearing your search query or filter tab.
                            </span>
                        </div>
                    ) : (
                        <div className="eval-results-list">
                            {filteredResults.map((result, index) => {
                                const isAbstained = Boolean(result.abstained);
                                const isError = result.status === "error";
                                const isHit = result.retrieval_hit === true;
                                const isMiss = result.retrieval_hit === false;

                                // 4.4 Color-coded Card Status
                                const cardStatusClass = isError
                                    ? "card-error"
                                    : isAbstained
                                      ? "card-abstained"
                                      : isHit
                                        ? "card-hit"
                                        : isMiss
                                          ? "card-miss"
                                          : "card-answered";

                                return (
                                    <details
                                        id={`case-card-${result.case_id}`}
                                        className={`eval-result-item ${cardStatusClass}`}
                                        key={`${selectedRun.run_id}-${
                                            result.case_id ?? index
                                        }`}
                                    >
                                        <summary>
                                            <span className="eval-result-title">
                                                <span className="case-id-tag">
                                                    #{result.case_id ?? "—"}
                                                </span>
                                                <span className="case-question-text">
                                                    {result.question}
                                                </span>
                                            </span>

                                            <div className="eval-result-badges">
                                                {result.confidence_score !==
                                                    null &&
                                                    result.confidence_score !==
                                                        undefined && (
                                                        <span
                                                            className="eval-badge badge-confidence"
                                                            title="Retrieval confidence score"
                                                        >
                                                            {(
                                                                result.confidence_score *
                                                                100
                                                            ).toFixed(0)}
                                                            % conf
                                                        </span>
                                                    )}

                                                {result.retrieval_hit !==
                                                    null &&
                                                    result.retrieval_hit !==
                                                        undefined && (
                                                        <span
                                                            className={`eval-badge ${
                                                                isHit
                                                                    ? "badge-hit"
                                                                    : "badge-miss"
                                                            }`}
                                                        >
                                                            {isHit ? (
                                                                <Check size={11} />
                                                            ) : (
                                                                <X size={11} />
                                                            )}
                                                            {isHit
                                                                ? "Hit"
                                                                : "Miss"}
                                                        </span>
                                                    )}

                                                <span
                                                    className={`eval-status ${
                                                        isError
                                                            ? "is-error"
                                                            : isAbstained
                                                              ? "is-abstained"
                                                              : "is-completed"
                                                    }`}
                                                >
                                                    {isError ? (
                                                        <>
                                                            <XCircle size={12} />
                                                            <span>Error</span>
                                                        </>
                                                    ) : isAbstained ? (
                                                        <>
                                                            <Shield size={12} />
                                                            <span>Abstained</span>
                                                        </>
                                                    ) : (
                                                        <>
                                                            <CheckCircle2
                                                                size={12}
                                                            />
                                                            <span>Answered</span>
                                                        </>
                                                    )}
                                                </span>
                                            </div>
                                        </summary>

                                        <div className="eval-result-detail">
                                            {isError ? (
                                                <div className="eval-error-box">
                                                    <AlertCircle size={16} />
                                                    <p>
                                                        This case failed during
                                                        evaluation. Error type:{" "}
                                                        <strong>
                                                            {result.error_type ||
                                                                "Unknown"}
                                                        </strong>
                                                    </p>
                                                </div>
                                            ) : (
                                                <>
                                                    <div className="eval-result-facts">
                                                        <div>
                                                            <span>Latency</span>
                                                            <strong>
                                                                {formatLatency(
                                                                    result.latency_ms
                                                                )}
                                                            </strong>
                                                        </div>
                                                        <div>
                                                            <span>
                                                                Sources cited
                                                            </span>
                                                            <strong>
                                                                {result.source_count ??
                                                                    0}
                                                            </strong>
                                                        </div>
                                                        <div>
                                                            <span>
                                                                Retrieval match
                                                            </span>
                                                            <strong>
                                                                {result.retrieval_hit ===
                                                                null
                                                                    ? "Not evaluated"
                                                                    : result.retrieval_hit
                                                                      ? "Hit (found expected doc)"
                                                                      : "Miss (expected doc missing)"}
                                                            </strong>
                                                        </div>
                                                    </div>

                                                    {/* 4.8 Answer Diff View */}
                                                    <div className="eval-detail-section">
                                                        <AnswerDiffView
                                                            generatedAnswer={
                                                                result.clean_answer ||
                                                                result.answer
                                                            }
                                                            expectedAnswer={
                                                                result.expected_answer
                                                            }
                                                        />
                                                    </div>

                                                    {/* 4.6 Retrieval Overlap Visualization */}
                                                    <div className="eval-detail-section">
                                                        <h4 className="eval-detail-subtitle">
                                                            Document Retrieval
                                                            Overlap
                                                        </h4>
                                                        <RetrievalOverlapVisualizer
                                                            expectedIds={
                                                                result.expected_document_ids ||
                                                                []
                                                            }
                                                            retrievedIds={
                                                                result.retrieved_document_ids ||
                                                                []
                                                            }
                                                        />
                                                    </div>
                                                </>
                                            )}
                                        </div>
                                    </details>
                                );
                            })}
                        </div>
                    )}
                </section>
            )}

            {/* Dataset and Run History Grid */}
            <section className="eval-content-grid">
                <div className="eval-panel">
                    <div className="eval-section-heading">
                        <div>
                            <h2>Evaluation dataset</h2>
                            <p>
                                Add questions representing real employee requests to
                                benchmark system performance.
                            </p>
                        </div>
                        <span className="eval-count">
                            {cases.length} test cases
                        </span>
                    </div>

                    <form className="eval-case-form" onSubmit={handleCreateCase}>
                        <label htmlFor="eval-question">Question *</label>
                        <textarea
                            id="eval-question"
                            value={question}
                            onChange={(event) => setQuestion(event.target.value)}
                            maxLength={2000}
                            rows={3}
                            placeholder="Example: What approval is required to access production databases?"
                            required
                        />

                        <label htmlFor="eval-expected-answer">
                            Expected answer <span>(optional reference)</span>
                        </label>
                        <textarea
                            id="eval-expected-answer"
                            value={expectedAnswer}
                            onChange={(event) =>
                                setExpectedAnswer(event.target.value)
                            }
                            maxLength={5000}
                            rows={3}
                            placeholder="Reference answer for side-by-side diff comparison."
                        />

                        <label htmlFor="eval-document-ids">
                            Expected document IDs <span>(optional, comma-separated)</span>
                        </label>
                        <input
                            id="eval-document-ids"
                            type="text"
                            value={expectedDocumentIds}
                            onChange={(event) =>
                                setExpectedDocumentIds(event.target.value)
                            }
                            placeholder="Example: 4, 12"
                        />
                        <p className="eval-field-help">
                            Document IDs from your Knowledge Base. Retrieval hit rate
                            checks if any of these are retrieved.
                        </p>

                        <button
                            className="eval-primary-button eval-add-button"
                            type="submit"
                            disabled={savingCase}
                        >
                            {savingCase ? (
                                <>
                                    <RefreshCw
                                        size={14}
                                        className="eval-spinner-icon"
                                    />
                                    <span>Saving case…</span>
                                </>
                            ) : (
                                <>
                                    <Plus size={14} />
                                    <span>Add evaluation case</span>
                                </>
                            )}
                        </button>
                    </form>

                    <div className="eval-case-list">
                        {loadingCases ? (
                            <p className="eval-empty-state">
                                Loading evaluation cases…
                            </p>
                        ) : cases.length === 0 ? (
                            <div className="eval-empty-state">
                                <strong>No evaluation cases yet</strong>
                                <span>
                                    Add your first test case using the form above.
                                </span>
                            </div>
                        ) : (
                            cases.map((item) => (
                                <article className="eval-case-item" key={item.id}>
                                    <div className="eval-case-main">
                                        <span className="eval-case-id">
                                            CASE #{item.id}
                                        </span>
                                        <p>{item.question}</p>

                                        <div className="eval-case-meta">
                                            <span>
                                                Expected docs:{" "}
                                                {item.expected_document_ids?.length
                                                    ? item.expected_document_ids.join(
                                                          ", "
                                                      )
                                                    : "None"}
                                            </span>
                                            <span>{formatDate(item.created_at)}</span>
                                        </div>
                                    </div>

                                    <button
                                        className="eval-text-button eval-delete-button"
                                        type="button"
                                        onClick={() => handleDeleteCase(item.id)}
                                        disabled={deletingCaseId === item.id}
                                        aria-label={`Delete evaluation case ${item.id}`}
                                    >
                                        <Trash2 size={14} />
                                        <span>
                                            {deletingCaseId === item.id
                                                ? "Deleting…"
                                                : "Delete"}
                                        </span>
                                    </button>
                                </article>
                            ))
                        )}
                    </div>
                </div>

                <aside className="eval-panel eval-history-panel">
                    <div className="eval-section-heading">
                        <div>
                            <h2>Run history</h2>
                            <p>Select any previous evaluation run to inspect.</p>
                        </div>
                    </div>

                    {loadingRuns ? (
                        <p className="eval-empty-state">Loading run history…</p>
                    ) : runs.length === 0 ? (
                        <div className="eval-empty-state">
                            <strong>No runs recorded</strong>
                            <span>
                                Completed evaluation runs will be preserved here.
                            </span>
                        </div>
                    ) : (
                        <div className="eval-run-list">
                            {runs.map((run) => (
                                <button
                                    type="button"
                                    className={`eval-run-item ${
                                        selectedRun?.run_id === run.run_id
                                            ? "is-selected"
                                            : ""
                                    }`}
                                    key={run.run_id}
                                    onClick={() => handleOpenRun(run.run_id)}
                                    disabled={openingRunId === run.run_id}
                                >
                                    <span className="eval-run-item-top">
                                        <strong>Run #{run.run_id}</strong>
                                        <span className="eval-run-count-pill">
                                            {openingRunId === run.run_id
                                                ? "Opening…"
                                                : `${
                                                      run.metrics?.total_cases ?? 0
                                                  } cases`}
                                        </span>
                                    </span>

                                    <span className="eval-run-item-date">
                                        {formatDate(run.created_at)}
                                    </span>

                                    <span className="eval-run-item-metrics">
                                        <span>
                                            Answer:{" "}
                                            {formatPercent(
                                                run.metrics?.answer_rate
                                            )}
                                        </span>
                                        <span>
                                            Hit:{" "}
                                            {formatPercent(
                                                run.metrics?.retrieval_hit_rate
                                            )}
                                        </span>
                                        <span>
                                            {formatLatency(
                                                run.metrics?.average_latency_ms
                                            )}
                                        </span>
                                    </span>
                                </button>
                            ))}
                        </div>
                    )}
                </aside>
            </section>
        </main>
    );
}
