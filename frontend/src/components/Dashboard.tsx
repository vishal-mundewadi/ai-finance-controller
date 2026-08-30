import { useEffect, useState,useRef } from "react";
import { motion } from "framer-motion";
import { analyzeSettlement, type SettlementAnalysis } from "../api/settlements";

const SETTLEMENT_IDS = [
  "SET0001", "SET0002", "SET0003", "SET0004", "SET0005",
  "SET0006", "SET0007", "SET0008", "SET0009", "SET0010",
];

function Dashboard() {
  const cache = useRef<Record<string, SettlementAnalysis>>({});
  const [selectedId, setSelectedId] = useState("SET0001");
  const [data, setData] = useState<SettlementAnalysis | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
  const cached = cache.current[selectedId];
  if (cached) {
    setData(cached);
    setError(null);
    setLoading(false);
    return;
  }

  setLoading(true);
  setError(null);
  analyzeSettlement("quick", selectedId)
    .then((result) => {
      cache.current[selectedId] = result;
      setData(result);
    })
    .catch((err) => setError(err.message))
    .finally(() => setLoading(false));
}, [selectedId]);

  const discrepancies = data?.results.filter((r) => r.is_discrepancy) ?? [];
  const clean = data?.results.filter((r) => !r.is_discrepancy) ?? [];

  return (
    <div className="min-h-screen bg-white px-6 md:px-16 py-10">
      <header className="mb-10">
        <h1 className="text-3xl md:text-4xl font-extrabold text-black tracking-tight">
          AI Settlement Investigator
        </h1>
        <p className="text-neutral-600 mt-1">
          Select a settlement batch to see what happened to every rupee.
        </p>
      </header>

      {/* Settlement selector */}
      <div className="flex flex-wrap gap-2 mb-8">
        {SETTLEMENT_IDS.map((id) => (
          <button
            key={id}
            onClick={() => setSelectedId(id)}
            className={`px-4 py-2 rounded-md text-sm font-semibold border transition-colors ${
              selectedId === id
                ? "bg-amber-600 text-white border-amber-600"
                : "bg-white text-black border-neutral-300 hover:border-amber-500"
            }`}
          >
            {id}
          </button>
        ))}
      </div>

      {loading && (
  <div className="animate-pulse">
    <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-10">
      <div className="h-24 bg-neutral-100 rounded-lg" />
      <div className="h-24 bg-neutral-100 rounded-lg" />
      <div className="h-24 bg-neutral-100 rounded-lg" />
    </div>
    <div className="h-6 w-48 bg-neutral-100 rounded mb-4" />
    <div className="space-y-4">
      <div className="h-28 bg-neutral-100 rounded-lg" />
      <div className="h-28 bg-neutral-100 rounded-lg" />
    </div>
  </div>
)}
      {error && <p className="text-red-600">Error: {error}</p>}

      {data && !loading && (
        <motion.div
          key={selectedId}
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4 }}
        >
          {/* Summary cards */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-10">
            <SummaryCard label="Total Payments" value={data.total_payments.toString()} />
            <SummaryCard label="Discrepancies Found" value={data.total_discrepancies.toString()} />
            <SummaryCard
              label="Total Discrepancy Amount"
              value={`₹${data.total_discrepancy_amount.toLocaleString("en-IN")}`}
              highlight
            />
          </div>

          {/* Discrepancy list */}
          <h2 className="text-xl font-bold text-black mb-4">
            Discrepancies ({discrepancies.length})
          </h2>
          <div className="space-y-4 mb-10">
            {discrepancies.length === 0 && (
              <p className="text-neutral-500">No discrepancies in this settlement. Clean batch.</p>
            )}
            {discrepancies.map((r) => (
              <DiscrepancyCard key={r.payment_id} result={r} />
            ))}
          </div>

          {/* Clean transactions, collapsed detail */}
          <details className="mb-4">
            <summary className="cursor-pointer text-neutral-500 font-medium">
              {clean.length} clean transactions (no action required)
            </summary>
            <div className="mt-3 space-y-1">
              {clean.map((r) => (
                <p key={r.payment_id} className="text-sm text-neutral-400 font-mono">
                  {r.payment_id} — {r.subtype || "clean"}
                </p>
              ))}
            </div>
          </details>
        </motion.div>
      )}
    </div>
  );
}

function SummaryCard({
  label,
  value,
  highlight = false,
}: {
  label: string;
  value: string;
  highlight?: boolean;
}) {
  return (
    <div className="border border-neutral-200 rounded-lg p-5 bg-white shadow-sm">
      <p className="text-sm text-neutral-500 mb-1">{label}</p>
      <p className={`text-2xl font-bold ${highlight ? "text-amber-600" : "text-black"}`}>
        {value}
      </p>
    </div>
  );
}

function DiscrepancyCard({
  result,
}: {
  result: {
    payment_id: string;
    category: string;
    subtype: string;
    discrepancy_amount: number;
    confidence: number;
    explanation: string;
    recommended_action: string;
    explanation_source?: string;
  };
}) {
  return (
    <div className="border border-amber-200 bg-amber-50/40 rounded-lg p-5">
      <div className="flex justify-between items-start mb-2">
        <div>
          <p className="font-mono text-sm text-neutral-500">{result.payment_id}</p>
          <p className="font-bold text-black">
            {result.category}
            {result.subtype && ` — ${result.subtype}`}
          </p>
        </div>
        <p className="text-lg font-extrabold text-amber-600">
          ₹{Math.abs(result.discrepancy_amount).toLocaleString("en-IN")}
        </p>
      </div>
      <p className="text-neutral-700 text-sm mb-2">{result.explanation}</p>
      <p className="text-sm text-black font-medium mb-2">
        <span className="text-amber-700 font-bold">Recommended action: </span>
        {result.recommended_action}
      </p>
      {result.explanation_source && (
        <span
          className={`inline-block text-xs font-semibold px-2 py-0.5 rounded-full ${
            result.explanation_source === "ai"
              ? "bg-amber-600 text-white"
              : "bg-neutral-200 text-neutral-600"
          }`}
        >
          {result.explanation_source === "ai" ? "✦ AI-generated" : "Template"}
        </span>
      )}
    </div>
  );
}

export default Dashboard;