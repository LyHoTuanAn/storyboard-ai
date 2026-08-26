import { useEffect, useRef, useState } from "react";

export function LogView({ lines }: { lines: string[] }) {
  const [follow, setFollow] = useState(true);
  const boxRef = useRef<HTMLDivElement>(null);

  // Dat scrollTop cua chinh khung nhat ky, KHONG dung scrollIntoView:
  // scrollIntoView cuon moi phan tu to hon dang chua no, ke ca ca trang -
  // nen moi dong log moi lai giat trang ve phia khung nhat ky trong khi
  // nguoi dung dang doc cho khac.
  useEffect(() => {
    if (!follow) return;
    const box = boxRef.current;
    if (box) box.scrollTop = box.scrollHeight;
  }, [lines, follow]);

  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold">Nhat ky</h3>
        <label className="flex items-center gap-2 text-xs" htmlFor="follow">
          <input
            id="follow"
            type="checkbox"
            checked={follow}
            onChange={(event) => setFollow(event.target.checked)}
          />
          Tu cuon
        </label>
      </div>
      <div
        ref={boxRef}
        className="mono h-72 overflow-auto px-3 py-2 text-xs leading-relaxed"
        style={{
          background: "var(--surface)",
          border: "1px solid var(--border)",
          borderRadius: "var(--radius)",
          color: "var(--text-dim)",
        }}
      >
        {lines.map((line, index) => (
          <div key={index} className="whitespace-pre-wrap">
            {line}
          </div>
        ))}
      </div>
    </div>
  );
}
