const API_BASE = "http://127.0.0.1:8000";

export interface DiscrepancyResult {
  payment_id: string;
  settlement_id: string;
  is_discrepancy: boolean;
  category: string;
  subtype: string;
  discrepancy_amount: number;
  confidence: number;
  explanation: string;
  recommended_action: string;
  explanation_source?: string;
}

export interface SettlementAnalysis {
  settlement_id: string;
  total_payments: number;
  total_discrepancies: number;
  total_discrepancy_amount: number;
  results: DiscrepancyResult[];
}

export async function analyzeSettlement(
  preset: string,
  settlementId: string
): Promise<SettlementAnalysis> {
  const response = await fetch(
    `${API_BASE}/settlements/${preset}/${settlementId}/analyze`
  );
  if (!response.ok) {
    throw new Error(`Failed to analyze ${settlementId}: ${response.status}`);
  }
  return response.json();
}