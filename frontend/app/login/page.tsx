"use client";

import { FormEvent, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Activity, ArrowRight, Eye, EyeOff, LockKeyhole, Monitor } from "lucide-react";

import BrandMark from "@/components/BrandMark";
import LanguageSwitcher from "@/components/LanguageSwitcher";
import { API_BASE } from "@/lib/api";
import { useBranding } from "@/lib/branding";
import { STORAGE_KEYS } from "@/lib/constants";
import { useI18n } from "@/lib/i18n";

export default function LoginPage() {
  const router = useRouter();
  const { branding } = useBranding();
  const { t, language } = useI18n();
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (localStorage.getItem(STORAGE_KEYS.token)) router.replace("/admin");
  }, [router]);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setLoading(true);
    setError("");
    const form = new FormData(event.currentTarget);
    try {
      const response = await fetch(`${API_BASE}/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-Language": language },
        body: JSON.stringify({ username: form.get("username"), password: form.get("password") }),
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) {
        const detail = Array.isArray(data.detail) ? data.detail.map((item: { msg?: string }) => item.msg).join("; ") : data.detail;
        throw new Error(typeof detail === "string" && detail ? detail : t("login.error"));
      }
      localStorage.setItem(STORAGE_KEYS.token, data.access_token);
      localStorage.setItem(STORAGE_KEYS.user, data.username);
      localStorage.setItem(STORAGE_KEYS.role, data.role);
      router.push("/admin");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : t("login.error"));
    } finally {
      setLoading(false);
    }
  }

  const headline = branding?.login_headline || t("login.headline");
  const message = branding?.login_message || t("login.message");

  return (
    <main className="login-page">
      <section className="login-brand-panel">
        <BrandMark variant="login" />
        <div className="login-message">
          <p className="eyebrow">{t("login.eyebrow")}</p>
          <h1>
            {headline.split("\n").map((line, index) => (
              <span key={index}>{index > 0 && <br />}{line}</span>
            ))}
          </h1>
          <p>{message}</p>
          <div className="network-visual">
            <div className="pulse-core"><Activity /></div>
            <span className="orbit orbit-one"><Monitor size={18} /></span>
            <span className="orbit orbit-two"><Monitor size={18} /></span>
            <span className="orbit orbit-three"><Monitor size={18} /></span>
          </div>
        </div>
        <p className="login-caption">{t("login.caption")}</p>
      </section>
      <section className="login-form-panel">
        <div className="login-language"><LanguageSwitcher /></div>
        <form onSubmit={submit} className="login-card">
          <div className="login-mobile-brand"><BrandMark variant="public" /></div>
          <div className="login-icon"><LockKeyhole /></div>
          <h2>{t("login.title")}</h2>
          <p>{t("login.subtitle")}</p>
          <label>
            {t("login.username")}
            <input name="username" autoComplete="username" placeholder={t("login.usernamePlaceholder")} required />
          </label>
          <label>
            {t("login.password")}
            <div className="password-field">
              <input
                name="password"
                type={showPassword ? "text" : "password"}
                autoComplete="current-password"
                placeholder={t("login.passwordPlaceholder")}
                minLength={8}
                required
              />
              <button type="button" onClick={() => setShowPassword(!showPassword)} aria-label={t("login.togglePassword")}>
                {showPassword ? <EyeOff /> : <Eye />}
              </button>
            </div>
          </label>
          {error && <div className="form-error" role="alert">{error}</div>}
          <button className="primary-button login-submit" disabled={loading}>
            {loading ? <><span className="spinner" /> {t("login.submitting")}</> : <>{t("login.submit")} <ArrowRight size={19} /></>}
          </button>
          <small>{t("login.restricted")}</small>
        </form>
      </section>
    </main>
  );
}
