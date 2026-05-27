import { Search, X } from 'lucide-react';
import { FormEvent, useEffect, useMemo, useRef, useState } from 'react';
import { searchSymbols } from '../api';
import type { SearchResult } from '../types';

type SearchBarProps = {
  onSelect: (symbol: string) => void;
};

export default function SearchBar({ onSelect }: SearchBarProps) {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<SearchResult[]>([]);
  const [isSearching, setIsSearching] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const trimmed = useMemo(() => query.trim(), [query]);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (trimmed.length < 2) {
      setResults([]);
      setError(null);
      setIsSearching(false);
      return;
    }

    const controller = new AbortController();
    const timer = window.setTimeout(() => {
      setIsSearching(true);
      searchSymbols(trimmed, controller.signal)
        .then((payload) => {
          setResults(payload);
          setError(null);
        })
        .catch((reason: Error) => {
          if (reason.name !== 'AbortError') {
            setError(reason.message);
            setResults([]);
          }
        })
        .finally(() => setIsSearching(false));
    }, 300);

    return () => {
      window.clearTimeout(timer);
      controller.abort();
    };
  }, [trimmed]);

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (!trimmed) {
      setError('검색어를 입력해 주세요.');
      inputRef.current?.focus();
      return;
    }
    onSelect(trimmed);
    setResults([]);
  }

  function handlePick(symbol: string) {
    setQuery(symbol);
    setResults([]);
    onSelect(symbol);
  }

  return (
    <form className="searchBox" onSubmit={handleSubmit} role="search">
      <Search size={18} aria-hidden="true" />
      <input
        ref={inputRef}
        aria-label="종목 검색"
        placeholder="티커 또는 종목명 검색"
        value={query}
        maxLength={20}
        onChange={(event) => setQuery(event.target.value)}
      />
      {query ? (
        <button type="button" className="iconButton" aria-label="검색어 지우기" onClick={() => setQuery('')}>
          <X size={16} />
        </button>
      ) : null}
      <button type="submit" className="primaryButton">
        조회
      </button>

      {trimmed.length >= 2 ? (
        <div className="suggestPanel">
          {isSearching ? <p className="suggestState">검색 중...</p> : null}
          {error ? <p className="suggestState errorText">{error}</p> : null}
          {!isSearching && !error && results.length === 0 ? <p className="suggestState">검색 결과 없음</p> : null}
          {results.map((result) => (
            <button type="button" className="suggestItem" key={result.symbol} onClick={() => handlePick(result.symbol)}>
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
