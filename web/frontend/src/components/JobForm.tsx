import { useState } from "react";
import { EyeIcon, EyeSlashIcon, PlayIcon } from "@phosphor-icons/react";
import { createJob } from "../api";
import { Field } from "./Field";

const inputStyle = {
  background: "var(--surface)",
  border: "1px solid var(--border)",
  borderRadius: "var(--radius)",
  color: "var(--text)",
};

export function JobForm({ onCreated }: { onCreated: (id: string) => void }) {
  const [context, setContext] = useState("");
  const [language, setLanguage] = useState("vietnamese");
  const [researchMode, setResearchMode] = useState<"deep" | "web" | "none">("web");
  const [fastMode, setFastMode] = useState(true);
  const [useImageSearch, setUseImageSearch] = useState(true);
  const [enableVeo, setEnableVeo] = useState(false);
  const [apiKey, setApiKey] = useState("");
  const [showKey, setShowKey] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setError(null);
    if (!context.trim()) {
      setError("Nhap chu de truoc khi chay");
      return;
    }
    setBusy(true);
    try {
      const { id } = await createJob({
        params: {
          context: context.trim(),
          language,
          research_mode: researchMode,
          use_internet_image_search: useImageSearch,
          fast_mode: fastMode,
          enable_veo: enableVeo,
          veo_direction_by_director: false,
        },
        ...(apiKey ? { api_key: apiKey } : {}),
      });
      setContext("");
      onCreated(id);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Khong tao duoc job");
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} className="flex flex-col gap-5">
      <Field label="Chu de video" htmlFor="context" error={error}>
        <textarea
          id="context"
          rows={3}
          value={context}
          onChange={(event) => setContext(event.target.value)}
          className="w-full px-3 py-2 text-sm"
          style={inputStyle}
        />
      </Field>

      <Field label="Ngon ngu loi thoai" htmlFor="language">
        <input
          id="language"
          value={language}
          onChange={(event) => setLanguage(event.target.value)}
          className="w-full px-3 py-2 text-sm"
          style={inputStyle}
        />
      </Field>

      <Field label="Che do nghien cuu" htmlFor="research">
        <select
          id="research"
          value={researchMode}
          onChange={(event) => setResearchMode(event.target.value as "deep" | "web" | "none")}
          className="w-full px-3 py-2 text-sm"
          style={inputStyle}
        >
          <option value="web">Web search (nhanh)</option>
          <option value="deep">Deep research (cham, ky)</option>
          <option value="none">Bo qua</option>
        </select>
      </Field>

      <fieldset className="flex flex-col gap-3">
        <legend className="text-sm font-medium">Tuy chon</legend>
        {[
          { id: "fast", label: "Fast mode (sinh song song)", value: fastMode, set: setFastMode },
          { id: "imgsearch", label: "Tim anh tham chieu tren mang", value: useImageSearch, set: setUseImageSearch },
          { id: "veo", label: "Bat Veo (tra phi)", value: enableVeo, set: setEnableVeo },
        ].map((item) => (
          <label key={item.id} htmlFor={item.id} className="flex items-center gap-2 text-sm">
            <input
              id={item.id}
              type="checkbox"
              checked={item.value}
              onChange={(event) => item.set(event.target.checked)}
            />
            {item.label}
          </label>
        ))}
      </fieldset>

      <Field
        label="API key rieng (tuy chon)"
        htmlFor="apikey"
        hint="De trong thi dung key trong .env. Key chi duoc truyen cho tien trinh chay job, khong luu lai."
      >
        <div className="flex gap-2">
          <input
            id="apikey"
            type={showKey ? "text" : "password"}
            value={apiKey}
            onChange={(event) => setApiKey(event.target.value)}
            className="mono w-full px-3 py-2 text-sm"
            style={inputStyle}
            autoComplete="new-password"
            autoCorrect="off"
            spellCheck={false}
          />
          <button
            type="button"
            onClick={() => setShowKey(!showKey)}
            className="px-3 transition-transform active:scale-[0.98]"
            style={inputStyle}
            aria-label={showKey ? "An key" : "Hien key"}
          >
            {showKey ? <EyeSlashIcon size={16} /> : <EyeIcon size={16} />}
          </button>
        </div>
      </Field>

      <button
        type="submit"
        disabled={busy}
        className="flex items-center justify-center gap-2 px-4 py-2.5 text-sm font-medium transition-transform active:scale-[0.98] disabled:opacity-60"
        style={{ background: "var(--accent)", color: "var(--bg)", borderRadius: "var(--radius)" }}
      >
        <PlayIcon size={16} weight="fill" />
        {busy ? "Dang tao..." : "Chay"}
      </button>
    </form>
  );
}
