
import { useState } from "react";
import {
    LockKeyhole,
    ShieldCheck,
    Eye,
    EyeOff,
    UserPlus,
} from "lucide-react";
import "./Login.css";

function getApiBaseUrl() {
    const frontendHost = window.location.hostname;
    const configuredUrl =
        import.meta.env.VITE_API_BASE_URL ||
        `http://${frontendHost}:8000`;

    const apiUrl = new URL(configuredUrl);

    if (
        ["localhost", "127.0.0.1"].includes(frontendHost) &&
        ["localhost", "127.0.0.1"].includes(apiUrl.hostname)
    ) {
        apiUrl.hostname = frontendHost;
    }

    return apiUrl.origin;
}

const API_BASE_URL = getApiBaseUrl();

export default function Login({ onLogin }) {
    const [mode, setMode] = useState("login");
    const [principalId, setPrincipalId] = useState("");
    const [password, setPassword] = useState("");
    const [confirmPassword, setConfirmPassword] = useState("");
    const [showPassword, setShowPassword] = useState(false);
    const [error, setError] = useState("");
    const [success, setSuccess] = useState("");
    const [loading, setLoading] = useState(false);

    function switchMode(nextMode) {
        setMode(nextMode);
        setError("");
        setSuccess("");
        setPassword("");
        setConfirmPassword("");
        setShowPassword(false);
    }

    async function handleSubmit(event) {
        event.preventDefault();
        setError("");
        setSuccess("");

        const cleanPrincipalId = principalId.trim();

        if (mode === "register") {
            if (password.length < 12) {
                setError("Password must contain at least 12 characters.");
                return;
            }

            if (password !== confirmPassword) {
                setError("Passwords do not match.");
                return;
            }
        }

        setLoading(true);

        try {
            const endpoint =
                mode === "register"
                    ? "/api/v1/auth/register"
                    : "/api/v1/auth/login";

            const response = await fetch(
                `${API_BASE_URL}${endpoint}`,
                {
                    method: "POST",
                    credentials: "include",
                    headers: {
                        "Content-Type": "application/json",
                        Accept: "application/json",
                    },
                    body: JSON.stringify({
                        principal_id: cleanPrincipalId,
                        password,
                    }),
                }
            );

            const data = await response.json().catch(() => ({}));

            if (!response.ok) {
                throw new Error(
                    data.detail ||
                    (mode === "register"
                        ? "Account creation failed."
                        : "Login failed. Check your credentials.")
                );
            }

            if (mode === "register") {
                setSuccess(
                    "Account created successfully. Sign in with your new credentials."
                );
                setMode("login");
                setPassword("");
                setConfirmPassword("");
                return;
            }

            const sessionResponse = await fetch(
                `${API_BASE_URL}/api/v1/auth/me`,
                {
                    method: "GET",
                    credentials: "include",
                    headers: {
                        Accept: "application/json",
                    },
                }
            );

            const sessionData = await sessionResponse
                .json()
                .catch(() => ({}));

            if (!sessionResponse.ok) {
                throw new Error(
                    "Login succeeded, but the browser session could not be verified. Check browser cookie settings."
                );
            }

            onLogin(sessionData);
        } catch (err) {
            setError(
                err instanceof Error
                    ? err.message
                    : "Unable to connect to the authentication server."
            );
        } finally {
            setLoading(false);
        }
    }

    return (
        <main className="login-page">
            <section className="login-card">
                <div className="login-brand-icon">
                    <ShieldCheck size={30} />
                </div>

                <h1>Knowledge Copilot</h1>

                <p className="login-subtitle">
                    Enterprise Knowledge &amp; Compliance
                </p>

                <div className="login-heading">
                    {mode === "login" ? (
                        <LockKeyhole size={20} />
                    ) : (
                        <UserPlus size={20} />
                    )}
                    <h2>
                        {mode === "login"
                            ? "Welcome back"
                            : "Create your account"}
                    </h2>
                </div>

                <p className="login-description">
                    {mode === "login"
                        ? "Sign in with your employee account to continue."
                        : "Create a standard employee account to get started."}
                </p>

                <form onSubmit={handleSubmit}>
                    <label htmlFor="principalId">Employee ID</label>

                    <input
                        id="principalId"
                        name="principalId"
                        type="text"
                        autoComplete="username"
                        value={principalId}
                        onChange={(event) =>
                            setPrincipalId(event.target.value)
                        }
                        placeholder="Enter your employee ID"
                        required
                        minLength={mode === "register" ? 3 : 1}
                        maxLength={128}
                    />

                    <label htmlFor="password">Password</label>

                    <div className="login-password-field">
                        <input
                            id="password"
                            name="password"
                            type={showPassword ? "text" : "password"}
                            autoComplete={
                                mode === "login"
                                    ? "current-password"
                                    : "new-password"
                            }
                            value={password}
                            onChange={(event) =>
                                setPassword(event.target.value)
                            }
                            placeholder={
                                mode === "register"
                                    ? "At least 12 characters"
                                    : "Enter your password"
                            }
                            required
                            minLength={mode === "register" ? 12 : 1}
                            maxLength={1024}
                        />

                        <button
                            className="login-password-toggle"
                            type="button"
                            onClick={() =>
                                setShowPassword((value) => !value)
                            }
                            aria-label={
                                showPassword ? "Hide password" : "Show password"
                            }
                        >
                            {showPassword ? (
                                <EyeOff size={18} />
                            ) : (
                                <Eye size={18} />
                            )}
                        </button>
                    </div>

                    {mode === "register" && (
                        <>
                            <label htmlFor="confirmPassword">
                                Confirm password
                            </label>

                            <input
                                id="confirmPassword"
                                name="confirmPassword"
                                type={showPassword ? "text" : "password"}
                                autoComplete="new-password"
                                value={confirmPassword}
                                onChange={(event) =>
                                    setConfirmPassword(event.target.value)
                                }
                                placeholder="Re-enter your password"
                                required
                                minLength={12}
                                maxLength={1024}
                            />
                        </>
                    )}

                    {error && (
                        <div className="login-error" role="alert">
                            {error}
                        </div>
                    )}

                    {success && (
                        <div className="login-success" role="status">
                            {success}
                        </div>
                    )}

                    <button
                        className="login-submit"
                        type="submit"
                        disabled={loading}
                    >
                        {loading
                            ? "Please wait..."
                            : mode === "login"
                                ? "Sign in securely"
                                : "Create account"}
                    </button>
                </form>

                <p className="login-security-note">
                    <LockKeyhole size={14} />
                    Protected employee access
                </p>

                <p className="login-description">
                    {mode === "login"
                        ? "Don't have an account?"
                        : "Already have an account?"}{" "}
                    <button
                        type="button"
                        className="auth-mode-toggle"
                        onClick={() =>
                            switchMode(
                                mode === "login" ? "register" : "login"
                            )
                        }
                    >
                        {mode === "login"
                            ? "Create account"
                            : "Sign in"}
                    </button>
                </p>
            </section>
        </main>
    );
}
