import { useEffect, useState, useRef } from "react";
import { motion, AnimatePresence, animate } from "framer-motion";
import { analyzeSettlement, type SettlementAnalysis } from "../api/settlements";

const SETTLEMENT_IDS = [
  "SET0001", "SET0002", "SET0003", "SET0004", "SET0005",
  "SET0006", "SET0007", "SET0008", "SET0009", "SET0010",
];

// Animates a number from 0 up to its final value whenever it changes.
function CountUpNumber({
  value,
  prefix = "",
  decimals = 0,
}: {
  value: number;
  prefix?: string;
  decimals?: number;
}) {
  const [display, setDisplay] = useState(`${prefix}0`);

  useEffect(() => {
    const controls = animate(0, value, {
      duration: 0.8,
      ease: "easeOut",
      onUpdate: (latest) => {
        setDisplay(
          `${prefix}${latest.toLocaleString("en-IN", {
            minimumFractionDigits: decimals,
            maximumFractionDigits: decimals,
          })}`
        );
      },
    });
    return controls.stop;
  }, [value, prefix, decimals]);

  return <span>{display}</span>;
}

// Picks a color intensity based on how large the discrepancy amount is.
function severityStyles(amount: number) {
  const abs = Math.abs(amount);
  if (abs >= 5000) {
    return { border: "border-red-300", bg: "bg-red-50/40", text: "text-red-600", badge: "bg-red-600" };
  }
  if (abs >= 500) {
    return { border: "border-amber-300", bg: "bg-amber-50/40", text: "text-amber-600", badge: "bg-amber-600" };
  }
  return { border: "border-yellow-200", bg: "bg-yellow-50/30", text: "text-yellow-600", badge: "bg-yellow-500" };
}

function Dashboard() {
  const [selectedId, setSelectedId] = useState("SET0001");
  const [data, setData] = useState<SettlementAnalysis | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const cache = useRef<Record<string, SettlementAnalysis>>({});

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

      <AnimatePresence mode="wait">
        {data && !loading && (
          <motion.div
            key={selectedId}
            initial={{ opacity: 0, x: 24 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: -24 }}
            transition={{ duration: 0.3, ease: "easeOut" }}
          >
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-10">
              <SummaryCard label="Total Payments">
                <CountUpNumber value={data.total_payments} />
              </SummaryCard>
              <SummaryCard label="Discrepancies Found">
                <CountUpNumber value={data.total_discrepancies} />
              </SummaryCard>
              <SummaryCard label="Total Discrepancy Amount" highlight>
                <CountUpNumber value={data.total_discrepancy_amount} prefix="₹" decimals={2} />
              </SummaryCard>
            </div>

            <h2 className="text-xl font-bold text-black mb-4">
              Discrepancies ({discrepancies.length})
            </h2>
            <div className="space-y-4 mb-10">
              {discrepancies.length === 0 && (
                <p className="text-neutral-500">No discrepancies in this settlement. Clean batch.</p>
              )}
              {discrepancies.map((r, i) => (
                <motion.div
                  key={r.payment_id}
                  initial={{ opacity: 0, y: 15 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.35, delay: i * 0.08 }}
                >
                  <DiscrepancyCard result={r} />
                </motion.div>
              ))}
            </div>

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
      </AnimatePresence>
    </div>
  );
}

function SummaryCard({
  label,
  children,
  highlight = false,
}: {
  label: string;
  children: React.ReactNode;
  highlight?: boolean;
}) {
  return (
    <div className="border border-neutral-200 rounded-lg p-5 bg-white shadow-sm">
      <p className="text-sm text-neutral-500 mb-1">{label}</p>
      <p className={`text-2xl font-bold ${highlight ? "text-amber-600" : "text-black"}`}>
        {children}
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
  const severity = severityStyles(result.discrepancy_amount);

  return (
    <div className={`border ${severity.border} ${severity.bg} rounded-lg p-5`}>
      <div className="flex justify-between items-start mb-2">
        <div>
          <p className="font-mono text-sm text-neutral-500">{result.payment_id}</p>
          <p className="font-bold text-black">
            {result.category}
            {result.subtype && ` — ${result.subtype}`}
          </p>
        </div>
        <p className={`text-lg font-extrabold ${severity.text}`}>
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
              ? `${severity.badge} text-white`
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