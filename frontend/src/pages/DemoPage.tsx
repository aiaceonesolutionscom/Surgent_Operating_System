import React, { useState } from "react";
import { Link } from "react-router-dom";
import { ArrowLeftIcon, ClockIcon, CheckCircle2Icon, Loader2Icon, StethoscopeIcon, ShieldIcon, UsersIcon, ZapIcon } from "lucide-react";
import { Navbar, Footer } from "../components/layout";
import { Container } from "../components/ui";
import { submitDemoRequest } from "../api/commerce";
import { ApiError } from "../api/client";

export function DemoPage() {
  const [submitted, setSubmitted] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [form, setForm] = useState({
    name: "",
    email: "",
    phone: "",
    practiceName: "",
    practiceType: "",
    monthlyLeads: "",
    currentSoftware: "",
    message: ""
  });

  const update = (field: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) =>
  setForm((f) => ({ ...f, [field]: e.target.value }));

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await submitDemoRequest({
        name: form.name,
        email: form.email,
        phone: form.phone || undefined,
        practice_name: form.practiceName || undefined,
        message: form.message || `Practice Type: ${form.practiceType}\nMonthly Leads: ${form.monthlyLeads}\nCurrent Software: ${form.currentSoftware}`
      });
      setSubmitted(true);
    } catch (err) {
      setError(
        err instanceof ApiError ?
        "We couldn't submit your request right now — please try again in a moment." :
        "Something went wrong. Please try again."
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen w-full bg-canvas font-sans text-ink">
      <Navbar />
      <main className="pt-28 pb-24">
        <Container>
          <Link
            to="/"
            className="inline-flex items-center gap-1.5 text-sm font-medium text-ink-soft transition-colors hover:text-teal-600">

            <ArrowLeftIcon className="h-4 w-4" />
            Back to home
          </Link>

          <div className="mt-10 grid gap-12 lg:grid-cols-[380px_1fr] lg:items-start">
            {/* Avatar + guidance */}
            <div className="flex flex-col items-center text-center lg:sticky lg:top-28">
              <div className="flex h-32 w-32 items-center justify-center rounded-full border-4 border-white bg-teal-600 shadow-lift">
                <StethoscopeIcon className="h-12 w-12 text-white" />
              </div>
              <p className="mt-5 font-display text-xl font-600 text-ink">
                Tell us about your practice
              </p>
              <p className="mt-2 max-w-xs text-sm text-ink-soft">
                Fill out the form and our team will reach out within 24 hours to walk you through exactly how Aiaceone's AI agents would work for your clinic.
              </p>
              <div className="mt-5 flex items-center gap-2 rounded-full bg-teal-50 px-4 py-2 text-sm font-semibold text-teal-700">
                <ClockIcon className="h-4 w-4" />
                Guaranteed response within 24 hours
              </div>
              
              {/* Trust indicators */}
              <div className="mt-8 grid grid-cols-3 gap-4 text-center">
                <div className="rounded-xl bg-white p-4 border border-sand-200">
                  <ShieldIcon className="h-6 w-6 mx-auto text-teal-600" />
                  <p className="mt-2 text-xs font-semibold text-ink">HIPAA Compliant</p>
                  <p className="text-[10px] text-ink-muted">Enterprise security</p>
                </div>
                <div className="rounded-xl bg-white p-4 border border-sand-200">
                  <UsersIcon className="h-6 w-6 mx-auto text-teal-600" />
                  <p className="mt-2 text-xs font-semibold text-ink">9 AI Agents</p>
                  <p className="text-[10px] text-ink-muted">Full practice coverage</p>
                </div>
                <div className="rounded-xl bg-white p-4 border border-sand-200">
                  <ZapIcon className="h-6 w-6 mx-auto text-teal-600" />
                  <p className="mt-2 text-xs font-semibold text-ink">2× Faster</p>
                  <p className="text-[10px] text-ink-muted">Lead response time</p>
                </div>
              </div>
              
              <p className="mt-6 text-xs text-ink-muted">
                Aiaceone is built by <span className="font-semibold text-ink-soft">AceOne Solutions</span>.
              </p>
            </div>

            {/* Form */}
            <div className="rounded-4xl border border-sand-200 bg-white p-8 shadow-soft sm:p-10">
              {submitted ?
              <div className="flex flex-col items-center py-10 text-center">
                  <span className="flex h-14 w-14 items-center justify-center rounded-full bg-teal-50 text-teal-600">
                    <CheckCircle2Icon className="h-7 w-7" />
                  </span>
                  <p className="mt-4 font-display text-2xl font-600 text-ink">You're all set</p>
                  <p className="mt-2 max-w-sm text-sm text-ink-soft">
                    We've got your request — check your inbox for a confirmation. Our
                    team will be in touch within 24 hours.
                  </p>
                </div> :

              <form onSubmit={submit} className="space-y-6">
                  {/* Section 1: Personal Info */}
                  <fieldset className="space-y-5">
                    <legend className="flex items-center gap-2 text-sm font-semibold uppercase tracking-wide text-ink-muted">
                      <StethoscopeIcon className="h-4 w-4 text-teal-600" />
                      Your Details
                    </legend>
                    <div className="grid gap-5 sm:grid-cols-2">
                      <Field label="Full name" required value={form.name} onChange={update("name")} placeholder="Dr. Jane Vance" />
                      <Field label="Work email" type="email" required value={form.email} onChange={update("email")} placeholder="you@practice.com" />
                    </div>
                    <div className="grid gap-5 sm:grid-cols-2">
                      <Field label="Phone" value={form.phone} onChange={update("phone")} placeholder="(555) 123-4567" />
                      <Field label="Practice name" required value={form.practiceName} onChange={update("practiceName")} placeholder="Meridian Plastic Surgery" />
                    </div>
                  </fieldset>

                  {/* Section 2: Practice Details */}
                  <fieldset className="space-y-5 pt-4 border-t border-sand-200">
                    <legend className="flex items-center gap-2 text-sm font-semibold uppercase tracking-wide text-ink-muted">
                      <UsersIcon className="h-4 w-4 text-teal-600" />
                      Practice Details
                    </legend>
                    <div className="grid gap-5 sm:grid-cols-2">
                      <SelectField
                        label="Practice type"
                        required
                        value={form.practiceType}
                        onChange={update("practiceType")}
                        options={[
                          { value: "", label: "Select practice type" },
                          { value: "plastic_surgery", label: "Plastic Surgery" },
                          { value: "medical_spa", label: "Medical Spa / Aesthetics" },
                          { value: "dermatology", label: "Dermatology" },
                          { value: "multi_specialty", label: "Multi-specialty Clinic" },
                          { value: "other", label: "Other" }
                        ]}
                      />
                      <SelectField
                        label="Monthly new leads"
                        value={form.monthlyLeads}
                        onChange={update("monthlyLeads")}
                        options={[
                          { value: "", label: "Select range" },
                          { value: "0-25", label: "0-25 leads/month" },
                          { value: "26-50", label: "26-50 leads/month" },
                          { value: "51-100", label: "51-100 leads/month" },
                          { value: "100+", label: "100+ leads/month" }
                        ]}
                      />
                    </div>
                    <SelectField
                      label="Current practice software"
                      value={form.currentSoftware}
                      onChange={update("currentSoftware")}
                      options={[
                        { value: "", label: "Select current software" },
                        { value: "nextech", label: "Nextech" },
                        { value: "symplast", label: "Symplast" },
                        { value: "patientnow", label: "PatientNow" },
                        { value: "athenanet", label: "athenahealth" },
                        { value: "paper_charts", label: "Paper charts / Spreadsheets" },
                        { value: "other", label: "Other / None" }
                      ]}
                    />
                  </fieldset>

                  {/* Section 3: Message */}
                  <fieldset className="space-y-3 pt-4 border-t border-sand-200">
                    <legend className="flex items-center gap-2 text-sm font-semibold uppercase tracking-wide text-ink-muted">
                      <ZapIcon className="h-4 w-4 text-teal-600" />
                      What would you like us to walk through? (optional)
                    </legend>
                    <textarea
                      value={form.message}
                      onChange={update("message")}
                      rows={4}
                      placeholder="e.g. how the receptionist agent handles after-hours calls, lead qualification for rhinoplasty enquiries, or post-op recovery automation"
                      className="w-full resize-none rounded-xl border border-sand-200 px-3.5 py-2.5 text-sm text-ink outline-none transition-colors focus:border-teal-400" />
                  </fieldset>

                  {error && <p className="text-sm text-red-600">{error}</p>}

                  <button
                  type="submit"
                  disabled={loading}
                  className="flex w-full items-center justify-center gap-2 rounded-full bg-ink py-3.5 text-sm font-semibold text-white transition-colors hover:bg-teal-700 disabled:opacity-60 sm:w-auto sm:px-10">

                    {loading && <Loader2Icon className="h-4 w-4 animate-spin" />}
                    {loading ? "Submitting…" : "Book my demo"}
                  </button>
                </form>
              }
            </div>
          </div>
        </Container>
      </main>
      <Footer />
    </div>);

}

