"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { motion } from "framer-motion";
import { ShieldCheck, ArrowRight, Mail, Lock, Eye, EyeOff, User, Building2, ArrowLeft, KeyRound, Briefcase } from "lucide-react";
import {
  authLoginStart, authLoginVerify,
  authSignupStart, authSignupVerify,
  authResendOtp, setStoredEmployeeId,
  fetchWorkspaces,
} from "@/lib/api";

type WorkspaceOption = {
  workspace_id: string;
  name: string;
  description: string | null;
};

type Mode = "login" | "signup";
type Stage = "credentials" | "otp";

type OtpState = {
  email: string;
  purpose: "signup" | "login";
  expiresIn: number;
};

export default function LoginPage() {
  const router = useRouter();

  const [mode, setMode] = useState<Mode>("login");
  const [stage, setStage] = useState<Stage>("credentials");

  // Shared
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);

  // Signup-only
  const [name, setName] = useState("");
  const [designation, setDesignation] = useState("");
  const [department, setDepartment] = useState("");
  const [workspaceId, setWorkspaceId] = useState("");
  const [workspaces, setWorkspaces] = useState<WorkspaceOption[]>([]);

  // Fetch available workspaces once (public list for demo purposes)
  useEffect(() => {
    fetchWorkspaces()
      .then((list) => setWorkspaces(list.map((w: { workspace_id: string; name: string; description: string | null }) => ({
        workspace_id: w.workspace_id,
        name: w.name,
        description: w.description,
      }))))
      .catch(() => setWorkspaces([]));
  }, []);

  // OTP stage
  const [code, setCode] = useState("");
  const [otpState, setOtpState] = useState<OtpState | null>(null);

  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  function switchMode(next: Mode) {
    setMode(next);
    setStage("credentials");
    setCode("");
    setOtpState(null);
    setError(null);
  }

  async function handleCredentials(e?: React.FormEvent) {
    if (e) e.preventDefault();
    if (!email.trim() || !password) {
      setError("Enter email and password");
      return;
    }
    if (mode === "signup" && !name.trim()) {
      setError("Enter your name");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const resp = mode === "login"
        ? await authLoginStart(email.trim(), password)
        : await authSignupStart(
            email.trim(), name.trim(), password,
            designation || undefined, department || undefined,
            workspaceId || undefined,
          );
      setOtpState({
        email: resp.email,
        purpose: resp.purpose,
        expiresIn: resp.expires_in_minutes,
      });
      setStage("otp");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Request failed");
    } finally {
      setBusy(false);
    }
  }

  async function handleOtpVerify(e?: React.FormEvent) {
    if (e) e.preventDefault();
    if (!otpState) return;
    if (code.trim().length < 4) {
      setError("Enter the code");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const profile = otpState.purpose === "login"
        ? await authLoginVerify(otpState.email, code.trim())
        : await authSignupVerify(otpState.email, code.trim());
      setStoredEmployeeId(profile.employee_id);
      router.replace("/");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Verification failed");
      setBusy(false);
    }
  }

  async function handleResendOtp() {
    if (!otpState) return;
    setBusy(true);
    setError(null);
    try {
      const resp = await authResendOtp(otpState.email, otpState.purpose);
      setOtpState({
        ...otpState,
        expiresIn: resp.expires_in_minutes,
      });
      setCode("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Resend failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-ks-bg p-6">
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        className="w-full max-w-md"
      >
        {/* Brand */}
        <div className="flex items-center justify-center gap-2.5 mb-10">
          <div className="w-9 h-9 rounded-lg bg-ks-primary flex items-center justify-center text-white font-bold shadow-[0_0_20px_rgba(79,70,229,0.4)]">
            K
          </div>
          <span className="text-xl font-semibold text-ks-text tracking-tight">Action Marshall</span>
        </div>

        {stage === "credentials" && (
          <CredentialsCard
            mode={mode}
            email={email} setEmail={setEmail}
            password={password} setPassword={setPassword}
            showPassword={showPassword} setShowPassword={setShowPassword}
            name={name} setName={setName}
            designation={designation} setDesignation={setDesignation}
            department={department} setDepartment={setDepartment}
            workspaceId={workspaceId} setWorkspaceId={setWorkspaceId}
            workspaces={workspaces}
            error={error}
            busy={busy}
            onSubmit={handleCredentials}
            onSwitchMode={() => switchMode(mode === "login" ? "signup" : "login")}
          />
        )}

        {stage === "otp" && otpState && (
          <OtpCard
            email={otpState.email}
            purpose={otpState.purpose}
            expiresIn={otpState.expiresIn}
            code={code} setCode={setCode}
            error={error}
            busy={busy}
            onSubmit={handleOtpVerify}
            onResend={handleResendOtp}
            onBack={() => { setStage("credentials"); setCode(""); setError(null); }}
          />
        )}

        <p className="text-center text-[11px] text-ks-text3 mt-6">
          Protected by rate limits and 2FA · OTP delivered via email (or backend console in dev).
        </p>
      </motion.div>
    </div>
  );
}

// ── Credentials screen (login + signup) ─────────────────────────
function CredentialsCard({
  mode, email, setEmail, password, setPassword, showPassword, setShowPassword,
  name, setName, designation, setDesignation, department, setDepartment,
  workspaceId, setWorkspaceId, workspaces,
  error, busy, onSubmit, onSwitchMode,
}: {
  mode: Mode;
  email: string; setEmail: (v: string) => void;
  password: string; setPassword: (v: string) => void;
  showPassword: boolean; setShowPassword: (v: boolean) => void;
  name: string; setName: (v: string) => void;
  designation: string; setDesignation: (v: string) => void;
  department: string; setDepartment: (v: string) => void;
  workspaceId: string; setWorkspaceId: (v: string) => void;
  workspaces: WorkspaceOption[];
  error: string | null;
  busy: boolean;
  onSubmit: (e?: React.FormEvent) => void;
  onSwitchMode: () => void;
}) {
  return (
    <form
      onSubmit={onSubmit}
      className="bg-ks-surface border border-ks-border rounded-2xl shadow-lg p-8"
    >
      <div className="mb-6">
        <div className="flex items-center gap-2 mb-2">
          <ShieldCheck className="w-5 h-5 text-ks-primary" />
          <h1 className="text-lg font-semibold text-ks-text">
            {mode === "login" ? "Sign in" : "Create account"}
          </h1>
        </div>
        <p className="text-[13px] text-ks-text2 leading-relaxed">
          {mode === "login"
            ? "Enter your work email and password. We'll send a one-time code to verify."
            : "Register for Action Marshall with your work email. You'll verify with a one-time code."}
        </p>
      </div>

      {error && (
        <div className="rounded-lg border border-red-500/30 bg-red-500/5 p-3 text-xs text-red-500 mb-4">
          {error}
        </div>
      )}

      <div className="space-y-3">
        {mode === "signup" && (
          <>
            <Field label="Full name" icon={User}>
              <input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="Alex Taylor"
                autoComplete="name"
                className="w-full bg-ks-surface-2 border border-ks-border rounded-lg text-sm text-ks-text pl-9 pr-3 py-2.5 outline-none focus:border-ks-primary transition-colors placeholder:text-ks-text3"
              />
            </Field>
            <div className="grid grid-cols-2 gap-2">
              <Field label="Designation" icon={Building2}>
                <input
                  type="text"
                  value={designation}
                  onChange={(e) => setDesignation(e.target.value)}
                  placeholder="Platform Engineer"
                  className="w-full bg-ks-surface-2 border border-ks-border rounded-lg text-sm text-ks-text pl-9 pr-3 py-2.5 outline-none focus:border-ks-primary transition-colors placeholder:text-ks-text3"
                />
              </Field>
              <Field label="Department" icon={Building2}>
                <input
                  type="text"
                  value={department}
                  onChange={(e) => setDepartment(e.target.value)}
                  placeholder="Engineering"
                  className="w-full bg-ks-surface-2 border border-ks-border rounded-lg text-sm text-ks-text pl-9 pr-3 py-2.5 outline-none focus:border-ks-primary transition-colors placeholder:text-ks-text3"
                />
              </Field>
            </div>

            {workspaces.length > 0 && (
              <Field label="Request access to workspace (optional)" icon={Briefcase}>
                <select
                  value={workspaceId}
                  onChange={(e) => setWorkspaceId(e.target.value)}
                  className="w-full bg-ks-surface-2 border border-ks-border rounded-lg text-sm text-ks-text pl-9 pr-3 py-2.5 outline-none focus:border-ks-primary transition-colors appearance-none cursor-pointer"
                >
                  <option value="">No workspace — request later</option>
                  {workspaces.map((w) => (
                    <option key={w.workspace_id} value={w.workspace_id}>{w.name}</option>
                  ))}
                </select>
              </Field>
            )}
            <p className="text-[11px] text-ks-text3 leading-snug -mt-1">
              An admin of the chosen workspace will review your request. Until approved, you'll only see your own profile.
            </p>
          </>
        )}

        <Field label="Work email" icon={Mail}>
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="you@company.com"
            autoComplete="email"
            className="w-full bg-ks-surface-2 border border-ks-border rounded-lg text-sm text-ks-text pl-9 pr-3 py-2.5 outline-none focus:border-ks-primary transition-colors placeholder:text-ks-text3"
          />
        </Field>

        <Field label="Password" icon={Lock}>
          <input
            type={showPassword ? "text" : "password"}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder={mode === "signup" ? "At least 6 characters" : "••••••••"}
            autoComplete={mode === "login" ? "current-password" : "new-password"}
            minLength={mode === "signup" ? 6 : undefined}
            className="w-full bg-ks-surface-2 border border-ks-border rounded-lg text-sm text-ks-text pl-9 pr-10 py-2.5 outline-none focus:border-ks-primary transition-colors placeholder:text-ks-text3"
          />
          <button
            type="button"
            onClick={() => setShowPassword(!showPassword)}
            className="absolute right-2 top-[30px] p-1 text-ks-text3 hover:text-ks-text transition-colors"
          >
            {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
          </button>
        </Field>
      </div>

      <button
        type="submit"
        disabled={busy || !email || !password || (mode === "signup" && !name)}
        className="w-full mt-6 flex items-center justify-center gap-2 px-4 py-2.5 bg-ks-primary text-white rounded-lg text-sm font-semibold hover:opacity-90 transition-opacity disabled:opacity-50 shadow-[0_0_20px_rgba(79,70,229,0.3)]"
      >
        {busy ? "Sending code…" : (
          <>
            {mode === "login" ? "Continue" : "Create account"}
            <ArrowRight className="w-4 h-4" />
          </>
        )}
      </button>

      <button
        type="button"
        onClick={onSwitchMode}
        className="w-full mt-3 text-[12px] text-ks-text3 hover:text-ks-text2 transition-colors"
      >
        {mode === "login"
          ? "Don't have an account? Sign up"
          : "Already have an account? Sign in"}
      </button>
    </form>
  );
}

// ── OTP verification screen ─────────────────────────
function OtpCard({
  email, purpose, expiresIn, code, setCode, error, busy,
  onSubmit, onResend, onBack,
}: {
  email: string;
  purpose: "signup" | "login";
  expiresIn: number;
  code: string; setCode: (v: string) => void;
  error: string | null;
  busy: boolean;
  onSubmit: (e?: React.FormEvent) => void;
  onResend: () => void;
  onBack: () => void;
}) {
  return (
    <form
      onSubmit={onSubmit}
      className="bg-ks-surface border border-ks-border rounded-2xl shadow-lg p-8"
    >
      <button
        type="button"
        onClick={onBack}
        className="flex items-center gap-1.5 text-[11px] text-ks-text3 hover:text-ks-text mb-4 transition-colors"
      >
        <ArrowLeft className="w-3.5 h-3.5" />
        Back
      </button>

      <div className="mb-6">
        <div className="flex items-center gap-2 mb-2">
          <KeyRound className="w-5 h-5 text-ks-primary" />
          <h1 className="text-lg font-semibold text-ks-text">Check your email</h1>
        </div>
        <p className="text-[13px] text-ks-text2 leading-relaxed">
          We sent a 6-digit code to{" "}
          <span className="font-semibold text-ks-text">{email}</span>. It expires in {expiresIn} minutes.
        </p>
      </div>


      {error && (
        <div className="rounded-lg border border-red-500/30 bg-red-500/5 p-3 text-xs text-red-500 mb-4">
          {error}
        </div>
      )}

      <div>
        <label className="block text-[11px] font-semibold text-ks-text3 uppercase tracking-widest mb-1.5">
          Verification code
        </label>
        <input
          type="text"
          inputMode="numeric"
          pattern="[0-9]*"
          maxLength={6}
          value={code}
          onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))}
          placeholder="000000"
          autoFocus
          className="w-full bg-ks-surface-2 border border-ks-border rounded-lg text-xl font-mono font-bold tracking-[0.4em] text-center text-ks-text py-3 outline-none focus:border-ks-primary transition-colors placeholder:text-ks-text3"
        />
      </div>

      <button
        type="submit"
        disabled={busy || code.length < 6}
        className="w-full mt-4 flex items-center justify-center gap-2 px-4 py-2.5 bg-ks-primary text-white rounded-lg text-sm font-semibold hover:opacity-90 transition-opacity disabled:opacity-50 shadow-[0_0_20px_rgba(79,70,229,0.3)]"
      >
        {busy ? "Verifying…" : (
          <>
            {purpose === "signup" ? "Create account" : "Sign in"}
            <ArrowRight className="w-4 h-4" />
          </>
        )}
      </button>

      <button
        type="button"
        onClick={onResend}
        disabled={busy}
        className="w-full mt-3 text-[12px] text-ks-text3 hover:text-ks-text2 transition-colors disabled:opacity-50"
      >
        Didn't get a code? Send a new one
      </button>
    </form>
  );
}

function Field({
  label, icon: Icon, children,
}: {
  label: string;
  icon: React.ComponentType<{ className?: string }>;
  children: React.ReactNode;
}) {
  return (
    <div>
      <label className="block text-[11px] font-semibold text-ks-text3 uppercase tracking-widest mb-1.5">
        {label}
      </label>
      <div className="relative">
        <Icon className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-ks-text3" />
        {children}
      </div>
    </div>
  );
}
