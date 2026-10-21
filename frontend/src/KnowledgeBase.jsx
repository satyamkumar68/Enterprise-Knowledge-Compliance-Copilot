
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
    Files,
    Search,
    RefreshCw,
    FileText,
    CheckCircle2,
    Clock3,
    AlertCircle,
    LoaderCircle,
    ShieldCheck,
    UploadCloud,
    X,
    Trash2,
} from "lucide-react";
import "./KnowledgeBase.css";

const MAX_UPLOAD_SIZE = 10 * 1024 * 1024;
const ACCEPTED_EXTENSIONS = [".pdf", ".docx", ".txt", ".md"];

function formatDate(value) {
    if (!value) return "Unavailable";

    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return "Unavailable";

    return new Intl.DateTimeFormat("en-IN", {
        day: "2-digit",
        month: "short",
        year: "numeric",
    }).format(date);
}

function StatusIcon({ status }) {
    switch (String(status).toLowerCase()) {
        case "indexed":
            return <CheckCircle2 size={15} />;
        case "processing":
        case "pending":
            return <Clock3 size={15} />;
        case "failed":
            return <AlertCircle size={15} />;
        default:
            return <FileText size={15} />;
    }
}

function getCsrfToken() {
    const cookie = document.cookie
        .split("; ")
        .find((item) => item.startsWith("kc_csrf="));

    return cookie
        ? decodeURIComponent(cookie.substring("kc_csrf=".length))
        : "";
}

function getUploadErrorMessage(status, detail) {
    if (status === 401) {
        return "Your session has expired. Please sign in again.";
    }

    if (status === 413) {
        return "This file exceeds the 10 MB upload limit.";
    }

    if (status === 415) {
        return "Unsupported file type. Choose a PDF, DOCX, TXT, or Markdown file.";
    }

    if (status === 422) {
        return detail || "The document could not be processed. Check that it contains readable text.";
    }

    if (status === 503) {
        return detail || "The document service is temporarily unavailable. Please try again later.";
    }

    return detail || `Upload failed (HTTP ${status}).`;
}

async function readErrorDetail(response) {
    try {
        const body = await response.json();
        return typeof body.detail === "string" ? body.detail : "";
    } catch {
        return "";
    }
}

