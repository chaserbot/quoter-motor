import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { QuoteContext, useQuoteReducer } from "@/store/quoteStore";
import { Home } from "@/pages/Home";
import { Review } from "@/pages/Review";
import { Details } from "@/pages/Details";
import { Success } from "@/pages/Success";

const queryClient = new QueryClient();

function AppProviders({ children }: { children: React.ReactNode }) {
  const [state, dispatch] = useQuoteReducer();
  return (
    <QueryClientProvider client={queryClient}>
      <QuoteContext.Provider value={{ state, dispatch }}>
        {children}
      </QuoteContext.Provider>
    </QueryClientProvider>
  );
}

export default function App() {
  return (
    <AppProviders>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/review" element={<Review />} />
          <Route path="/details" element={<Details />} />
          <Route path="/success" element={<Success />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </AppProviders>
  );
}
