import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { fetchMatchedQuote, searchQuotes, type FlexDocument } from "@/api/client";
import { useQuoteStore } from "@/store/quoteStore";
import { StepNav } from "@/components/StepNav";

export function Home() {
  const { dispatch } = useQuoteStore();
  const navigate = useNavigate();

  const [input, setInput] = useState("");
  const [searchResults, setSearchResults] = useState<FlexDocument[]>([]);
  const [searching, setSearching] = useState(false);
  const [loading, setLoading] = useState(false);
  const [loadingMsg, setLoadingMsg] = useState("");
  const [error, setError] = useState("");

  async function handleSearch() {
    if (!input.trim()) return;
    setSearching(true);
    setError("");
    try {
      const results = await searchQuotes(input.trim());
      setSearchResults(results);
      if (results.length === 0) setError("No quotes found matching that number.");
    } catch (e: unknown) {
      setError(errorMessage(e));
    } finally {
      setSearching(false);
    }
  }

  async function handleLoad(docId: string) {
    setLoading(true);
    setError("");
    setLoadingMsg("Fetching quote from Flex…");
    try {
      setLoadingMsg("Fetching quote + running AI matching against current inventory…");
      const result = await fetchMatchedQuote(docId);
      dispatch({
        type: "SET_MATCH_RESULTS",
        document: result.document,
        matches: result.matches,
      });
      navigate("/review");
    } catch (e: unknown) {
      setError(errorMessage(e));
    } finally {
      setLoading(false);
    }
  }

  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === "Enter") handleSearch();
  }

  return (
    <div className="min-h-screen bg-surface text-slate-200 p-8">
      <div className="max-w-2xl mx-auto">
        <div className="mb-10">
          <h1 className="text-2xl font-semibold tracking-tight text-white">
            Quoter Motor
          </h1>
          <p className="text-slate-500 text-sm mt-1">
            Recreate a Flex quote with current gear and pricing
          </p>
        </div>

        <StepNav current={0} />

        <div className="bg-surface-card border border-surface-border rounded-lg p-6">
          <h2 className="text-sm font-medium text-slate-400 uppercase tracking-wider mb-4">
            Source Quote
          </h2>

          <div className="flex gap-2">
            <input
              className="flex-1 bg-surface border border-surface-border rounded px-3 py-2 text-sm text-slate-200 placeholder-slate-500 focus:outline-none focus:border-sky-500 font-mono"
              placeholder="Quote number (e.g. Q-2024-0042)"
              value={input}
              onChange={(e) => { setInput(e.target.value); setSearchResults([]); }}
              onKeyDown={handleKeyDown}
              disabled={loading}
            />
            <button
              onClick={handleSearch}
              disabled={searching || loading || !input.trim()}
              className="px-4 py-2 bg-sky-600 hover:bg-sky-700 disabled:opacity-40 text-white text-sm rounded font-medium transition-colors"
            >
              {searching ? "Searching…" : "Search"}
            </button>
          </div>

          {error && (
            <p className="mt-3 text-sm text-red-400">{error}</p>
          )}

          {loading && (
            <div className="mt-4 flex items-center gap-3 text-sm text-slate-400">
              <span className="animate-spin inline-block w-4 h-4 border-2 border-sky-500 border-t-transparent rounded-full" />
              {loadingMsg}
            </div>
          )}

          {searchResults.length > 0 && !loading && (
            <div className="mt-4 space-y-2">
              <p className="text-xs text-slate-500 uppercase tracking-wider">
                {searchResults.length} result{searchResults.length !== 1 ? "s" : ""}
              </p>
              {searchResults.map((doc) => (
                <div
                  key={doc.id}
                  className="flex items-center justify-between p-3 border border-surface-border rounded hover:border-sky-600 transition-colors"
                >
                  <div>
                    <span className="font-mono text-sm text-sky-400">
                      {doc.documentNumber ?? doc.id}
                    </span>
                    {(doc.name as string) && (
                      <span className="ml-3 text-sm text-slate-300">{doc.name as string}</span>
                    )}
                    {(doc.definitionName as string) && (
                      <span className="ml-2 text-xs text-slate-500">({doc.definitionName as string})</span>
                    )}
                    {doc.clientName && (
                      <span className="ml-2 text-xs text-slate-500">— {doc.clientName}</span>
                    )}
                  </div>
                  <button
                    onClick={() => handleLoad(doc.id)}
                    className="ml-4 px-3 py-1 text-sm bg-sky-700 hover:bg-sky-600 text-white rounded transition-colors"
                  >
                    Load →
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>

        <p className="mt-6 text-xs text-slate-600 text-center">
          This will fetch the source quote, pull current inventory, and run AI matching.
          No changes are made until you approve and push.
        </p>
      </div>
    </div>
  );
}

function errorMessage(e: unknown): string {
  if (e instanceof Error) return e.message;
  return "Unexpected error";
}
