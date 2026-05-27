import { useEffect, useMemo, useRef, useState } from "react";
import { Search, Loader2 } from "lucide-react";
import { searchStocks, ApiError } from "../services/api";
import type { SearchResult } from "../types";

interface Props {
  onSelect: (result: SearchResult) => void;
}

interface SearchState {
  status: "idle" | "loading" | "ready" | "error";
  results: SearchResult[];
  error?: string;
  source?: "live" | "mock";
}

const MIN_QUERY_LENGTH = 2;

export function SearchBar({ onSelect }: Props) {
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const [state, setState] = useState<SearchState>({ status: "idle", results: [] });
  const containerRef = useRef<HTMLDivElement | null>(null);

  const trimmed = useMemo(() => query.trim(), [query]);

  useEffect(() => {
    if (trimmed.length < MIN_QUERY_LENGTH) {
      setState({ status: "idle", results: [] });
      return;
    }
    const controller = new AbortController();
    setState((prev) => ({ ...prev, status: "loading" }));
    const handle = window.setTimeout(async () => {
      try {
        const payload = await searchStocks(trimmed, controller.signal);
        setState({
          status: "ready",
          results: payload.results,
          source: payload.source,
        });
      } catch (error) {
        if (controller.signal.aborted) {
          return;
        }
        const message = error instanceof ApiError ? error.message : "검색 중 오류가 발생했습니다.";
        setState({ status: "error", results: [], error: message });
      }
    }, 280);
    return () => {
      controller.abort();
      window.clearTimeout(handle);
    };
  }, [trimmed]);

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (!containerRef.current) return;
      if (!containerRef.current.contains(event.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const handleSelect = (result: SearchResult) => {
    setQuery(result.symbol);
    setOpen(false);
    onSelect(result);
  };

  const showDropdown = open && trimmed.length >= MIN_QUERY_LENGTH;

  return (
    <div className="search-shell" ref={containerRef}>
      <div className="search-box">
        <Search size={18} color="rgba(232,236,255,0.6)" />
        <input
          type="text"
          value={query}
          onChange={(event) => {
            setQuery(event.target.value);
            setOpen(true);
          }}
          onFocus={() => setOpen(true)}
          placeholder="티커 또는 회사명을 입력하세요 (예: AAPL, Samsung)"
          aria-label="종목 검색"
          maxLength={80}
        />
        {state.status === "loading" && (
          <Loader2 size={16} color="var(--accent-cyan)" className="spinner" />
        )}
      </div>
      {showDropdown && (
        <div className="search-dropdown" role="listbox">
          {state.status === "loading" && state.results.length === 0 && (
            <div className="search-empty">검색 중…</div>
          )}
          {state.status === "error" && (
            <div className="search-empty">{state.error}</div>
          )}
          {state.status === "ready" && state.results.length === 0 && (
            <div className="search-empty">검색 결과가 없습니다.</div>
          )}
          {state.results.map((result) => (
            <button
              key={`${result.symbol}-${result.exchange}`}
              className="search-result"
              role="option"
              onClick={() => handleSelect(result)}
              type="button"
            >
              <div>
                <div className="symbol">{result.symbol}</div>
                <div style={{ fontSize: 13, color: "var(--text-secondary)" }}>{result.name}</div>
              </div>
              <div className="meta">
                <div>{result.exchange}</div>
                <div>{result.market} · {result.currency}</div>
              </div>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
