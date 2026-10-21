
import { useEffect, useState } from "react";
import {
    Activity,
    CheckCircle2,
    Clock3,
    Laptop,
    LockKeyhole,
    Moon,
    RefreshCw,
    ShieldCheck,
    Sun,
    UserRound,
    XCircle,
} from "lucide-react";
import "./Settings.css";

function formatDate(value) {
    if (!value) return "Not provided by the server";

    const date = new Date(value);

    if (Number.isNaN(date.getTime())) return "Unavailable";

    return new Intl.DateTimeFormat("en-IN", {
        dateStyle: "medium",
        timeStyle: "short",
    }).format(date);
}

function StatusBadge({ status }) {
    const ready = status === "online";

    return (
        <span className={`settings-status ${ready ? "is-online" : "is-offline"}`}>
            {ready ? <CheckCircle2 size={15} /> : <XCircle size={15} />}
            {ready ? "Connected" : "Unavailable"}
        </span>
    );
}

export default function SettingsPage({
    apiBaseUrl,
    currentUser,
    theme,
    onThemeChange,
    onSignOut,
}) {
    const [backendStatus, setBackendStatus] = useState("checking");
    const [session, setSession] = useState(null);
    const [statusError, setStatusError] = useState("");
    const [checking, setChecking] = useState(false);

    async function refreshStatus() {
        setChecking(true);
        setStatusError("");

        try {
            const [healthResponse, sessionResponse] = await Promise.all([
                fetch(`${apiBaseUrl}/health`, {
                    method: "GET",
                    credentials: "include",
                    headers: { Accept: "application/json" },
                }),
                fetch(`${apiBaseUrl}/api/v1/auth/me`, {
                    method: "GET",
                    credentials: "include",
                    headers: { Accept: "application/json" },
                }),
            ]);

            setBackendStatus(healthResponse.ok ? "online" : "offline");

            if (sessionResponse.ok) {
                setSession(await sessionResponse.json());
            } else {
                setSession(null);
            }

            if (!healthResponse.ok) {
                setStatusError(
                    `Backend health check returned HTTP ${healthResponse.status}.`
                );
            } else if (!sessionResponse.ok) {
                setStatusError(
                    "The current session could not be verified. You may need to sign in again."
                );
            }
        } catch {
            setBackendStatus("offline");
            setSession(null);
            setStatusError(
                "Could not reach the backend. Check that FastAPI is running."
            );
        } finally {
            setChecking(false);
        }
    }

    useEffect(() => {
        refreshStatus();
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [apiBaseUrl]);

    const employeeId =
        session?.principal_id ||
        currentUser?.principal_id ||
        "Unavailable";

    return (
        <section className="settings-workspace">
            <div className="settings-heading-row">
                <div>
                    <span className="settings-eyebrow">
                        <Activity size={14} />
                        WORKSPACE PREFERENCES
                    </span>

                    <h1>Settings</h1>

                    <p className="settings-subtitle">
                        Manage your appearance, review your account, and check the
                        application connection.
                    </p>
                </div>

                <button
                    className="settings-refresh-button"
                    type="button"
                    onClick={refreshStatus}
                    disabled={checking}
                >
                    <RefreshCw
                        size={16}
                        className={checking ? "settings-spin" : ""}
                    />
                    {checking ? "Checking..." : "Refresh status"}
                </button>
            </div>

            <section
                className="settings-panel"
                aria-labelledby="settings-appearance-title"
            >
                <div className="settings-panel-icon">
                    <Laptop size={21} />
                </div>

                <div className="settings-panel-body">
                    <h2 id="settings-appearance-title">Appearance</h2>

                    <p>Choose the theme for your current workspace.</p>

                    <div
                        className="settings-theme-options"
                        role="group"
                        aria-label="Appearance theme"
                    >
                        <button
                            type="button"
                            className={`settings-theme-option ${theme === "light" ? "selected" : ""
                                }`}
                            aria-pressed={theme === "light"}
                            onClick={() => onThemeChange("light")}
                        >
                            <Sun size={19} />

                            <span>
                                <strong>Light</strong>
                                <small>Bright, clean workspace</small>
                            </span>

                            {theme === "light" && <CheckCircle2 size={17} />}
                        </button>

                        <button
                            type="button"
                            className={`settings-theme-option ${theme === "dark" ? "selected" : ""
                                }`}
                            aria-pressed={theme === "dark"}
                            onClick={() => onThemeChange("dark")}
                        >
                            <Moon size={19} />

                            <span>
                                <strong>Dark</strong>
                                <small>Lower-light workspace</small>
                            </span>

                            {theme === "dark" && <CheckCircle2 size={17} />}
                        </button>
                    </div>

                    <p className="settings-help-text">
                        The theme changes immediately and is held in application state.
                    </p>
                </div>
            </section>

            <section
                className="settings-panel"
                aria-labelledby="settings-account-title"
            >
                <div className="settings-panel-icon">
                    <UserRound size={21} />
                </div>

                <div className="settings-panel-body">
                    <h2 id="settings-account-title">Employee account</h2>

                    <p>Account details returned by your authenticated session.</p>

                    <dl className="settings-details">
                        <div>
                            <dt>Employee ID</dt>
                            <dd>{employeeId}</dd>
                        </div>

                        <div>
                            <dt>Authentication</dt>
                            <dd>Secure session cookie</dd>
                        </div>

                        <div>
                            <dt>Session expires</dt>
                            <dd>{formatDate(session?.expires_at)}</dd>
                        </div>

                        <div>
                            <dt>Session status</dt>
                            <dd>{session ? "Verified" : "Not verified"}</dd>
                        </div>
                    </dl>
                </div>
            </section>

            <section
                className="settings-panel"
                aria-labelledby="settings-security-title"
            >
                <div className="settings-panel-icon">
                    <ShieldCheck size={21} />
                </div>

                <div className="settings-panel-body">
                    <h2 id="settings-security-title">Security</h2>

                    <p>
                        Your requests use the signed-in employee session. Document
                        permissions are enforced by the backend.
                    </p>

                    <div className="settings-security-note">
                        <LockKeyhole size={17} />

                        <span>
                            Sign out when you finish using this shared or unattended device.
                        </span>
                    </div>

                    <button
                        className="settings-signout-button"
                        type="button"
                        onClick={onSignOut}
                    >
                        Sign out securely
                    </button>
                </div>
            </section>

            <section
                className="settings-panel"
                aria-labelledby="settings-status-title"
            >
                <div className="settings-panel-icon">
                    <Activity size={21} />
                </div>

                <div className="settings-panel-body">
                    <h2 id="settings-status-title">Application status</h2>

                    <p>
                        Connection checks use read-only status and session endpoints.
                    </p>

                    <div className="settings-details settings-status-details">
                        <div>
                            <span className="settings-detail-label">Frontend</span>

                            <span className="settings-status is-online">
                                <CheckCircle2 size={15} />
                                Running
                            </span>
                        </div>

                        <div>
                            <span className="settings-detail-label">Backend API</span>

                            {backendStatus === "checking" ? (
                                <span className="settings-status is-checking">
                                    <Clock3 size={15} />
                                    Checking
                                </span>
                            ) : (
                                <StatusBadge status={backendStatus} />
                            )}
                        </div>

                        <div>
                            <span className="settings-detail-label">API address</span>
                            <code>{apiBaseUrl}</code>
                        </div>
                    </div>

                    {statusError && (
                        <p className="settings-status-error" role="status">
                            {statusError}
                        </p>
                    )}
                </div>
            </section>

            <p className="settings-footer-note">
                Settings do not change employee permissions or modify stored documents.
            </p>
        </section>
    );
}
