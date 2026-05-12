import { useState, useCallback, useRef, useEffect } from "react";
import { searchInventory, type FlexElement } from "@/api/client";

interface Props {
  onSelect: (item: FlexElement) => void;
  placeholder?: string;
}

export function InventorySearch({ onSelect, placeholder = "Search current inventory…" }: Props) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<FlexElement[]>([]);
  const [loading, setLoading] = useState(false);
  const [open, setOpen] = useState(false);
  const debounceRef = useRef<ReturnType<typeof setTimeout>>();
  const containerRef = useRef<HTMLDivElement>(null);

  const search = useCallback(async (q: string) => {
    if (q.length < 2) { setResults([]); return; }
    setLoading(true);
    try {
      const items = await searchInventory(q);
      setResults(items);
      setOpen(true);
    } catch {
      setResults([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => search(query), 300);
    return () => clearTimeout(debounceRef.current);
  }, [query, search]);

  // Close on outside click
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (!containerRef.current?.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  return (
    <div ref={containerRef} className="relative w-full">
      <input
        className="w-full bg-surface border border-surface-border rounded px-3 py-1.5 text-sm text-slate-200 placeholder-slate-500 focus:outline-none focus:border-sky-500"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        onFocus={() => results.length > 0 && setOpen(true)}
        placeholder={placeholder}
      />
      {loading && (
        <div className="absolute right-2 top-1/2 -translate-y-1/2 text-slate-500 text-xs">…</div>
      )}
      {open && results.length > 0 && (
        <div className="absolute z-50 mt-1 w-full max-h-56 overflow-y-auto bg-surface-card border border-surface-border rounded shadow-lg">
          {results.map((item) => (
            <button
              key={item.id}
              className="w-full text-left px-3 py-2 text-sm hover:bg-surface-border transition-colors"
              onMouseDown={() => {
                onSelect(item);
                setQuery(item.name ?? "");
                setOpen(false);
              }}
            >
              <span className="text-slate-200">{item.name}</span>
              {item.elementTypeName && (
                <span className="ml-2 text-xs text-slate-500">{item.elementTypeName}</span>
              )}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
