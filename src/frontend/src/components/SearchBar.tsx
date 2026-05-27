import { Search, X } from 'lucide-react';
import { FormEvent, KeyboardEvent, useEffect, useMemo, useRef, useState } from 'react';
import { searchSymbols } from '../api';
import type { SearchResult } from '../types';

type SearchBarProps = {
  onSelect: (symbol: string) => void;
};

const RESULTS_PANEL_ID = 'search-suggestions';

export default function SearchBar({ onSelect }: SearchBarProps) {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<SearchResult[]>([]);
  const [isSearching, setIsSearching] = useState(false);
  const [isPanelOpen, setIsPanelOpen] = useState(false);
  const [activeIndex, setActiveIndex] = useState(-1);
  const [error, setError] = useState<string | null>(null);
  const trimmed = useMemo(() => query.trim(), [query]);
  const formRef = useRef<HTMLFormElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const activeIndexRef = useRef(-1);

  useEffect(() => {
    if (trimmed.length < 2) {
      closeSuggestions();
      setIsSearching(false);
      return;
    }

    const controller = new AbortController();
    let active = true;
    const timer = window.setTimeout(() => {
      setIsSearching(true);
      setIsPanelOpen(true);
      searchSymbols(trimmed, controller.signal)
        .then((payload) => {
          if (!active) {
            return;
          }
          setResults(payload);
          updateActiveIndex(-1);
          setError(null);
        })
        .catch((reason: Error) => {
          if (active && reason.name !== 'AbortError') {
            setError(reason.message);
            setResults([]);
            updateActiveIndex(-1);
          }
        })
        .finally(() => {
          if (active) {
            setIsSearching(false);
          }
        });
    }, 300);

    return () => {
      active = false;
      window.clearTimeout(timer);
      controller.abort();
    };
  }, [trimmed]);

  useEffect(() => {
    function handlePointerDown(event: MouseEvent) {
      if (!formRef.current?.contains(event.target as Node)) {
        closeSuggestions();
      }
    }

    document.addEventListener('mousedown', handlePointerDown);
    return () => document.removeEventListener('mousedown', handlePointerDown);
  }, []);

  function closeSuggestions() {
    setResults([]);
    setError(null);
    setIsPanelOpen(false);
    updateActiveIndex(-1);
  }

  function updateActiveIndex(nextIndex: number) {
    activeIndexRef.current = nextIndex;
    setActiveIndex(nextIndex);
  }

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (!trimmed) {
      setError('검색어를 입력해 주세요.');
      setIsPanelOpen(true);
      inputRef.current?.focus();
      return;
    }
    onSelect(trimmed);
    closeSuggestions();
  }

  function handlePick(symbol: string) {
    setQuery(symbol);
    closeSuggestions();
    onSelect(symbol);
  }

  function handleKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === 'Escape') {
      closeSuggestions();
      return;
    }

    if (event.key === 'ArrowDown' && results.length > 0) {
      event.preventDefault();
      setIsPanelOpen(true);
      updateActiveIndex((activeIndexRef.current + 1) % results.length);
      return;
    }

    if (event.key === 'ArrowUp' && results.length > 0) {
      event.preventDefault();
      setIsPanelOpen(true);
      updateActiveIndex(activeIndexRef.current <= 0 ? results.length - 1 : activeIndexRef.current - 1);
      return;
    }

    if (event.key === 'Enter' && isPanelOpen && activeIndexRef.current >= 0 && results[activeIndexRef.current]) {
      event.preventDefault();
      handlePick(results[activeIndexRef.current].symbol);
    }
  }

  function handleQueryChange(nextQuery: string) {
    setQuery(nextQuery);
    if (nextQuery.trim().length >= 2) {
      setIsPanelOpen(true);
    }
  }

  const activeResultId = activeIndex >= 0 ? `${RESULTS_PANEL_ID}-${activeIndex}` : undefined;

  return (
    <form className="searchBox" onSubmit={handleSubmit} role="search" ref={formRef}>
      <Search size={18} aria-hidden="true" />
      <input
        ref={inputRef}
        aria-activedescendant={activeResultId}
        aria-controls={RESULTS_PANEL_ID}
        aria-expanded={isPanelOpen}
        aria-label="종목 검색"
        autoComplete="off"
        placeholder="티커 또는 종목명 검색"
        value={query}
        maxLength={20}
        onChange={(event) => handleQueryChange(event.target.value)}
        onFocus={() => {
          if (trimmed.length >= 2) {
            setIsPanelOpen(true);
          }
        }}
        onKeyDown={handleKeyDown}
      />
      {query ? (
        <button type="button" className="iconButton" aria-label="검색어 지우기" onClick={() => setQuery('')}>
          <X size={16} />
        </button>
      ) : null}
      <button type="submit" className="primaryButton">
        조회
      </button>

      {isPanelOpen && trimmed.length >= 2 ? (
        <div className="suggestPanel" id={RESULTS_PANEL_ID} role="listbox">
          {isSearching ? <p className="suggestState">검색 중...</p> : null}
          {error ? <p className="suggestState errorText">{error}</p> : null}
          {!isSearching && !error && results.length === 0 ? <p className="suggestState">검색 결과 없음</p> : null}
          {results.map((result, index) => (
            <button
              type="button"
              className={`suggestItem ${activeIndex === index ? 'active' : ''}`}
              id={`${RESULTS_PANEL_ID}-${index}`}
              key={result.symbol}
              role="option"
              aria-selected={activeIndex === index}
              onClick={() => handlePick(result.symbol)}
              onMouseEnter={() => updateActiveIndex(index)}
            >
              <strong>{result.symbol}</strong>
              <span>{result.name ?? '데이터 없음'}</span>
              <small>{[result.exchange, result.assetType, result.currency].filter(Boolean).join(' / ')}</small>
            </button>
          ))}
        </div>
      ) : null}
    </form>
  );
}
