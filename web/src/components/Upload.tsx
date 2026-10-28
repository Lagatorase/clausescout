import { useState } from "react";

interface Props {
  supported: string[];
  onUpload: (files: File[]) => Promise<void>;
}

export default function Upload({ supported, onUpload }: Props) {
  const [over, setOver] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function send(list: FileList | null) {
    if (!list || list.length === 0) return;
    setBusy(true);
    setError(null);
    try {
      await onUpload([...list]);
    } catch (e) {
      setError((e as Error).message);
      setBusy(false);
    }
  }

  return (
    <div className="upload">
      <h1>Review a contract pack</h1>
      <p className="muted">
        ClauseScout finds the 41 CUAD clause types, quotes each one word for word with its page
        or paragraph, and flags risks against your playbook. Files stay on this computer.
      </p>
      <div
        className={"drop" + (over ? " over" : "")}
        onDragOver={(e) => {
          e.preventDefault();
          setOver(true);
        }}
        onDragLeave={() => setOver(false)}
        onDrop={(e) => {
          e.preventDefault();
          setOver(false);
          send(e.dataTransfer.files);
        }}
      >
        <p>Drop contracts here, or choose files</p>
        <input
          type="file"
          multiple
          aria-label="Choose contract files"
          accept={supported.join(",")}
          disabled={busy}
          onChange={(e) => send(e.target.files)}
        />
        <p className="muted">{supported.join(", ")} files. Scanned PDFs need OCR first.</p>
        {busy && <p>Uploading...</p>}
        {error && (
          <p className="error" role="alert">
            {error}
          </p>
        )}
      </div>
    </div>
  );
}