export default function KnowledgeBase({ apiBaseUrl }) {
    const [documents, setDocuments] = useState([]);
    const [total, setTotal] = useState(0);
    const [loading, setLoading] = useState(true);
    const [refreshing, setRefreshing] = useState(false);
    const [error, setError] = useState("");
    const [search, setSearch] = useState("");
    const [statusFilter, setStatusFilter] = useState("all");

    const [selectedFile, setSelectedFile] = useState(null);
    const [uploading, setUploading] = useState(false);
    const [uploadError, setUploadError] = useState("");
    const [uploadSuccess, setUploadSuccess] = useState("");

    const [deletingId, setDeletingId] = useState(null);
    const [deleteError, setDeleteError] = useState("");
    const [deleteSuccess, setDeleteSuccess] = useState("");

    const fileInputRef = useRef(null);

    const loadDocuments = useCallback(async (refresh = false) => {
        if (refresh) {
            setRefreshing(true);
        } else {
            setLoading(true);
        }

        setError("");

        try {
            const response = await fetch(
                `${apiBaseUrl}/api/v1/documents`,
                {
                    credentials: "include",
                    headers: {
                        Accept: "application/json",
                    },
                }
            );

            if (!response.ok) {
                const detail = await readErrorDetail(response);

                if (response.status === 401) {
                    throw new Error(
                        "Your session has expired. Please sign in again."
                    );
                }

                throw new Error(
                    detail || `Could not load documents (HTTP ${response.status}).`
                );
            }

            const data = await response.json();
            const rows = Array.isArray(data.documents)
                ? data.documents
                : [];

            setDocuments(rows);
            setTotal(
                Number.isFinite(data.total) ? data.total : rows.length
            );

            return true;
        } catch (err) {
            setError(
                err instanceof Error
                    ? err.message
                    : "An unexpected error occurred."
            );
            return false;
        } finally {
            setLoading(false);
            setRefreshing(false);
        }
    }, [apiBaseUrl]);

    useEffect(() => {
        loadDocuments();
    }, [loadDocuments]);

    const filteredDocuments = useMemo(() => {
        const query = search.trim().toLowerCase();

        return documents.filter((doc) => {
            const filename = String(doc.filename || "").toLowerCase();
            const status = String(doc.status || "unknown").toLowerCase();

            return (
                filename.includes(query) &&
                (statusFilter === "all" || status === statusFilter)
            );
        });
    }, [documents, search, statusFilter]);

    const indexedCount = documents.filter(
        (doc) => String(doc.status).toLowerCase() === "indexed"
    ).length;

    function validateFile(file) {
        if (!file) {
            return "Choose a document before uploading.";
        }

        const dotIndex = file.name.lastIndexOf(".");
        const extension = dotIndex >= 0
            ? file.name.slice(dotIndex).toLowerCase()
            : "";

        if (!ACCEPTED_EXTENSIONS.includes(extension)) {
            return "Unsupported file type. Choose a PDF, DOCX, TXT, or Markdown file.";
        }

        if (file.size === 0) {
            return "The selected file is empty.";
        }

        if (file.size > MAX_UPLOAD_SIZE) {
            return "The file exceeds the 10 MB upload limit.";
        }

        return "";
    }

    function handleFileChange(event) {
        const file = event.target.files?.[0] || null;

        setSelectedFile(file);
        setUploadError("");
        setUploadSuccess("");

        if (file) {
            const validationError = validateFile(file);

            if (validationError) {
                setUploadError(validationError);
                setSelectedFile(null);
                event.target.value = "";
            }
        }
    }

    async function handleUpload(event) {
        event.preventDefault();

        setUploadError("");
        setUploadSuccess("");

        const validationError = validateFile(selectedFile);

        if (validationError) {
            setUploadError(validationError);
            return;
        }

        const formData = new FormData();
        formData.append("file", selectedFile);

        setUploading(true);

        try {
            const response = await fetch(
                `${apiBaseUrl}/api/v1/documents/upload`,
                {
                    method: "POST",
                    credentials: "include",
                    headers: {
                        Accept: "application/json",
                        "X-CSRF-Token": getCsrfToken(),
                    },
                    body: formData,
                }
            );

            if (!response.ok) {
                const detail = await readErrorDetail(response);
                throw new Error(
                    getUploadErrorMessage(response.status, detail)
                );
            }

            const result = await response.json();

            setUploadSuccess(
                `${result.filename || selectedFile.name} uploaded successfully. Status: ${result.status || "processed"}.`
            );

            setSelectedFile(null);

            if (fileInputRef.current) {
                fileInputRef.current.value = "";
            }

            const refreshed = await loadDocuments(true);

            if (!refreshed) {
                setUploadSuccess(
                    "Upload succeeded, but the document list could not refresh. Use Refresh to try again."
                );
            }
        } catch (err) {
            setUploadError(
                err instanceof Error
                    ? err.message
                    : "An unexpected upload error occurred."
            );
        } finally {
            setUploading(false);
        }
    }

    function clearUploadMessages() {
        setUploadError("");
        setUploadSuccess("");
    }

    async function handleDelete(doc) {
        if (deletingId !== null) return;

        const filename = doc.filename || "this document";

        const confirmed = window.confirm(
            `Remove "${filename}" from your Knowledge Base?\n\n` +
            "Your access will be removed. If no other users have access, " +
            "the document and its indexed chunks will be deleted permanently."
        );

        if (!confirmed) return;

        setDeletingId(doc.document_id);
        setDeleteError("");
        setDeleteSuccess("");

        try {
            const response = await fetch(
                `${apiBaseUrl}/api/v1/documents/${doc.document_id}`,
                {
                    method: "DELETE",
                    credentials: "include",
                    headers: {
                        Accept: "application/json",
                        "X-CSRF-Token": getCsrfToken(),
                    },
                }
            );

            if (!response.ok) {
                const detail = await readErrorDetail(response);

                if (response.status === 401) {
                    throw new Error(
                        "Your session has expired. Please sign in again."
                    );
                }

                if (response.status === 404) {
                    throw new Error(
                        detail || "The document was not found or you cannot remove it."
                    );
                }

                throw new Error(
                    detail || `Could not remove document (HTTP ${response.status}).`
                );
            }

            const result = await response.json();

            setDeleteSuccess(
                result.message || `"${filename}" was removed successfully.`
            );

            const refreshed = await loadDocuments(true);

            if (!refreshed) {
                setDeleteSuccess(
                    "The delete request succeeded, but the list could not refresh. Click Refresh to reload it."
                );
            }
        } catch (err) {
            setDeleteError(
                err instanceof Error
                    ? err.message
                    : "An unexpected deletion error occurred."
            );
        } finally {
            setDeletingId(null);
        }
    }

    return (
        <section className="kb-workspace">
            <div className="kb-heading-row">
                <div>
                    <div className="kb-eyebrow">
                        <ShieldCheck size={14} />
                        ACCESS-CONTROLLED DOCUMENTS
                    </div>

                    <h1>Knowledge Base</h1>

                    <p className="kb-subtitle">
                        Browse, upload, and search documents available to your account.
                    </p>
                </div>

                <button
                    className="kb-refresh-button"
                    onClick={() => loadDocuments(true)}
                    disabled={loading || refreshing || deletingId !== null}
                    type="button"
                >
                    {refreshing ? (
                        <LoaderCircle className="kb-spin" size={16} />
                    ) : (
                        <RefreshCw size={16} />
                    )}
                    {refreshing ? "Refreshing..." : "Refresh"}
                </button>
            </div>

            <div className="kb-stats-grid">
                <div className="kb-stat-card">
                    <div className="kb-stat-icon">
                        <Files size={20} />
                    </div>
                    <div>
                        <span>Available documents</span>
                        <strong>{loading ? "—" : total}</strong>
                    </div>
                </div>

                <div className="kb-stat-card">
                    <div className="kb-stat-icon kb-green">
                        <CheckCircle2 size={20} />
                    </div>
                    <div>
                        <span>Successfully indexed</span>
                        <strong>{loading ? "—" : indexedCount}</strong>
                    </div>
                </div>
            </div>

            <section className="kb-upload-panel" aria-labelledby="kb-upload-title">
                <div className="kb-upload-heading">
                    <div className="kb-upload-icon">
                        <UploadCloud size={22} />
                    </div>
                    <div>
                        <h2 id="kb-upload-title">Upload a document</h2>
                        <p>Add a document to your private knowledge base.</p>
                    </div>
                </div>

                <form onSubmit={handleUpload}>
                    <label className="kb-file-picker">
                        <FileText size={20} />

                        <span className="kb-file-picker-copy">
                            <strong>
                                {selectedFile
                                    ? selectedFile.name
                                    : "Choose a document"}
                            </strong>
                            <small>
                                PDF, DOCX, TXT, or MD · Maximum 10 MB
                            </small>
                        </span>

                        {selectedFile && (
                            <button
                                className="kb-clear-file"
                                type="button"
                                aria-label="Remove selected file"
                                disabled={uploading}
                                onClick={(event) => {
                                    event.preventDefault();
                                    event.stopPropagation();
                                    setSelectedFile(null);
                                    clearUploadMessages();

                                    if (fileInputRef.current) {
                                        fileInputRef.current.value = "";
                                    }
                                }}
                            >
                                <X size={17} />
                            </button>
                        )}

                        <input
                            ref={fileInputRef}
                            type="file"
                            accept=".pdf,.docx,.txt,.md"
                            onChange={handleFileChange}
                            disabled={uploading}
                            aria-label="Choose a document to upload"
                        />
                    </label>

                    <div className="kb-upload-actions">
                        <span className="kb-upload-hint">
                            <ShieldCheck size={14} />
                            Access is granted to your account only.
                        </span>

                        <button
                            className="kb-upload-button"
                            type="submit"
                            disabled={!selectedFile || uploading}
                        >
                            {uploading ? (
                                <>
                                    <LoaderCircle
                                        className="kb-spin"
                                        size={16}
                                    />
                                    Uploading and indexing...
                                </>
                            ) : (
                                <>
                                    <UploadCloud size={16} />
                                    Upload document
                                </>
                            )}
                        </button>
                    </div>
                </form>

                {uploading && (
                    <div className="kb-upload-progress" role="status">
                        <div className="kb-upload-progress-bar" />
                        <span>
                            Processing your document. This may take a little while.
                        </span>
                    </div>
                )}

                {uploadError && (
                    <div
                        className="kb-upload-feedback kb-upload-feedback-error"
                        role="alert"
                    >
                        <AlertCircle size={18} />
                        <span>{uploadError}</span>
                        <button
                            type="button"
                            aria-label="Dismiss upload error"
                            onClick={() => setUploadError("")}
                        >
                            <X size={16} />
                        </button>
                    </div>
                )}

                {uploadSuccess && (
                    <div
                        className="kb-upload-feedback kb-upload-feedback-success"
                        role="status"
                    >
                        <CheckCircle2 size={18} />
                        <span>{uploadSuccess}</span>
                        <button
                            type="button"
                            aria-label="Dismiss success message"
                            onClick={() => setUploadSuccess("")}
                        >
                            <X size={16} />
                        </button>
                    </div>
                )}
            </section>

            <div className="kb-panel">
                <div className="kb-panel-heading">
                    <div>
                        <h2>Your documents</h2>
                        <p>
                            Only documents your account is authorized to read are listed.
                        </p>
                    </div>

                    {!loading && (
                        <span className="kb-count">
                            {filteredDocuments.length} shown
                        </span>
                    )}
                </div>

                <div className="kb-filters">
                    <label className="kb-search">
                        <Search size={17} />
                        <input
                            type="search"
                            value={search}
                            onChange={(event) => setSearch(event.target.value)}
                            placeholder="Search by filename..."
                            aria-label="Search documents by filename"
                        />
                    </label>

                    <label className="kb-status-filter">
                        <span>Status</span>
                        <select
                            value={statusFilter}
                            onChange={(event) => setStatusFilter(event.target.value)}
                            aria-label="Filter documents by status"
                        >
                            <option value="all">All statuses</option>
                            <option value="indexed">Indexed</option>
                            <option value="processing">Processing</option>
                            <option value="pending">Pending</option>
                            <option value="failed">Failed</option>
                        </select>
                    </label>
                </div>

                {deleteError && (
                    <div className="kb-delete-feedback kb-delete-feedback-error" role="alert">
                        <AlertCircle size={18} />
                        <span>{deleteError}</span>
                        <button
                            type="button"
                            aria-label="Dismiss deletion error"
                            onClick={() => setDeleteError("")}
                        >
                            <X size={16} />
                        </button>
                    </div>
                )}

                {deleteSuccess && (
                    <div className="kb-delete-feedback kb-delete-feedback-success" role="status">
                        <CheckCircle2 size={18} />
                        <span>{deleteSuccess}</span>
                        <button
                            type="button"
                            aria-label="Dismiss deletion message"
                            onClick={() => setDeleteSuccess("")}
                        >
                            <X size={16} />
                        </button>
                    </div>
                )}

                {error && (
                    <div className="kb-error" role="alert">
                        <AlertCircle size={20} />
                        <div>
                            <strong>Could not load documents</strong>
                            <p>{error}</p>
                            <button
                                type="button"
                                onClick={() => loadDocuments()}
                            >
                                Try again
                            </button>
                        </div>
                    </div>
                )}

                {!error && loading && (
                    <div className="kb-message" role="status">
                        <LoaderCircle className="kb-spin" size={23} />
                        Loading your authorized documents...
                    </div>
                )}

                {!error && !loading && filteredDocuments.length === 0 && (
                    <div className="kb-message kb-empty">
                        <Files size={27} />
                        <strong>
                            {documents.length === 0
                                ? "No documents available yet"
                                : "No matching documents"}
                        </strong>
                        <p>
                            {documents.length === 0
                                ? "Upload a document above to start building your knowledge base."
                                : "Try another filename or status filter."}
                        </p>

                        {(search || statusFilter !== "all") && (
                            <button
                                type="button"
                                onClick={() => {
                                    setSearch("");
                                    setStatusFilter("all");
                                }}
                            >
                                Clear filters
                            </button>
                        )}
                    </div>
                )}

                {!error && !loading && filteredDocuments.length > 0 && (
                    <div className="kb-table-wrap">
                        <table className="kb-table">
                            <thead>
                                <tr>
                                    <th>Document</th>
                                    <th>Status</th>
                                    <th>Chunks</th>
                                    <th>Added</th>
                                    <th>Actions</th>
                                </tr>
                            </thead>

                            <tbody>
                                {filteredDocuments.map((doc) => {
                                    const status = String(
                                        doc.status || "unknown"
                                    ).toLowerCase();
                                    const isDeleting =
                                        deletingId === doc.document_id;
                                    const anotherDeletionInProgress =
                                        deletingId !== null && !isDeleting;

                                    return (
                                        <tr key={doc.document_id}>
                                            <td>
                                                <div className="kb-document">
                                                    <div className="kb-file-icon">
                                                        <FileText size={19} />
                                                    </div>
                                                    <div>
                                                        <strong>
                                                            {doc.filename || "Untitled"}
                                                        </strong>
                                                        <small>
                                                            Document ID: {doc.document_id}
                                                        </small>
                                                    </div>
                                                </div>
                                            </td>

                                            <td>
                                                <span
                                                    className={`kb-badge kb-status-${status}`}
                                                >
                                                    <StatusIcon status={status} />
                                                    {status.charAt(0).toUpperCase() +
                                                        status.slice(1)}
                                                </span>
                                            </td>

                                            <td>{doc.chunk_count ?? 0}</td>

                                            <td>{formatDate(doc.created_at)}</td>

                                            <td>
                                                <button
                                                    className="kb-delete-button"
                                                    type="button"
                                                    onClick={() => handleDelete(doc)}
                                                    disabled={
                                                        isDeleting ||
                                                        anotherDeletionInProgress ||
                                                        uploading ||
                                                        refreshing
                                                    }
                                                    aria-label={`Delete ${doc.filename || "document"}`}
                                                    title="Remove document"
                                                >
                                                    {isDeleting ? (
                                                        <LoaderCircle
                                                            size={15}
                                                            className="kb-spin"
                                                        />
                                                    ) : (
                                                        <Trash2 size={15} />
                                                    )}
                                                    {isDeleting ? "Removing..." : "Delete"}
                                                </button>
                                            </td>
                                        </tr>
                                    );
                                })}
                            </tbody>
                        </table>
                    </div>
                )}
            </div>

            <p className="kb-security-note">
                <ShieldCheck size={15} />
                Document access is checked by the backend.
            </p>
        </section>
    );
}
