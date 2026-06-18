const API_BASE_URL = import.meta.env.VITE_API_BASE_URL;

export async function fetchPortfolio() {
  if (!API_BASE_URL) {
    const response = await fetch(`./data/portfolio.json?v=${Date.now()}`, { cache: "no-store" });
    if (!response.ok) {
      return [];
    }
    const payload = await response.json();
    return {
      positions: payload.positions ?? [],
      opportunities: payload.opportunities ?? [],
      forumSignals: payload.forum_signals ?? [],
      expertSignals: payload.expert_signals ?? [],
    };
  }

  const response = await fetch(`${API_BASE_URL.replace(/\/$/, "")}/api/portfolio`);
  if (!response.ok) {
    throw new Error(`Portfolio API returned ${response.status}`);
  }
  const payload = await response.json();
  return Array.isArray(payload)
    ? { positions: payload, opportunities: [], forumSignals: [] }
    : {
        positions: payload.positions ?? [],
        opportunities: payload.opportunities ?? [],
        forumSignals: payload.forum_signals ?? [],
        expertSignals: payload.expert_signals ?? [],
      };
}
