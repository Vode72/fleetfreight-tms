import { useEffect, useId, useRef, useState, type SubmitEvent } from "react";
import { useTranslation } from "react-i18next";

import type { LoginResult } from "../../auth/authApi";
import { useAuth } from "../../auth/useAuth";
import { formatWait } from "./formatWait";

type Failure = Exclude<LoginResult, { ok: true }>;

function useFailureMessage(failure: Failure | null): string | null {
  const { t, i18n } = useTranslation();
  if (!failure) return null;
  switch (failure.reason) {
    case "invalid":
      return t("auth.errors.invalid");
    case "validation":
      return t("auth.errors.validation");
    case "network":
      return t("auth.errors.network");
    case "unexpected":
      return t("auth.errors.unexpected");
    case "rateLimited":
      return failure.retryAfterSeconds === null
        ? t("auth.errors.rateLimitedNoWait")
        : t("auth.errors.rateLimited", { wait: formatWait(failure.retryAfterSeconds, i18n.language) });
  }
}

/** Email + password form. On success the auth state changes and the login route redirects. */
export function LoginForm() {
  const { t } = useTranslation();
  const { login } = useAuth();
  const emailId = useId();
  const passwordId = useId();
  const alertId = useId();
  const emailRef = useRef<HTMLInputElement>(null);
  const passwordRef = useRef<HTMLInputElement>(null);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [failure, setFailure] = useState<Failure | null>(null);
  const message = useFailureMessage(failure);

  useEffect(() => {
    emailRef.current?.focus();
  }, []);

  async function handleSubmit(event: SubmitEvent<HTMLFormElement>) {
    event.preventDefault();
    if (submitting) return;
    if (email.trim() === "" || password === "") {
      setFailure({ ok: false, reason: "validation" });
      (email.trim() === "" ? emailRef : passwordRef).current?.focus();
      return;
    }
    setSubmitting(true);
    setFailure(null);
    const result = await login(email.trim(), password);
    if (result.ok) return; // the route redirects; this form unmounts
    setSubmitting(false);
    setFailure(result);
    if (result.reason === "invalid") {
      setPassword("");
      passwordRef.current?.focus();
    }
  }

  return (
    <form className="auth-form" onSubmit={(event) => void handleSubmit(event)} noValidate>
      <div className="auth-field">
        <label htmlFor={emailId}>{t("auth.login.email")}</label>
        <input
          ref={emailRef}
          id={emailId}
          type="email"
          name="email"
          autoComplete="username"
          value={email}
          onChange={(event) => {
            setEmail(event.target.value);
          }}
          aria-describedby={message ? alertId : undefined}
          aria-invalid={failure?.reason === "validation" && email.trim() === "" ? true : undefined}
        />
      </div>
      <div className="auth-field">
        <label htmlFor={passwordId}>{t("auth.login.password")}</label>
        <input
          ref={passwordRef}
          id={passwordId}
          type="password"
          name="password"
          autoComplete="current-password"
          value={password}
          onChange={(event) => {
            setPassword(event.target.value);
          }}
          aria-describedby={message ? alertId : undefined}
          aria-invalid={failure?.reason === "validation" && password === "" ? true : undefined}
        />
      </div>
      <div id={alertId} role="alert" className={message ? "auth-alert" : undefined}>
        {message}
      </div>
      <button type="submit" className="auth-submit" disabled={submitting} aria-busy={submitting}>
        {submitting ? t("auth.login.submitting") : t("auth.login.submit")}
      </button>
    </form>
  );
}