function Field({
  label,
  type = "text",
  required,
  value,
  onChange,
  placeholder


}: {label: string;type?: string;required?: boolean;value: string;onChange: (e: React.ChangeEvent<HTMLInputElement>) => void;placeholder?: string;}) {
  return (
    <label className="block text-sm font-medium text-ink-soft">
      {label}{required && <span className="text-teal-600"> *</span>}
      <input
        type={type}
        required={required}
        value={value}
        onChange={onChange}
        placeholder={placeholder}
        className="mt-1.5 w-full rounded-xl border border-sand-200 px-3.5 py-2.5 text-sm text-ink outline-none transition-colors focus:border-teal-400" />

    </label>);
}

function SelectField({
  label,
  required,
  value,
  onChange,
  options


}: {label: string;required?: boolean;value: string;onChange: (e: React.ChangeEvent<HTMLSelectElement>) => void;options: {value: string; label: string}[];}) {
  return (
    <label className="block text-sm font-medium text-ink-soft">
      {label}{required && <span className="text-teal-600"> *</span>}
      <select
        required={required}
        value={value}
        onChange={onChange}
        className="mt-1.5 w-full rounded-xl border border-sand-200 px-3.5 py-2.5 text-sm text-ink outline-none transition-colors focus:border-teal-400 bg-white">
        {options.map((opt) => (
          <option key={opt.value} value={opt.value}>
            {opt.label}
          </option>
        ))}
      </select>

    </label>);
}