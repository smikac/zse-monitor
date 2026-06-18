const API_BASE_URL = import.meta.env.VITE_API_BASE_URL;

export async function fetchPortfolio() {
  if (!API_BASE_URL) {
    const response = await fetch(`./data/portfolio.json?v=${Date.now()}`, { cache: "no-store" });
    if (!response.ok) {
      return [];
    }
    const payload = await response.json();
    return payload.positions ?? [];
  }

  const response = await fetch(`${API_BASE_URL.replace(/\/$/, "")}/api/portfolio`);
  if (!response.ok) {
    throw new Error(`Portfolio API returned ${response.status}`);
  }
  return response.json();
}
