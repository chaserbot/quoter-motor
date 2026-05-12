import { useNavigate } from "react-router-dom";
import { useQuoteStore } from "@/store/quoteStore";
import { StepNav } from "@/components/StepNav";

export function Success() {
  const { state, dispatch } = useQuoteStore();
  const navigate = useNavigate();

  const flexBaseUrl = "https://clearlamp.flexrentalsolutions.com/f5";

  return (
    <div className="min-h-screen bg-surface text-slate-200 p-8">
      <div className="max-w-2xl mx-auto">
        <div className="mb-6">
          <h1 className="text-2xl font-semibold tracking-tight text-white">Quoter Motor</h1>
        </div>

        <StepNav current={3} />

        <div className="bg-surface-card border border-emerald-600/30 rounded-lg p-8 text-center">
          <div className="text-4xl mb-4">✓</div>
          <h2 className="text-xl font-semibold text-emerald-400 mb-2">Quote Created</h2>
          {state.createdDocNumber && (
            <p className="font-mono text-sky-400 text-lg mb-1">{state.createdDocNumber}</p>
          )}
          {state.createdDocId && (
            <p className="text-slate-500 text-sm mb-6">Document ID: {state.createdDocId}</p>
          )}

          {state.createdDocId && (
            <a
              href={`${flexBaseUrl}/document/${state.createdDocId}`}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-block px-5 py-2 bg-sky-700 hover:bg-sky-600 text-white text-sm rounded transition-colors mb-4"
            >
              Open in Flex →
            </a>
          )}

          <div className="mt-6">
            <button
              onClick={() => {
                dispatch({ type: "RESET" });
                navigate("/");
              }}
              className="text-sm text-slate-500 hover:text-slate-300 underline"
            >
              Start another quote
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
